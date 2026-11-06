[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$TargetTriple = "",
    [ValidateSet("lite", "rapidocr")]
    [string]$Profile = "lite"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distDir = Join-Path $repoRoot "dist\sidecar"
$workDir = Join-Path $repoRoot "dist\pyinstaller-work"
$specDir = Join-Path $repoRoot "dist\pyinstaller-spec"
$tauriBinDir = Join-Path $repoRoot "apps\desktop\src-tauri\binaries"

New-Item -ItemType Directory -Force -Path $distDir, $workDir, $specDir, $tauriBinDir | Out-Null

if (-not $TargetTriple) {
    $TargetTriple = (& rustc --print host-tuple).Trim()
}
if (-not $TargetTriple) {
    throw "Unable to determine the Rust host target triple."
}

$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm", "--clean", "--onefile", "--noconsole",
    "--name", "labor-case-api",
    "--paths", (Join-Path $repoRoot "apps\api"),
    "--distpath", $distDir,
    "--workpath", $workDir,
    "--specpath", $specDir,
    "--add-data", ((Join-Path $repoRoot "knowledge") + ";knowledge"),
    "--add-data", ((Join-Path $repoRoot "samples") + ";samples"),
    "--add-data", ((Join-Path $repoRoot "models\manifest.json") + ";models"),
    # Optional model runtimes execute these workers with their own private
    # Python interpreter, so the source files must survive PyInstaller's
    # one-file extraction instead of existing only as bundled bytecode.
    "--add-data", ((Join-Path $repoRoot "apps\api\app\model_workers") + ";app/model_workers"),
    "--add-data", ((Join-Path $repoRoot "apps\api\alembic") + ";apps/api/alembic"),
    "--add-data", ((Join-Path $repoRoot "apps\api\alembic.ini") + ";apps/api")
)

if ($Profile -eq "rapidocr") {
    $arguments += @(
        "--hidden-import", "rapidocr_onnxruntime",
        "--hidden-import", "onnxruntime",
        "--collect-data", "rapidocr_onnxruntime"
    )
    # Keep the OCR profile focused on the ONNX/OpenCV runtime. Optional
    # provider imports otherwise make PyInstaller inspect unrelated model and
    # training stacks that are neither needed nor supported in this profile.
    foreach ($module in @(
        "paddleocr", "paddle", "torch", "torchaudio", "torchvision",
        "transformers", "timm", "sklearn", "matplotlib", "plotly", "winrt"
    )) {
        $arguments += @("--exclude-module", $module)
    }
} else {
    # PyInstaller follows imports inside optional provider methods even when
    # those providers are unavailable at runtime. The lite profile excludes
    # the model stacks explicitly so the core API stays a small, honest
    # manual-OCR fallback instead of bundling an accidental training stack.
    foreach ($module in @(
        "rapidocr_onnxruntime", "onnxruntime", "cv2", "paddleocr", "paddle",
        "torch", "torchaudio", "torchvision", "transformers", "timm",
        "sklearn", "matplotlib", "plotly", "winrt"
    )) {
        $arguments += @("--exclude-module", $module)
    }
}
$arguments += (Join-Path $repoRoot "scripts\desktop_api_launcher.py")

& $Python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$source = Join-Path $distDir "labor-case-api.exe"
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "PyInstaller did not produce $source"
}

$target = Join-Path $tauriBinDir "labor-case-api-$TargetTriple.exe"
Copy-Item -Force -LiteralPath $source -Destination $target
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
[pscustomobject]@{
    artifact = $source
    target_triple = $TargetTriple
    profile = $Profile
    sha256 = $hash
    size_bytes = (Get-Item -LiteralPath $source).Length
} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $distDir "manifest.json")

Write-Host "Sidecar ready: $source"
Write-Host "Tauri binary: $target"
