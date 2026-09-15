# Preservation of the LTP3 Invitation

Asset extraction for the **LTP3 Invitation**, a 1999 Win32 demo by Syndrome
and Orange Juice. The untouched distribution archive is kept in
`demo-releases/`, its ordinary ZIP contents in `demo-unpack/`, and the 157
decoded production assets in `demo-assets/`.

The recovered files include the original LightWave objects and scenes, TGA
textures, XM soundtrack, WAV effects, MOA animations, and morph-gizmo files.
No asset paths or payloads have been rewritten.

Build and extract on Windows:

```powershell
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
./bin/klx_unpack.exe --ltp3-exe demo-unpack/ltp3-invitation/LTP3.exe `
    demo-unpack/ltp3-invitation/data demo-assets/another-extraction
```

The destination must not already exist. Run the regression checks with:

```powershell
ctest --test-dir build -C Release --output-on-failure
```

See the [complete extraction process](documentation/EXTRACTION_PROCESS.md),
[container format](documentation/ltp3-container-format.md),
[asset validation report](documentation/ASSET_VALIDATION.md), and
[SHA-256 manifest](documentation/ltp3-manifest.json).
