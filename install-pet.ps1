[CmdletBinding()]
param(
  [Parameter()]
  [ValidateNotNullOrEmpty()]
  [string]$Destination = (Join-Path $env:USERPROFILE '.codex\pets\ootori-sayumi-pet')
)

$ErrorActionPreference = 'Stop'
$sourceDirectory = Join-Path $PSScriptRoot 'outputs\ootori_sayumi_pet'
if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) {
  throw "Pet source directory does not exist: $sourceDirectory"
}

$manifestPath = Join-Path $sourceDirectory 'pet.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
  throw "Pet manifest does not exist: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($field in @('id', 'displayName', 'description', 'spritesheetPath')) {
  if ($manifest.$field -isnot [string] -or [string]::IsNullOrWhiteSpace($manifest.$field)) {
    throw "Pet manifest requires a non-empty string: $field"
  }
}
if ($manifest.spriteVersionNumber -ne 2) {
  throw 'Pet manifest must declare spriteVersionNumber: 2.'
}

# Only copy a WebP inside this package, even if a manifest is edited by hand.
if ([IO.Path]::IsPathRooted($manifest.spritesheetPath)) {
  throw 'spritesheetPath must be relative to the pet source directory.'
}
$sourcePrefix = [IO.Path]::GetFullPath($sourceDirectory) + [IO.Path]::DirectorySeparatorChar
$sourceAtlas = [IO.Path]::GetFullPath((Join-Path $sourceDirectory $manifest.spritesheetPath))
if (-not $sourceAtlas.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
  throw 'spritesheetPath must stay inside the pet source directory.'
}
if ([IO.Path]::GetExtension($sourceAtlas) -ine '.webp') {
  throw 'The installer requires a WebP spritesheet.'
}
if (-not (Test-Path -LiteralPath $sourceAtlas -PathType Leaf)) {
  throw "Pet spritesheet does not exist: $sourceAtlas"
}

$releaseStatusPath = Join-Path $sourceDirectory 'release-status.json'
if (Test-Path -LiteralPath $releaseStatusPath) {
  $releaseStatus = Get-Content -LiteralPath $releaseStatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($releaseStatus.installable -is [bool] -and -not $releaseStatus.installable) {
    throw 'Installation blocked: release-status.json marks this pet as installable=false.'
  }
}

# Finish preflight before touching a previously installed pet.
$manifest.spritesheetPath = 'spritesheet.webp'
$installedJson = ($manifest | ConvertTo-Json -Depth 32) + [Environment]::NewLine
$destinationDirectory = [IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
$installedAtlas = Join-Path $destinationDirectory 'spritesheet.webp'
Copy-Item -LiteralPath $sourceAtlas -Destination $installedAtlas -Force
[IO.File]::WriteAllText(
  (Join-Path $destinationDirectory 'pet.json'),
  $installedJson,
  (New-Object System.Text.UTF8Encoding($false))
)

Write-Host "Installed $($manifest.displayName) to $destinationDirectory"
Get-ChildItem -LiteralPath $destinationDirectory
