# LTP3 Invitation Asset Extraction Process

## Outcome

The original distribution was preserved unchanged, its ordinary ZIP layer was
expanded, and the demo-specific `data` container was reconstructed into 157
original asset files. The decoded payloads total 2,819,572 bytes and include
the LightWave scenes and objects, soundtrack, sound effects, textures, and
animation-support files used by the demo.

Nothing inside the decoded assets was converted, renamed, repaired, translated,
or rewritten. Original Windows-1252 spelling, capitalization, accents, and the
historical `D:/Devellop/LTP3-Iinvit/` path are retained. The drive letter is
represented as the ordinary top-level directory `D/` so that extraction remains
contained within the repository. `.gitattributes` marks the release, unpacked
distribution, and decoded-asset trees as binary so Git cannot normalize original
text payloads or their line endings.

## Preservation layout

| Preservation layer | Repository location |
|---|---|
| Untouched distribution | `demo-releases/ltp3-invitation.zip` |
| Expanded ZIP contents | `demo-unpack/ltp3-invitation/` |
| Decoded original assets | `demo-assets/ltp3-invitation/` |
| Native extractor source | `klx_unpack.c` |
| Python reference decoder | `tools/unpack_ltp3.py` |
| Per-file provenance and hashes | `documentation/ltp3-manifest.json` |
| Regression checks | `tests/validate_assets.py` |

## Source artifact

The source ZIP is 1,713,277 bytes and has SHA-256:

```text
c69b1fcf3eeb43baad107396530348654519597e163348ca21eef8ba3d2cb12e
```

Its seven entries are recorded below. Sizes and timestamps come from the ZIP
central directory; hashes are over the expanded bytes.

| ZIP entry | Bytes | Compressed bytes | CRC-32 | SHA-256 | ZIP timestamp |
|---|---:|---:|---|---|---|
| `Add info for ATI rage 128 user.txt` | 73 | 69 | `64fe03da` | `df7b2834477c83ef28b1ad649d40a3a73385e886a1d42dca158040b6bf66659a` | 1999-07-03 16:19:54 |
| `LTP3.exe` | 189,952 | 77,276 | `d9dcf36d` | `ac4604d48d0e0441693b342d70640e0eb2b548f9702cac3bb5f9f4ab1c7a80bc` | 1999-06-04 05:06:44 |
| `Tech-Info.txt` | 2,743 | 1,418 | `11447e7d` | `b0ffcda434f4fbfa18971ece0c106c150ae1d3c1197f82a7623cd9bb0256e164` | 1999-06-04 16:10:56 |
| `midas11.dll` | 160,256 | 83,356 | `706a8713` | `1b9ec903edeb6e91fff67539c381c4e4d55543e61aa572ce09863c270a0a2054` | 1998-03-01 22:34:52 |
| `data` | 1,553,269 | 1,549,477 | `525799b9` | `fa481da550f822118db775cba7e63c789bf35b3e501c80a5c8d923a149d45525` | 1999-06-04 05:03:10 |
| `file_id.diz` | 185 | 134 | `82c11bc4` | `0708d1569f4706e52792e083194ecb915d0a586f7a33ab7d3a4d4ec3331db867` | 1999-06-04 03:57:04 |
| `ltp3 invit.nfo` | 1,676 | 803 | `da93064a` | `a1b0a8a177f53a651892189b6b2e0756bc8d8c44e51dc31371e97f452ad09897` | 1999-07-03 16:25:18 |

ZIP timestamps have no timezone field. They are reproduced as stored and are
not asserted to be UTC.

## Chronological reconstruction log

### 1. Reference workflow inspection

The extraction work in
`C:/works/projects/preservation-freestyle-by-syndrome-condense` was used as the
local reference. Its extractor, Python prototype, manifest, tests, directory
separation, path-safety rules, and format documentation established the desired
preservation shape. The relevant Freestyle extraction commit is `18234d7`.

The starting `klx_unpack.c`, `tools/unpack_klx.py`, and Windows extractor in this
repository were byte-identical to their Freestyle counterparts. They implement
the nX engine's FXLK wrapper and LZARI codec.

### 2. Outer archive expansion

The ZIP directory was inspected before writing files. It contained no absolute
paths, traversal components, duplicate names, or nested directories. It was
expanded into a new `demo-unpack/ltp3-invitation/` directory. The SHA-256 hashes
of all seven expanded entries were then captured.

```powershell
Expand-Archive -LiteralPath demo-releases/ltp3-invitation.zip `
    -DestinationPath demo-unpack/ltp3-invitation
```

### 3. FXLK hypothesis rejected

The Freestyle inner archive begins with ASCII `FXLK`. LTP3's `data` begins:

```text
16 01 00 00 c6 b8 be 2c 32 a8 9e 8d 6a 2c f2 e1
```

Consequently the existing FXLK parser correctly rejected it. The first value,
`0x00000116` (278), was initially considered as a possible entry count. Binary
analysis and a successful first-file decode showed that it is instead the
decoded size of `WolfCube.lwo`.

### 4. Executable inspection

`LTP3.exe` is an ordinary PE32 image with image base `0x00400000` and entry RVA
`0x0001d2c0`; UPX 5.1.1 reports that it is not UPX-packed. Static strings expose
the original asset paths, but `data` itself contains neither paths nor an index.

Rizin analysis located the file lookup routine at virtual address `0x00401440`.
It walks a 157-entry metadata table embedded in the executable at RVA
`0x00027030` (VA `0x00427030`, raw file offset `0x00026430`). Each 12-byte entry
holds an absolute path pointer, a compression flag, and the complete stored
record size. The sum of the 157 record sizes is exactly 1,553,269 bytes, the size
of `data`.

Every release entry has compression flag `1`. The lookup routine reads a
four-byte decoded-size prefix from the selected record and then initializes the
same 4 KiB LZARI decoder used in the later FXLK format. Full structural details
and observed code addresses are in
[`ltp3-container-format.md`](ltp3-container-format.md).

### 5. First proof decode

The first metadata record names `D:/Devellop/LTP3-Iinvit/WolfCube.lwo`, has a
stored record size of 211 bytes, and declares a decoded size of 278 bytes. The
remaining 207 bytes decode to:

```text
46 4f 52 4d 00 00 01 0e 4c 57 4f 42 ...
F  O  R  M              L  W  O  B
```

The IFF FORM size is internally consistent and identifies an original LightWave
object. This corrected the earlier entry-count hypothesis and established the
record boundary and codec use.

### 6. Extractor implementation

`klx_unpack.c` was extended rather than replaced. Existing FXLK support remains
available. LTP3 mode:

- requires `LTP3.exe` explicitly through `--ltp3-exe`;
- parses and bounds-checks the PE32 section table;
- maps the known metadata-table RVA through the PE sections;
- validates all 157 names, flags, sizes, cumulative offsets, and path conflicts;
- decodes every payload before it creates the destination;
- refuses existing destinations, unsafe paths, links, duplicate paths, and
  file/directory prefix collisions;
- preserves Windows-1252 names by converting them to UTF-8/UTF-16 only for host
  filesystem access.

The explicit executable argument is intentional. The `data` bytes are not
self-describing, so retaining the exact matching executable is required to
recover names and boundaries.

### 7. Full extraction

The release extractor was built with CMake 3.30.3 and MSVC 19.41 using C99,
`/W4 /WX`, and the static Microsoft C runtime. The resulting Windows x64 binary
imports only `KERNEL32.dll`. The commands were:

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
./bin/klx_unpack.exe --list --ltp3-exe `
    demo-unpack/ltp3-invitation/LTP3.exe `
    demo-unpack/ltp3-invitation/data
./bin/klx_unpack.exe --ltp3-exe `
    demo-unpack/ltp3-invitation/LTP3.exe `
    demo-unpack/ltp3-invitation/data `
    demo-assets/ltp3-invitation
```

The checked-in `bin/klx_unpack.exe` is 163,328 bytes with SHA-256:

```text
ec6396beb4060dd0e14ae636e52e3ec3d0733c7f3a7b7fb5930b34f826ccdbfb
```

The analysis/build environment was Windows with Windows SDK 10.0.22621.0,
Rizin 0.9.1, UPX 5.1.1, CMake 3.30.3, MSVC 19.41, and Python 3.12.5. These
versions describe this run; the extractor format is not intended to depend on
them.

### 8. Independent implementation comparison

`tools/unpack_ltp3.py` independently parses the PE metadata table and performs
the extraction using the Python LZARI implementation. Python 3.12.5 decoded all
157 records into an ignored analysis directory. Relative paths, sizes, and
SHA-256 hashes were compared with the C output: all 157 files matched and there
were zero differences.

The Python output generated `documentation/ltp3-manifest.json`, which records
both source hashes, every record and payload offset, stored and decoded sizes,
original and local paths, method, and per-file SHA-256.

### 9. Format and regression validation

All asset families were structurally checked. TGA images were also fully decoded
with Pillow during the preservation run. The repeatable standard-library tests
validate the committed asset hashes and structures, perform a fresh extraction,
compare it with the manifest, verify overwrite refusal, and ensure a truncated
container is rejected before an output directory is created.

```powershell
ctest --test-dir build -C Release --output-on-failure
```

See [`ASSET_VALIDATION.md`](ASSET_VALIDATION.md) for the results and limits.

## Re-extracting with Python

The Python implementation writes a `manifest.json` inside its new output tree:

```powershell
python tools/unpack_ltp3.py `
    demo-unpack/ltp3-invitation/LTP3.exe `
    demo-unpack/ltp3-invitation/data `
    analysis/python-extract
```

List metadata without decoding payloads:

```powershell
python tools/unpack_ltp3.py --list `
    demo-unpack/ltp3-invitation/LTP3.exe `
    demo-unpack/ltp3-invitation/data
```

## Evidence boundaries and remaining uncertainty

- The ZIP, executable, container, and decoded files are preserved; the original
  authoring directories and filesystem timestamps outside the ZIP are unknown.
- `data` has no signature, embedded filenames, checksums, or timestamps. Its
  interpretation depends on the matching `LTP3.exe` hash recorded above.
- The original x86 routine was statically inspected, but was not executed under
  emulation for a third byte-for-byte oracle. Confidence instead comes from two
  implementations, exact record-size accounting, valid payload structures, and
  complete hash agreement.
- MOA1 and morph-gizmo payloads are preserved in their original formats; their
  complete semantics were not reverse-engineered in this extraction phase.
- No claim is made here about modern playback, DirectDraw/Direct3D rendering,
  MIDAS audio parity, scene timing, or visual fidelity. This phase recovers the
  original production inputs only.
