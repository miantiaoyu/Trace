[CmdletBinding()]
param()

function ConvertFrom-Utf8Base64([string]$value) {
    [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($value))
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distRoot = Join-Path $repoRoot "dist"
$bundleRoot = Join-Path $distRoot "trace-server"
$zipPath = Join-Path $distRoot "trace-server.zip"
$expectedPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar

foreach ($path in @($distRoot, $bundleRoot, $zipPath)) {
    $fullPath = [IO.Path]::GetFullPath($path)
    if (-not $fullPath.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        $message = ConvertFrom-Utf8Base64 "5ouS57ud5pON5L2c5LuT5bqT5LmL5aSW55qE6Lev5b6EOiA="
        throw "$message$fullPath"
    }
}

if (Test-Path -LiteralPath $bundleRoot) {
    Remove-Item -LiteralPath $bundleRoot -Recurse -Force
}
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
New-Item -ItemType Directory -Path $bundleRoot -Force | Out-Null

$files = @(
    ".dockerignore",
    "docker-compose.yml",
    "Dockerfile",
    "requirements.txt",
    "deploy\run-trace.sh",
    "deploy\install-systemd.sh"
)
$directories = @(
    "trace_api_probe",
    "deploy\systemd"
)

foreach ($relativePath in $files) {
    $destination = Join-Path $bundleRoot $relativePath
    New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $repoRoot $relativePath) -Destination $destination
}

foreach ($relativePath in $directories) {
    $destination = Join-Path $bundleRoot $relativePath
    New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $repoRoot $relativePath) -Destination $destination -Recurse
}

Get-ChildItem -LiteralPath $bundleRoot -Directory -Recurse -Force |
    Where-Object Name -EQ "__pycache__" |
    Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $bundleRoot -File -Recurse -Filter "*.pyc" |
    Remove-Item -Force

Copy-Item -LiteralPath (Join-Path $repoRoot "deploy\SERVER_README.md") -Destination (Join-Path $bundleRoot "README.md")
Compress-Archive -Path (Join-Path $bundleRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal

$createdMessage = ConvertFrom-Utf8Base64 "5pyN5Yqh5Zmo5Y+R5biD5YyF5bey55Sf5oiQOiA="
$configMessage = ConvertFrom-Utf8Base64 "5Y+R5biD5YyF5LiN5YyF5ZCrIHByb2QtZGIueW1sIOWSjCB0ZXN0LWRiLnltbO+8m+ivt+WcqOacjeWKoeWZqOS4iuWNleeLrOaPkOS+m+OAgg=="
Write-Host "$createdMessage$zipPath"
Write-Host $configMessage
