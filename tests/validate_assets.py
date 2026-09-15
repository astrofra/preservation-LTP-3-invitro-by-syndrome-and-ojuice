#!/usr/bin/env python3
"""Regression tests for the preserved LTP3 archive and extracted assets."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import wave


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "demo-unpack" / "ltp3-invitation" / "data"
EXECUTABLE = ROOT / "demo-unpack" / "ltp3-invitation" / "LTP3.exe"
ASSETS = ROOT / "demo-assets" / "ltp3-invitation"
MANIFEST = ROOT / "documentation" / "ltp3-manifest.json"
TOOL = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "bin" / "klx_unpack.exe"
if len(sys.argv) > 1:
    del sys.argv[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_lwob(path: Path) -> None:
    data = path.read_bytes()
    if data[:4] != b"FORM" or data[8:12] != b"LWOB":
        raise AssertionError(f"{path}: not a FORM/LWOB object")
    if struct.unpack_from(">I", data, 4)[0] + 8 != len(data):
        raise AssertionError(f"{path}: inconsistent FORM size")
    offset = 12
    while offset < len(data):
        if offset + 8 > len(data):
            raise AssertionError(f"{path}: truncated IFF chunk")
        size = struct.unpack_from(">I", data, offset + 4)[0]
        offset += 8 + size + (size & 1)
    if offset != len(data):
        raise AssertionError(f"{path}: chunk extends beyond FORM")


def validate_tga(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 18:
        raise AssertionError(f"{path}: truncated TGA header")
    id_length, color_map_type, image_type = data[:3]
    color_map_length = struct.unpack_from("<H", data, 5)[0]
    color_map_depth = data[7]
    width, height = struct.unpack_from("<HH", data, 12)
    pixel_depth = data[16]
    if not width or not height or image_type not in (2, 10) or pixel_depth not in (16, 24, 32):
        raise AssertionError(f"{path}: unsupported TGA layout")
    color_map_bytes = color_map_length * ((color_map_depth + 7) // 8) if color_map_type else 0
    offset = 18 + id_length + color_map_bytes
    pixel_bytes = pixel_depth // 8
    remaining = width * height
    if image_type == 2:
        offset += remaining * pixel_bytes
    else:
        while remaining:
            if offset >= len(data):
                raise AssertionError(f"{path}: truncated TGA RLE packet")
            packet = data[offset]
            offset += 1
            count = (packet & 0x7F) + 1
            if count > remaining:
                raise AssertionError(f"{path}: TGA packet exceeds image dimensions")
            offset += pixel_bytes if packet & 0x80 else count * pixel_bytes
            remaining -= count
    if offset > len(data):
        raise AssertionError(f"{path}: truncated TGA pixel data")
    trailer = data[offset:]
    if trailer:
        if len(data) < 26 or data[-18:] != b"TRUEVISION-XFILE.\0":
            raise AssertionError(f"{path}: invalid TGA 2.0 footer")
        extension_offset, developer_offset = struct.unpack_from("<II", data, len(data) - 26)
        if developer_offset or extension_offset != offset or extension_offset + 495 != len(data) - 26:
            raise AssertionError(f"{path}: inconsistent TGA extension area")
        if struct.unpack_from("<H", data, extension_offset)[0] != 495:
            raise AssertionError(f"{path}: invalid TGA extension size")


class Ltp3AssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tool = TOOL
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def run_tool(self, *arguments: object, success: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [str(self.tool), *(str(argument) for argument in arguments)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if success and result.returncode != 0:
            self.fail(f"extractor failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
        if not success and result.returncode == 0:
            self.fail(f"extractor unexpectedly succeeded:\n{result.stdout}")
        return result

    def test_manifest_and_committed_assets(self) -> None:
        manifest = self.manifest
        self.assertEqual(manifest["archive_sha256"], sha256(ARCHIVE))
        self.assertEqual(manifest["metadata_executable_sha256"], sha256(EXECUTABLE))
        self.assertEqual(manifest["file_count"], 157)
        self.assertEqual(manifest["total_size"], 2_819_572)
        found = sorted(path for path in ASSETS.rglob("*") if path.is_file())
        self.assertEqual(len(found), 157)
        self.assertEqual(sum(path.stat().st_size for path in found), manifest["total_size"])
        for entry in manifest["entries"]:
            path = ASSETS / entry["path"]
            self.assertTrue(path.is_file(), entry["path"])
            self.assertEqual(path.stat().st_size, entry["size"], entry["path"])
            self.assertEqual(sha256(path), entry["sha256"], entry["path"])

    def test_format_families(self) -> None:
        counts = Counter(path.suffix.lower() for path in ASSETS.rglob("*") if path.is_file())
        self.assertEqual(
            counts,
            Counter({".lwo": 74, ".tga": 49, ".lws": 18, ".wav": 9, ".moa": 4, ".giz": 2, ".xm": 1}),
        )
        for path in ASSETS.rglob("*.lwo"):
            validate_lwob(path)
        for path in ASSETS.rglob("*.tga"):
            validate_tga(path)
        for path in ASSETS.rglob("*.lws"):
            self.assertEqual(path.read_bytes().decode("cp1252").splitlines()[:2], ["LWSC", "1"])
        for path in ASSETS.rglob("*.wav"):
            with wave.open(str(path), "rb") as stream:
                self.assertEqual(stream.getnchannels(), 1)
                self.assertIn(stream.getsampwidth(), (1, 2))
                self.assertIn(stream.getframerate(), (11025, 22050, 44100))
                self.assertGreater(stream.getnframes(), 0)
        for path in ASSETS.rglob("*.moa"):
            self.assertEqual(path.read_bytes()[:4], b"MOA1")
        for path in ASSETS.rglob("*.giz"):
            self.assertTrue(path.read_bytes().startswith(b"MORPHGIZMO\n\nVERSION 1\n"))
        modules = list(ASSETS.rglob("*.xm"))
        self.assertEqual(len(modules), 1)
        self.assertTrue(modules[0].read_bytes().startswith(b"Extended Module: "))

    def test_c_extractor_matches_manifest(self) -> None:
        listing = self.run_tool("--list", "--ltp3-exe", EXECUTABLE, ARCHIVE)
        self.assertIn("157 files", listing.stdout)
        self.assertEqual(listing.stdout.count(" lzari "), 157)
        with tempfile.TemporaryDirectory(prefix="ltp3-unpack-") as temporary:
            output = Path(temporary) / "assets"
            self.run_tool("--ltp3-exe", EXECUTABLE, ARCHIVE, output)
            for entry in self.manifest["entries"]:
                path = output / entry["path"]
                self.assertEqual(path.stat().st_size, entry["size"], entry["path"])
                self.assertEqual(sha256(path), entry["sha256"], entry["path"])
            self.run_tool("--ltp3-exe", EXECUTABLE, ARCHIVE, output, success=False)

    def test_rejects_inconsistent_container(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ltp3-invalid-") as temporary:
            temporary = Path(temporary)
            truncated = temporary / "data"
            truncated.write_bytes(ARCHIVE.read_bytes()[:-1])
            output = temporary / "output"
            self.run_tool("--ltp3-exe", EXECUTABLE, truncated, output, success=False)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
