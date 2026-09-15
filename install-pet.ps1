$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'outputs\ootori_sayumi_pet'
$dst = Join-Path $env:USERPROFILE '.codex\pets\ootori-sayumi-pet'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item (Join-Path $src 'spritesheet-extended.webp') (Join-Path $dst 'spritesheet.webp') -Force
@'{
  "id": "ootori-sayumi-pet",
  "displayName": "Ootori Sayumi pet",
  "description": "A gentle chibi twin-tail companion with blue eyes, soft encouragement, and playful snack breaks.",
  "spriteVersionNumber": 2,
  "spritesheetPath": "spritesheet.webp"
}
'@ | Set-Content -Encoding UTF8 (Join-Path $dst 'pet.json')
Write-Host "Installed Ootori Sayumi pet to $dst"
Get-ChildItem $dst
