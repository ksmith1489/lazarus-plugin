param(
    [string] $OutputRoot = "release"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath ".").Path
$outputRootPath = Join-Path $repoRoot $OutputRoot
$packageName = "lazarus-plugin-2.0.3"
$packageDir = Join-Path $outputRootPath $packageName
$zipPath = Join-Path $outputRootPath "OctoPrint-3DPrintSaver.com-2.0.3.zip"

New-Item -ItemType Directory -Force -Path $outputRootPath | Out-Null
$resolvedOutput = (Resolve-Path -LiteralPath $outputRootPath).Path
if (-not $packageDir.StartsWith($resolvedOutput, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to replace a package directory outside the release output root."
}
if (Test-Path -LiteralPath $packageDir) {
    Remove-Item -LiteralPath $packageDir -Recurse -Force
}
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Force -Path $packageDir | Out-Null
foreach ($file in @("babel.cfg", "LICENSE.txt", "MANIFEST.in", "PRIVACY.md", "pyproject.toml", "README.md", "requirements.txt", "Taskfile.yml", "TERMS.md")) {
    Copy-Item -LiteralPath (Join-Path $repoRoot $file) -Destination $packageDir -Force
}
Copy-Item -LiteralPath (Join-Path $repoRoot "octoprint_lazarus") -Destination $packageDir -Recurse -Force

Get-ChildItem -LiteralPath $packageDir -Directory -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $packageDir -File -Recurse |
    Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
    Remove-Item -Force
Compress-Archive -LiteralPath $packageDir -DestinationPath $zipPath -CompressionLevel Optimal
Write-Host "Built $zipPath"
