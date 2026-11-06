[CmdletBinding()]
param(
    [switch]$SkipNpmInstall,
    [switch]$SkipSidecar,
    [switch]$SkipWebPrepare,
    [switch]$ReuseCanonicalInstaller,
    [switch]$CommercialRelease,
    [string]$CertificateThumbprint = $env:SIGNING_CERT_THUMBPRINT
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distDir = Join-Path $repoRoot "dist"
$build = Join-Path $PSScriptRoot "build-desktop.ps1"

if (-not $ReuseCanonicalInstaller) {
    & $build `
        -SidecarProfile rapidocr `
        -SkipNpmInstall:$SkipNpmInstall `
        -SkipSidecar:$SkipSidecar `
        -SkipWebPrepare:$SkipWebPrepare `
        -CommercialRelease:$CommercialRelease `
        -CertificateThumbprint $CertificateThumbprint
}

$canonical = Join-Path $distDir "LaborCaseAgent.exe"
$userInstaller = Join-Path $distDir "LaborCaseAgent-UserSetup.exe"
$canonicalManifestPath = Join-Path $distDir "desktop-build-manifest.json"
$canonicalManifest = if (Test-Path -LiteralPath $canonicalManifestPath) {
    Get-Content -LiteralPath $canonicalManifestPath -Raw | ConvertFrom-Json
} else {
    $null
}
if (-not (Test-Path -LiteralPath $canonical -PathType Leaf)) {
    throw "Canonical installer was not produced: $canonical"
}
if (Test-Path -LiteralPath $userInstaller) {
    Remove-Item -LiteralPath $userInstaller -Force
}
Move-Item -LiteralPath $canonical -Destination $userInstaller

$manifest = [ordered]@{
    generated_at = [DateTimeOffset]::Now.ToString("o")
    distribution = [ordered]@{
        artifact = $userInstaller
        edition = "distribution"
        includes_optional_models = $false
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $userInstaller).Hash.ToLowerInvariant()
        size_bytes = (Get-Item -LiteralPath $userInstaller).Length
        signed = [bool]($canonicalManifest -and $canonicalManifest.signed)
        signature_verified_at = if ($canonicalManifest) { $canonicalManifest.signature_verified_at } else { $null }
    }
    roadshow = [ordered]@{
        launcher = (Join-Path $repoRoot "start-roadshow-5090.bat")
        edition = "roadshow"
        model_root = (Join-Path $distDir "models")
        copies_models = $false
    }
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $distDir "edition-build-manifest.json")
$manifest.distribution | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $distDir "desktop-build-manifest.json")
$manifest | ConvertTo-Json -Depth 5
