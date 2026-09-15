# LTP3 Extracted Asset Validation

## Summary

Both preservation decoders produced the same 157 relative paths, byte sizes, and
SHA-256 hashes. The extracted tree contains 2,819,572 bytes.

| Extension | Count | Decoded bytes | Validation performed |
|---|---:|---:|---|
| `.lwo` | 74 | 226,444 | `FORM/LWOB`, FORM length, and every padded IFF chunk boundary |
| `.lws` | 18 | 84,872 | Windows-1252 text; every file starts with `LWSC` and version `1` |
| `.tga` | 49 | 1,169,536 | TGA 2.0 structure and RLE packet bounds; full Pillow decode |
| `.wav` | 9 | 346,152 | RIFF/WAVE opened through Python's `wave` decoder; channel/rate/sample checks |
| `.xm` | 1 | 859,907 | FastTracker XM signature and header fields |
| `.moa` | 4 | 127,742 | Original `MOA1` signature retained |
| `.giz` | 2 | 4,919 | Text signature `MORPHGIZMO`, version 1 |
| **Total** | **157** | **2,819,572** | Per-file SHA-256 in the manifest |

## LightWave assets

All 74 `.lwo` files are big-endian IFF `FORM` files of type `LWOB`. For every
object, the FORM size equals the file size minus eight bytes and every child
chunk, including even-byte padding, ends within the FORM boundary.

All 18 `.lws` files are LightWave scene text files with the two-line header:

```text
LWSC
1
```

The absolute asset references inside scenes are intentionally unchanged.

## Textures

All 49 textures are TGA 2.0 RLE true-color images with 16-bit stored pixels, a
495-byte extension area, and a valid `TRUEVISION-XFILE.` footer. Pillow fully
decoded every image as RGBA during this preservation run.

Fourteen distinct dimensions occur:

| Dimensions | Count |
|---|---:|
| 64 x 64 | 8 |
| 93 x 57 | 1 |
| 112 x 33 | 1 |
| 128 x 32 | 2 |
| 128 x 64 | 5 |
| 128 x 88 | 1 |
| 128 x 128 | 8 |
| 128 x 256 | 1 |
| 160 x 64 | 1 |
| 230 x 256 | 1 |
| 256 x 64 | 7 |
| 256 x 128 | 3 |
| 256 x 256 | 9 |
| 490 x 10 | 1 |

## Audio

The soundtrack is the original 859,907-byte XM module:

| Header field | Value |
|---|---|
| Module name | `Syndrome Mob` |
| Tracker | `FastTracker v2.00` |
| XM version | 1.04 |
| Song length | 32 orders |
| Restart position | 7 |
| Channels | 32 |
| Patterns | 31 |
| Instruments | 27 |
| Default tempo | 3 |
| Default BPM | 125 |

The nine effects are valid mono PCM WAVE files:

| File | Sample format | Rate | Frames | Duration |
|---|---|---:|---:|---:|
| `Batman.wav` | 8-bit mono | 22,050 Hz | 34,193 | 1.550703 s |
| `Boulard.wav` | 8-bit mono | 22,050 Hz | 31,488 | 1.428027 s |
| `Cochon.wav` | 8-bit mono | 11,025 Hz | 6,613 | 0.599819 s |
| `maF.wav` | 8-bit mono | 44,100 Hz | 66,143 | 1.499841 s |
| `Mamut.wav` | 8-bit mono | 22,050 Hz | 50,156 | 2.274649 s |
| `nintendo.wav` | 16-bit mono | 22,050 Hz | 12,016 | 0.544943 s |
| `Ovni.wav` | 8-bit mono | 11,025 Hz | 36,163 | 3.280091 s |
| `Para.wav` | 8-bit mono | 22,050 Hz | 42,335 | 1.919955 s |
| `Squeezed.wav` | 8-bit mono | 22,050 Hz | 54,633 | 2.477687 s |

This phase validates structure and metadata. It does not claim a listening test,
sample-accurate MIDAS playback parity, or decoded PCM comparison.

## Animation-support formats

The four `.moa` payloads begin with `MOA1`, unlike the later `MOA3` files found
in Freestyle. The two `.giz` files are readable morph-gizmo descriptions with
the header `MORPHGIZMO`, version 1, and original absolute LightWave paths. These
files are preserved without a claim that their full semantics are understood.

## Reproducible checks

The committed regression performs four groups of checks:

1. source and per-file hashes against `ltp3-manifest.json`;
2. structural checks for every asset family;
3. a clean C extraction followed by 157 size/hash comparisons;
4. refusal to overwrite and rejection of a truncated `data` file before output.

Run it after building:

```powershell
ctest --test-dir build -C Release --output-on-failure
```

The Python reference decoder provides a second implementation:

```powershell
python tools/unpack_ltp3.py --list `
    demo-unpack/ltp3-invitation/LTP3.exe `
    demo-unpack/ltp3-invitation/data
```

The authoritative file-level evidence is
[`ltp3-manifest.json`](ltp3-manifest.json).
