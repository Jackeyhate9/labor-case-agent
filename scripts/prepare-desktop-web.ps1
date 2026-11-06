[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [string]$NodePath = "C:\Program Files\nodejs\node.exe"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$webDir = Join-Path $repoRoot "apps\web"
$resourceRoot = Join-Path $repoRoot "apps\desktop\src-tauri\resources"
$webResource = Join-Path $resourceRoot "web"
$nodeResource = Join-Path $resourceRoot "node\node.exe"

if (-not $SkipBuild) {
    Push-Location $webDir
    try {
        $previousApiUrl = $env:NEXT_PUBLIC_API_URL
        $env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:17831"
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Next.js standalone build failed." }
    } finally {
        if ($null -eq $previousApiUrl) {
            Remove-Item Env:NEXT_PUBLIC_API_URL -ErrorAction SilentlyContinue
        } else {
            $env:NEXT_PUBLIC_API_URL = $previousApiUrl
        }
        Pop-Location
    }
}

$standalone = Join-Path $webDir ".next\standalone"
$static = Join-Path $webDir ".next\static"
if (-not (Test-Path -LiteralPath (Join-Path $standalone "server.js") -PathType Leaf)) {
    throw "Next.js standalone server.js was not produced."
}
if (-not (Test-Path -LiteralPath $NodePath -PathType Leaf)) {
    throw "Node runtime not found: $NodePath"
}

if (Test-Path -LiteralPath $webResource) {
    $resolvedResource = (Resolve-Path -LiteralPath $webResource).Path
    $resolvedDesktop = (Resolve-Path -LiteralPath (Join-Path $repoRoot "apps\desktop")).Path
    if (-not $resolvedResource.StartsWith($resolvedDesktop, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to replace a resource directory outside apps/desktop."
    }
    Remove-Item -Recurse -Force -LiteralPath $webResource
}
New-Item -ItemType Directory -Force -Path $webResource, (Split-Path $nodeResource -Parent) | Out-Null
Copy-Item -Recurse -Force -Path (Join-Path $standalone "*") -Destination $webResource
New-Item -ItemType Directory -Force -Path (Join-Path $webResource ".next\static") | Out-Null
Copy-Item -Recurse -Force -Path (Join-Path $static "*") -Destination (Join-Path $webResource ".next\static")
if (Test-Path -LiteralPath (Join-Path $webDir "public")) {
    Copy-Item -Recurse -Force -LiteralPath (Join-Path $webDir "public") -Destination (Join-Path $webResource "public")
}
Copy-Item -Force -LiteralPath $NodePath -Destination $nodeResource

Write-Host "Next standalone resource: $webResource"
Write-Host "Node runtime resource: $nodeResource"
