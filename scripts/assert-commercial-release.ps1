[CmdletBinding()]
param(
    [string]$Manifest = "dist\desktop-build-manifest.json"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$failures = @()
if ([string]::IsNullOrWhiteSpace($env:PUBLISHER_NAME)) { $failures += "PUBLISHER_NAME is missing" }
if ([string]::IsNullOrWhiteSpace($env:SUPPORT_EMAIL) -or $env:SUPPORT_EMAIL -notmatch "^[^@\s]+@[^@\s]+\.[^@\s]+$") {
    $failures += "SUPPORT_EMAIL is missing or invalid"
}
$manifestPath = Join-Path $repoRoot $Manifest
if (-not (Test-Path -LiteralPath $manifestPath)) {
    $failures += "desktop build manifest is missing"
} else {
    $record = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if (-not $record.signed) { $failures += "desktop installer is not signature-verified" }
    if (-not (Test-Path -LiteralPath $record.artifact)) {
        $failures += "desktop installer is missing"
    } else {
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $record.artifact).Hash.ToLowerInvariant()
        if ($actualHash -ne $record.sha256) { $failures += "desktop installer hash does not match manifest" }
        if ((Get-AuthenticodeSignature -LiteralPath $record.artifact).Status -ne "Valid") {
            $failures += "desktop installer Authenticode signature is not valid"
        }
    }
}
foreach ($name in @("terms", "privacy", "ai-notice")) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "apps\web\app\legal\$name\page.tsx"))) {
        $failures += "legal page is missing: $name"
    }
}
if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ -ErrorAction Continue }
    throw "Commercial release gate failed with $($failures.Count) issue(s)."
}
Write-Host "Commercial release gate passed."
