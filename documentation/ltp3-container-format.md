# LTP3 External-Table Asset Container

## Scope

This document describes the asset container shipped as `data` beside the 1999
`LTP3.exe`. It is related to the later nX `FXLK` format through its LZARI codec,
but it does not have an FXLK header or an embedded index.

The observations apply to the exact preserved pair:

| File | Bytes | SHA-256 |
|---|---:|---|
| `LTP3.exe` | 189,952 | `ac4604d48d0e0441693b342d70640e0eb2b548f9702cac3bb5f9f4ab1c7a80bc` |
| `data` | 1,553,269 | `fa481da550f822118db775cba7e63c789bf35b3e501c80a5c8d923a149d45525` |

## Split metadata design

The container is a bare concatenation of stored file records. It cannot be
decoded reliably by itself because filenames, compression flags, and stored
record sizes live in `LTP3.exe`.

The executable is a PE32 image based at `0x00400000`. Its metadata table begins
at RVA `0x00027030`, VA `0x00427030`, and raw file offset `0x00026430`. It has
157 consecutive records of 12 bytes each:

| Record offset | Size | Meaning |
|---:|---:|---|
| `+0x00` | 4 | Absolute VA of a null-terminated Windows-1252 path |
| `+0x04` | 4 | Compression flag: `0` means raw, nonzero means LZARI |
| `+0x08` | 4 | Complete stored record size in `data` |

All integers are unsigned 32-bit little-endian values. All 157 records in this
release use compression flag `1`. The path strings use forward slashes and begin
with `D:/Devellop/LTP3-Iinvit/`. The misspellings in `Devellop` and `Iinvit` are
original and must not be normalized away.

The original lookup routine treats slash and backslash as equivalent and uses a
case-insensitive comparison. The extractor retains the canonical path spelling
from the table.

## Data record layout

For a compressed metadata record:

| Record offset | Size | Meaning |
|---:|---:|---|
| `+0x00` | 4 | Decoded payload size |
| `+0x04` | record size minus 4 | Headerless LZARI bitstream |

The start of record `n` is the sum of the complete stored sizes of records
`0..n-1`. The sum of all 157 record sizes is exactly 1,553,269 bytes; there are
no gaps, alignment bytes, global header, or trailer.

The first record demonstrates the layout:

| Field | Value |
|---|---|
| Path | `D:/Devellop/LTP3-Iinvit/WolfCube.lwo` |
| Record offset | 0 |
| Complete stored size | 211 bytes |
| Decoded-size prefix | 278 bytes (`0x00000116`) |
| LZARI bytes | 207 bytes at offset 4 |
| Decoded signature | `FORM` / `LWOB` |

The complete table, offsets, sizes, and output hashes are recorded in
[`ltp3-manifest.json`](ltp3-manifest.json).

## LZARI codec

Each record starts a fresh decoder state. The stream carries no end marker; the
decoded-size prefix determines when to stop.

- Sliding window: 4,096 bytes.
- Maximum match: 60 bytes; minimum emitted match: 3 bytes.
- Initial window: 4,036 ASCII spaces followed by 60 zero bytes.
- Initial cursor: 4,036.
- Symbol alphabet: 314 symbols.
- Symbols 0-255 are literals after adaptive symbol-to-character mapping.
- Symbols 256-313 produce matches of `symbol - 253` bytes.
- Arithmetic range: `[0, 0x20000)` with an initial 17-bit code.
- Bits are read most-significant first.
- Character frequencies start at 1 and are adaptively reordered.
- Frequencies are halved when the cumulative total reaches `0x7fff`.
- The fixed position cumulative model is initialized with
  `cum[i-1] = cum[i] + 10000 / (i + 200)` for `i` from 4,096 down to 1.
- Decoded distances range from 1 through 4,096.
- Overlapping window copies reuse bytes written by the same match.

The preservation decoders allow at most two virtual zero bytes of arithmetic
termination lookahead. This is bounded, unlike an unrestricted read past a
record boundary.

The algorithm and constants match the FXLK reader reconstructed for Freestyle,
but the outer organization differs:

| Property | LTP3 `data` | Freestyle FXLK |
|---|---|---|
| Global signature | None | `FXLK` |
| File index | PE table in companion executable | LZARI index in archive |
| Per-file decoded size | Four-byte prefix in each compressed record | In index entry |
| Per-file stored size | PE table | In index entry |
| Filename | PE table | In index entry |
| Payload codec | LZARI in all observed records | LZARI or XOR `0x9a` |

## Reconstruction evidence

The useful observed addresses in `LTP3.exe`, based at `0x00400000`, are:

| Virtual address | Observed role |
|---|---|
| `0x00401440` | Normalize requested path and search the embedded table |
| `0x0040148d` | Load the table cursor corresponding to record field `+0x08` |
| `0x0040149c` | Seek to the cumulative stored offset in `data` |
| `0x004014e3` | Add the current record's stored size on a name mismatch |
| `0x004014eb` | Advance the table cursor by 12 bytes |
| `0x004014ef` | Stop after the last of 157 table records |
| `0x00401511` | Test the record compression flag at field `+0x04` |
| `0x0040153e` | Read the four-byte decoded-size prefix |
| `0x0040158e` | Initialize arithmetic state from the current record |
| `0x00401000` | Read one input bit |
| `0x00401060` | Initialize character and position models |
| `0x004010f0` | Update and rescale the adaptive character model |
| `0x00401230` | Read the initial 17-bit arithmetic value |
| `0x00401250` | Decode a character/length symbol |
| `0x00401350` | Decode a match distance |
| `0x004015c0` | Copy literals/matches into the caller's output buffer |

The table boundaries are also visible in the lookup loop: its cursor begins at
VA `0x00427038` (field `+0x08` in record zero), advances by 12, and terminates
when it reaches `0x00427794` after the final record.

## Extractor behavior and limits

The C and Python implementations validate the entire metadata relationship
before writing output:

- PE and section bounds;
- table bounds and mapped path pointers;
- expected path prefix and Windows-1252 decoding;
- supported flags and nonzero stored record sizes;
- cumulative stored sizes ending exactly at EOF;
- maximum total decoded size of 256 MiB by default;
- safe relative path mapping;
- case-insensitive duplicates and file/directory prefix conflicts.

The C extractor decodes all payloads before creating the destination and refuses
to overwrite an existing destination. It keeps the original drive as directory
`D/`, turning `D:/Devellop/LTP3-Iinvit/Intro.lws` into
`D/Devellop/LTP3-Iinvit/Intro.lws` below the selected output root.

## Limitations

- There is no container checksum. The manifest supplies preservation hashes that
  were not present in the original format.
- Compatibility with another executable build or another early nX archive is
  not claimed. The metadata RVA and count are release-specific and guarded by
  structural checks.
- Raw records are represented by the original lookup code but do not occur in
  this release; all observed records are LZARI-compressed.
- The exact compressor implementation and any authoring-side packer were not
  recovered in this phase.
