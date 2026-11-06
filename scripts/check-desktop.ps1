[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$tauri = Join-Path $repoRoot "apps\desktop\src-tauri"
$createdFiles = [System.Collections.Generic.List[string]]::new()
$createdDirectories = [System.Collections.Generic.List[string]]::new()

function Add-CheckPlaceholder([string]$Path) {
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
        $createdDirectories.Add($parent)
    }
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType File -Path $Path | Out-Null
        $createdFiles.Add($Path)
    }
}

Add-CheckPlaceholder (Join-Path $tauri "binaries\labor-case-api-x86_64-pc-windows-msvc.exe")
Add-CheckPlaceholder (Join-Path $tauri "resources\node\node.exe")
Add-CheckPlaceholder (Join-Path $tauri "resources\web\.check-placeholder")

try {
    cargo check --manifest-path (Join-Path $tauri "Cargo.toml")
    if ($LASTEXITCODE -ne 0) { throw "Desktop cargo check failed." }
} finally {
    foreach ($path in $createdFiles) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
    foreach ($path in ($createdDirectories | Sort-Object Length -Descending)) {
        if ((Test-Path -LiteralPath $path) -and -not (Get-ChildItem -LiteralPath $path -Force)) {
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        }
    }
}
