# Labor Case Agent desktop shell

This Tauri v2 shell embeds a PyInstaller-built FastAPI sidecar, the full
Next.js standalone workspace, and a bundled Node.js runtime. Both services
bind to loopback only; the WebView opens the workspace at `127.0.0.1:3000`.

Build from the repository root on Windows:

```powershell
.\scripts\build-desktop.ps1 -SidecarProfile rapidocr
```

The script builds the Python sidecar first, applies Tauri's required Rust target
suffix, builds an NSIS installer, and copies verified artifacts to `dist/`.
`dist/LaborCaseAgent.exe` is the canonical installer, not a portable binary.

The verified v0.2 release uses the `rapidocr` profile and includes its CPU
ONNX runtime. The script's `lite` profile remains available for a smaller
manual-fallback build. CUDA/audio/embedding runtimes and model weights remain
external in both profiles.
