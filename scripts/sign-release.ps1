[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CertificateThumbprint,
    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [string[]]$Artifacts = @("dist\LaborCaseAgent.exe")
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if (-not $signtool) {
    $kitRoot = "${env:ProgramFiles(x86)}\Windows Kits\10\bin"
    $candidate = Get-ChildItem -LiteralPath $kitRoot -Filter signtool.exe -Recurse -File `
        -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $candidate) { throw "signtool.exe was not found. Install the Windows SDK." }
    $signtoolPath = $candidate.FullName
} else {
    $signtoolPath = $signtool.Source
}

$resolved = foreach ($artifact in $Artifacts) {
    $path = if ([IO.Path]::IsPathRooted($artifact)) { $artifact } else { Join-Path $repoRoot $artifact }
    (Resolve-Path -LiteralPath $path -ErrorAction Stop).Path
}
foreach ($path in $resolved) {
    & $signtoolPath sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $path
    if ($LASTEXITCODE -ne 0) { throw "Signing failed: $path" }
    & $signtoolPath verify /pa /all /v $path
    if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $path" }
}

$manifestPath = Join-Path $repoRoot "dist\desktop-build-manifest.json"
if (Test-Path -LiteralPath $manifestPath) {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $primaryArtifact = $resolved[0]
    $manifest.artifact = $primaryArtifact
    $manifest.sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $primaryArtifact).Hash.ToLowerInvariant()
    $manifest.size_bytes = (Get-Item -LiteralPath $primaryArtifact).Length
    $manifest.signed = $true
    $manifest | Add-Member -NotePropertyName signature_verified_at `
        -NotePropertyValue ([DateTimeOffset]::UtcNow.ToString("O")) -Force
    $manifest | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath $manifestPath
}
Write-Host "Authenticode signing and verification completed for $($resolved.Count) artifact(s)."
