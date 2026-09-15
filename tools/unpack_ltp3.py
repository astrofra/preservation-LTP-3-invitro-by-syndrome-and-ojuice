#!/usr/bin/env python3
"""Extract the LTP3 companion `data` archive using metadata from LTP3.exe.

Python 3.10+ and the sibling unpack_klx.py module are required; there are no
third-party dependencies. See documentation/ltp3-container-format.md.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys

from unpack_klx import FormatError, LzariDecoder, relative_path


TABLE_RVA = 0x27030
ENTRY_COUNT = 157
PATH_PREFIX = "D:/Devellop/LTP3-Iinvit/"
MAX_BYTES = 256 * 1024 * 1024


class PeImage:
    """Small, bounds-checked PE32 RVA reader for the preserved executable."""

    def __init__(self, data: bytes):
        if len(data) < 0x40 or data[:2] != b"MZ":
            raise FormatError("metadata executable is not an MZ file")
        nt_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if nt_offset + 24 > len(data) or data[nt_offset : nt_offset + 4] != b"PE\0\0":
            raise FormatError("metadata executable has no valid PE header")
        self.section_count = struct.unpack_from("<H", data, nt_offset + 6)[0]
        optional_size = struct.unpack_from("<H", data, nt_offset + 20)[0]
        optional = nt_offset + 24
        if (
            optional_size < 64
            or optional + optional_size > len(data)
            or struct.unpack_from("<H", data, optional)[0] != 0x10B
        ):
            raise FormatError("metadata executable is not a supported PE32 image")
        if not 0 < self.section_count <= 96:
            raise FormatError("invalid PE section count")
        self.image_base = struct.unpack_from("<I", data, optional + 28)[0]
        self.size_of_headers = struct.unpack_from("<I", data, optional + 60)[0]
        section_table = optional + optional_size
        if section_table + self.section_count * 40 > len(data):
            raise FormatError("truncated PE section table")
        self.data = data
        self.sections = []
        for index in range(self.section_count):
            offset = section_table + index * 40
            virtual_size, rva, raw_size, raw_offset = struct.unpack_from(
                "<IIII", data, offset + 8
            )
            self.sections.append((rva, max(virtual_size, raw_size), raw_offset, raw_size))

    def map_rva(self, rva: int) -> memoryview:
        if 0 <= rva < min(self.size_of_headers, len(self.data)):
            return memoryview(self.data)[rva : self.size_of_headers]
        for start, span, raw_offset, raw_size in self.sections:
            if start <= rva < start + span:
                delta = rva - start
                if delta >= raw_size or raw_offset + raw_size > len(self.data):
                    break
                return memoryview(self.data)[raw_offset + delta : raw_offset + raw_size]
        raise FormatError(f"unmapped or uninitialized PE RVA 0x{rva:08x}")

    def c_string_at_va(self, va: int) -> str:
        if va < self.image_base:
            raise FormatError(f"invalid image address 0x{va:08x}")
        region = self.map_rva(va - self.image_base)
        try:
            end = region.tobytes().index(0)
        except ValueError as exc:
            raise FormatError(f"unterminated string at 0x{va:08x}") from exc
        if not 0 < end <= 4096:
            raise FormatError(f"invalid string length at 0x{va:08x}")
        return region[:end].tobytes().decode("cp1252")


@dataclass(frozen=True)
class Entry:
    name: str
    path: Path
    record_offset: int
    record_size: int
    size: int
    payload_offset: int
    stored_size: int

    @property
    def method(self) -> str:
        return "lzari"

    def decode(self, archive: bytes) -> bytes:
        payload = archive[self.payload_offset : self.payload_offset + self.stored_size]
        try:
            return LzariDecoder(payload).decode(self.size)
        except FormatError as exc:
            raise FormatError(f"{self.name}: {exc}") from exc


def read_entries(archive: bytes, executable: bytes, max_bytes: int = MAX_BYTES) -> list[Entry]:
    pe = PeImage(executable)
    table = pe.map_rva(TABLE_RVA)
    if len(table) < ENTRY_COUNT * 12:
        raise FormatError("truncated LTP3 metadata table")
    entries = []
    record_offset = 0
    total = 0
    seen: list[tuple[str, ...]] = []
    for index in range(ENTRY_COUNT):
        name_va, compressed, record_size = struct.unpack_from("<III", table, index * 12)
        name = pe.c_string_at_va(name_va)
        if not name.startswith(PATH_PREFIX):
            raise FormatError(f"unexpected LTP3 asset path: {name!r}")
        if compressed != 1:
            raise FormatError(f"unsupported storage flag {compressed} for {name}")
        if record_size < 4 or record_offset + record_size > len(archive):
            raise FormatError(f"invalid stored size for {name}")
        size = struct.unpack_from("<I", archive, record_offset)[0]
        total += size
        if total > max_bytes:
            raise FormatError("declared output exceeds --max-output-mib")
        path = relative_path(name)
        key = tuple(part.casefold() for part in path.parts)
        if any(key == other or key[: len(other)] == other or other[: len(key)] == key for other in seen):
            raise FormatError(f"duplicate or conflicting output path: {path}")
        seen.append(key)
        entries.append(
            Entry(name, path, record_offset, record_size, size, record_offset + 4, record_size - 4)
        )
        record_offset += record_size
    if record_offset != len(archive):
        raise FormatError(f"unaccounted archive bytes: {len(archive) - record_offset}")
    return entries


def manifest_for(
    archive: bytes,
    executable: bytes,
    archive_name: str,
    executable_name: str,
    entries: list[Entry],
    decoded: list[bytes],
) -> dict:
    return {
        "format": "LTP3 external-table LZARI container",
        "archive": archive_name,
        "archive_size": len(archive),
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "metadata_executable": executable_name,
        "metadata_executable_size": len(executable),
        "metadata_executable_sha256": hashlib.sha256(executable).hexdigest(),
        "metadata_table_rva": f"0x{TABLE_RVA:08x}",
        "filename_encoding": "Windows-1252",
        "path_mapping": "D:/path/file -> D/path/file (drive retained as directory)",
        "file_count": len(entries),
        "total_size": sum(entry.size for entry in entries),
        "entries": [
            {
                "original_path": entry.name,
                "path": entry.path.as_posix(),
                "record_offset": entry.record_offset,
                "record_size": entry.record_size,
                "payload_offset": entry.payload_offset,
                "stored_size": entry.stored_size,
                "size": entry.size,
                "method": entry.method,
                "sha256": hashlib.sha256(contents).hexdigest(),
            }
            for entry, contents in zip(entries, decoded, strict=True)
        ],
    }


def extract(
    archive: bytes,
    executable: bytes,
    entries: list[Entry],
    output: Path,
    archive_name: str,
    executable_name: str,
) -> None:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    decoded = [entry.decode(archive) for entry in entries]
    for entry, contents in zip(entries, decoded, strict=True):
        target = output / entry.path
        if not target.resolve().is_relative_to(output):
            raise FormatError(f"output path escapes destination: {entry.path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(contents)
    manifest = manifest_for(
        archive, executable, archive_name, executable_name, entries, decoded
    )
    with (output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path, help="LTP3.exe carrying the metadata table")
    parser.add_argument("archive", type=Path, help="companion data file")
    parser.add_argument("output", nargs="?", type=Path, help="new extraction directory")
    parser.add_argument("--list", action="store_true", help="list entries without decoding")
    parser.add_argument("--max-output-mib", type=int, default=256)
    args = parser.parse_args()
    if not args.list and args.output is None:
        parser.error("provide an output directory or --list")
    if args.list and args.output is not None:
        parser.error("--list does not accept an output directory")
    if args.max_output_mib <= 0:
        parser.error("--max-output-mib must be positive")
    try:
        archive = args.archive.read_bytes()
        executable = args.executable.read_bytes()
        entries = read_entries(archive, executable, args.max_output_mib * 1024 * 1024)
        if args.list:
            for entry in entries:
                print(
                    f"{entry.payload_offset:9d} {entry.stored_size:9d} "
                    f"{entry.size:9d} {entry.method:7s} {entry.name}"
                )
        else:
            extract(
                archive,
                executable,
                entries,
                args.output,
                str(args.archive),
                str(args.executable),
            )
            print(f"Extracted to {args.output.resolve()}")
        counts = Counter(entry.path.suffix.lower() for entry in entries)
        print(
            f"{len(entries)} files, {sum(entry.size for entry in entries):,} decoded bytes; "
            f"{dict(sorted(counts.items()))}"
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
