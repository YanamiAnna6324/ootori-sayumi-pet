[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$installerPath = Join-Path $projectRoot 'install-pet.ps1'
$atlasPath = Join-Path $projectRoot 'outputs\ootori_sayumi_pet\spritesheet-extended.webp'
$testRoot = Join-Path $projectRoot ('work\installer-test-' + [Guid]::NewGuid().ToString('N'))
$utf8 = New-Object System.Text.UTF8Encoding($false)
$checks = 0

function Assert-True([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw "FAIL: $Message" }
  $script:checks++
}

function Write-Json([string]$Path, $Value) {
  [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 32), $script:utf8)
}

function New-Fixture([string]$Name) {
  $fixtureRoot = Join-Path $script:testRoot $Name
  $source = Join-Path $fixtureRoot 'outputs\ootori_sayumi_pet'
  New-Item -ItemType Directory -Path $source -Force | Out-Null
  Copy-Item -LiteralPath $script:installerPath -Destination (Join-Path $fixtureRoot 'install-pet.ps1')
  Copy-Item -LiteralPath $script:atlasPath -Destination (Join-Path $source 'custom-atlas.webp')
  $manifest = [ordered]@{
    id = 'ootori-sayumi-pet'
    displayName = ('Ootori ' + [char]0x5C0F + [char]0x591C + ' test')
    description = 'This value must come from the source manifest.'
    spriteVersionNumber = 2
    spritesheetPath = 'custom-atlas.webp'
  }
  Write-Json (Join-Path $source 'pet.json') $manifest
  return [pscustomobject]@{
    Root = $fixtureRoot
    Source = $source
    Installer = Join-Path $fixtureRoot 'install-pet.ps1'
    Destination = Join-Path $fixtureRoot 'installed'
    Manifest = $manifest
  }
}

function Invoke-ExpectedFailure($Fixture, [string]$MessagePattern, [switch]$RequireRelease) {
  $failure = $null
  try { & $Fixture.Installer -Destination $Fixture.Destination -RequireRelease:$RequireRelease | Out-Null }
  catch { $failure = $_.Exception.Message }
  Assert-True ($null -ne $failure -and $failure -match $MessagePattern) "Expected rejection matching: $MessagePattern; got: $failure"
}

$tokens = $null
$parseErrors = $null
[Management.Automation.Language.Parser]::ParseFile($installerPath, [ref]$tokens, [ref]$parseErrors) | Out-Null
Assert-True ($parseErrors.Count -eq 0) 'Installer parses without PowerShell errors.'

# All installs run against copied fixtures; the actual .codex/pets directory is untouched.
$ok = New-Fixture 'valid-package'
& $ok.Installer -Destination $ok.Destination | Out-Null
$installedManifestPath = Join-Path $ok.Destination 'pet.json'
$installedManifest = Get-Content -LiteralPath $installedManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
Assert-True ($installedManifest.displayName -ceq $ok.Manifest.displayName) 'Unicode display name survives installation.'
Assert-True ($installedManifest.description -ceq $ok.Manifest.description) 'Installer reads metadata from the source manifest.'
Assert-True ($installedManifest.id -ceq $ok.Manifest.id -and $installedManifest.spriteVersionNumber -eq 2) 'Installed identity and v2 version match the source.'
Assert-True ($installedManifest.spritesheetPath -ceq 'spritesheet.webp') 'Installed manifest points at the installed atlas.'
$sourceHash = (Get-FileHash -LiteralPath (Join-Path $ok.Source 'custom-atlas.webp') -Algorithm SHA256).Hash
$installedHash = (Get-FileHash -LiteralPath (Join-Path $ok.Destination 'spritesheet.webp') -Algorithm SHA256).Hash
Assert-True ($sourceHash -ceq $installedHash) 'Installed WebP hash matches the source.'
$jsonBytes = [IO.File]::ReadAllBytes($installedManifestPath)
$hasBom = $jsonBytes.Length -ge 3 -and $jsonBytes[0] -eq 239 -and $jsonBytes[1] -eq 187 -and $jsonBytes[2] -eq 191
Assert-True (-not $hasBom) 'Installed manifest is UTF-8 without BOM.'

# A rejected release must preserve an existing installation byte for byte.
Write-Json (Join-Path $ok.Source 'release-status.json') @{ installable = $false }
$manifestHash = (Get-FileHash -LiteralPath $installedManifestPath -Algorithm SHA256).Hash
Invoke-ExpectedFailure $ok 'installable=false' -RequireRelease
Assert-True ((Get-FileHash -LiteralPath $installedManifestPath -Algorithm SHA256).Hash -ceq $manifestHash) 'Blocked release preserves the installed manifest.'
Assert-True ((Get-FileHash -LiteralPath (Join-Path $ok.Destination 'spritesheet.webp') -Algorithm SHA256).Hash -ceq $installedHash) 'Blocked release preserves the installed WebP.'

# The user's original no-switch command permits a clearly marked preview draft.
$draftAtlas = Join-Path $ok.Source 'draft.webp'
Copy-Item -LiteralPath (Join-Path $ok.Source 'custom-atlas.webp') -Destination $draftAtlas
Write-Json (Join-Path $ok.Source 'release-status.json') @{ installable = $false; draftSpritesheetPath = 'draft.webp' }
$ok.Manifest.spritesheetPath = 'not-used-for-draft.webp'
Write-Json (Join-Path $ok.Source 'pet.json') $ok.Manifest
$warnings = @()
& $ok.Installer -Destination $ok.Destination -WarningVariable warnings -WarningAction SilentlyContinue | Out-Null
$draftManifest = Get-Content -LiteralPath $installedManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
Assert-True ($warnings.Count -gt 0) 'Draft install reports unfinished animation.'
Assert-True ($draftManifest.description -match 'Preview draft') 'Installed draft manifest is clearly marked.'
Assert-True ((Get-FileHash -LiteralPath (Join-Path $ok.Destination 'spritesheet.webp')).Hash -ceq (Get-FileHash -LiteralPath $draftAtlas).Hash) 'Draft path from release status is installed.'
$backupDirectories = @(Get-ChildItem -LiteralPath (Join-Path $ok.Destination 'backups') -Directory)
Assert-True ($backupDirectories.Count -eq 1) 'Previous installation gets one backup directory.'
Assert-True ((Get-FileHash -LiteralPath (Join-Path $backupDirectories[0].FullName 'pet.json')).Hash -ceq $manifestHash) 'Backup preserves previous manifest bytes.'
Assert-True ((Get-FileHash -LiteralPath (Join-Path $backupDirectories[0].FullName 'spritesheet.webp')).Hash -ceq $installedHash) 'Backup preserves previous spritesheet bytes.'

$draftEscape = New-Fixture 'draft-path-escape'
Write-Json (Join-Path $draftEscape.Source 'release-status.json') @{ installable = $false; draftSpritesheetPath = '..\outside.webp' }
Invoke-ExpectedFailure $draftEscape 'stay inside'
Assert-True (-not (Test-Path -LiteralPath $draftEscape.Destination)) 'Draft paths use the same package path checks.'

$missingAtlas = New-Fixture 'missing-atlas'
$missingAtlas.Manifest.spritesheetPath = 'missing.webp'
Write-Json (Join-Path $missingAtlas.Source 'pet.json') $missingAtlas.Manifest
Invoke-ExpectedFailure $missingAtlas 'spritesheet does not exist'
Assert-True (-not (Test-Path -LiteralPath $missingAtlas.Destination)) 'Missing atlas creates no destination.'

$invalidManifest = New-Fixture 'invalid-manifest'
$invalidManifest.Manifest.displayName = ''
Write-Json (Join-Path $invalidManifest.Source 'pet.json') $invalidManifest.Manifest
Invoke-ExpectedFailure $invalidManifest 'non-empty string: displayName'
Assert-True (-not (Test-Path -LiteralPath $invalidManifest.Destination)) 'Invalid manifest creates no destination.'

$unsafePath = New-Fixture 'unsafe-path'
$unsafePath.Manifest.spritesheetPath = '..\outside.webp'
Write-Json (Join-Path $unsafePath.Source 'pet.json') $unsafePath.Manifest
Invoke-ExpectedFailure $unsafePath 'stay inside'
Assert-True (-not (Test-Path -LiteralPath $unsafePath.Destination)) 'Escaping atlas path creates no destination.'

$missingSourceRoot = Join-Path $testRoot 'missing-source'
New-Item -ItemType Directory -Path $missingSourceRoot | Out-Null
Copy-Item -LiteralPath $installerPath -Destination (Join-Path $missingSourceRoot 'install-pet.ps1')
$missingSource = [pscustomobject]@{
  Installer = Join-Path $missingSourceRoot 'install-pet.ps1'
  Destination = Join-Path $missingSourceRoot 'installed'
}
Invoke-ExpectedFailure $missingSource 'source directory does not exist'
Assert-True (-not (Test-Path -LiteralPath $missingSource.Destination)) 'Missing source creates no destination.'

Write-Host "PASS: $checks installer checks. Debug fixtures retained at $testRoot"
