[CmdletBinding()]
param(
    [switch]$SkipNpmInstall,
    [switch]$SkipSidecar,
    [switch]$SkipWebPrepare,
    [ValidateSet("lite", "rapidocr")]
    [string]$SidecarProfile = "lite",
    [switch]$CommercialRelease,
    [string]$CertificateThumbprint = $env:SIGNING_CERT_THUMBPRINT
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$desktopDir = Join-Path $repoRoot "apps\desktop"
$distDir = Join-Path $repoRoot "dist"
New-Item -ItemType Directory -Force -Path $distDir | Out-Null

if ($env:OS -ne "Windows_NT") {
    throw "The verified NSIS path must run on Windows."
}

if (-not $SkipSidecar) {
    & (Join-Path $PSScriptRoot "build-sidecar.ps1") -Profile $SidecarProfile
}

if (-not $SkipWebPrepare) {
    & (Join-Path $PSScriptRoot "prepare-desktop-web.ps1")
}

Push-Location $desktopDir
try {
    if (-not $SkipNpmInstall) {
        if (Test-Path -LiteralPath "package-lock.json") {
            npm ci
        } else {
            npm install
        }
        if ($LASTEXITCODE -ne 0) { throw "npm dependency installation failed." }
    }

    npm run tauri -- build --bundles nsis
    if ($LASTEXITCODE -ne 0) { throw "Tauri NSIS build failed." }
} finally {
    Pop-Location
}

$bundleDir = Join-Path $desktopDir "src-tauri\target\release\bundle\nsis"
$installers = @(Get-ChildItem -LiteralPath $bundleDir -Filter "*.exe" -File -ErrorAction SilentlyContinue)
if ($installers.Count -eq 0) {
    throw "No NSIS installer was found under $bundleDir"
}

# `target/release/*.exe` depends on adjacent Tauri resources and is not a
# portable single file. The canonical dist/LaborCaseAgent.exe is therefore the
# self-contained NSIS installer, not a misleading copy of the raw Rust binary.
$portableDestination = Join-Path $distDir "LaborCaseAgent.exe"
Copy-Item -Force -LiteralPath $installers[0].FullName -Destination $portableDestination
$record = [pscustomobject]@{
    artifact = $portableDestination
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $portableDestination).Hash.ToLowerInvariant()
    size_bytes = (Get-Item -LiteralPath $portableDestination).Length
    signed = $false
}
$record | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $distDir "desktop-build-manifest.json")
$record | Format-Table -AutoSize
Write-Host "Canonical NSIS installer: $portableDestination"

if ($CommercialRelease) {
    if ([string]::IsNullOrWhiteSpace($CertificateThumbprint)) {
        throw "Commercial release requires SIGNING_CERT_THUMBPRINT or -CertificateThumbprint."
    }
    & (Join-Path $PSScriptRoot "generate-sbom.ps1")
    & (Join-Path $PSScriptRoot "sign-release.ps1") `
        -CertificateThumbprint $CertificateThumbprint -Artifacts @($portableDestination)
    & (Join-Path $PSScriptRoot "assert-commercial-release.ps1")
}
