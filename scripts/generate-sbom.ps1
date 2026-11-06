[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist\sbom"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$output = Join-Path $repoRoot $OutputDirectory
New-Item -ItemType Directory -Force -Path $output | Out-Null

Push-Location (Join-Path $repoRoot "apps\web")
try {
    $npmSbom = npm sbom --sbom-format cyclonedx
    if ($LASTEXITCODE -ne 0) { throw "npm SBOM generation failed." }
    $npmSbom | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $output "web.cdx.json")
} finally {
    Pop-Location
}

$python = if (Test-Path (Join-Path $repoRoot ".venv\Scripts\python.exe")) {
    Join-Path $repoRoot ".venv\Scripts\python.exe"
} else {
    "python"
}
& $python -m pip show cyclonedx-bom *> $null
if ($LASTEXITCODE -ne 0) {
    throw "cyclonedx-bom is required. Install it with: python -m pip install cyclonedx-bom"
}
& $python -m cyclonedx_py environment --output-format JSON --output-reproducible `
    --output-file (Join-Path $output "api.cdx.json")
if ($LASTEXITCODE -ne 0) { throw "Python SBOM generation failed." }

cargo cyclonedx --manifest-path (Join-Path $repoRoot "apps\desktop\src-tauri\Cargo.toml") `
    --format json --override-filename desktop
if ($LASTEXITCODE -ne 0) {
    throw "cargo-cyclonedx is required. Install it with: cargo install cargo-cyclonedx"
}
Move-Item -Force -LiteralPath (Join-Path $repoRoot "apps\desktop\src-tauri\desktop.cdx.json") `
    -Destination (Join-Path $output "desktop.cdx.json")

$index = Get-ChildItem -LiteralPath $output -Filter "*.cdx.json" -File | ForEach-Object {
    [pscustomobject]@{
        file = $_.Name
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
        size_bytes = $_.Length
    }
}
$index | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $output "index.json")
$index | Format-Table -AutoSize
