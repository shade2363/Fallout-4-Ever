# Pack the loose converted assets into BA2 archives, staged in tool\output\ba2-stage\ (nothing is installed or deleted; the loose sources stay).
#   powershell -ExecutionPolicy Bypass -File packaging\pack_ba2.ps1                 # build every archive that is out of date, verify it
#   powershell -ExecutionPolicy Bypass -File packaging\pack_ba2.ps1 -DryRun         # show the plan only
#   powershell -ExecutionPolicy Bypass -File packaging\pack_ba2.ps1 -Only items-textures -Force
# Archives are named after the plugin that owns the content ("<Plugin> - Main.ba2"): Fallout 4 mounts every "<plugin name>*.ba2" in Data for an active plugin
# (the string table of Fallout4.exe has the "%s*.ba2" pattern), so install-output.ps1 only has to copy them next to the plugins.
# Written to tool\output\ba2-stage\: the .ba2 files, stage.json (what each archive holds + a signature of its sources; install-output.ps1 uses it to refuse stale archives)
# and logs. Archives that are rebuilt replace the old file; the old one is kept once as <name>.pre-pkg.
#
# What is NOT packed (stays loose on purpose):
#   * tool\output\loose\meshes\new_vegas - the keyframed door / terminal / gate / animated-activator nifs that must OVERRIDE the converted meshes inside Fallout3 - Main.ba2
#     and the DLC archives (loose files win over archives; 250 of them replace a Fallout3 - Main entry, 91 a DLC entry),
#   * audio (audio\pack_audio.ps1 owns the voice / radio / music archives; Sound\fo3 stays loose by default), scripts, videos, F4SE, LODSettings.
# Fix applied while staging textures: Archive2 silently skips DDS files it does not accept. All our normal / specular maps (BC5, DX10 header with typeless format
# and arraySize 0) were skipped, so packaging\stage_dds.py writes header-corrected copies (pixel data untouched, checked) into ba2-stage\_work and the archive is built from those.
[CmdletBinding()]
param(
  [string[]]$Only,                  # keys (actors-main, actors-facetint, items-main, items-textures) or archive names; default = all
  [switch]$Force,                   # rebuild even when the stage.json signature says the archive is up to date
  [switch]$NoVerify,                # skip the Archive2 -extract round trip (the file-list / size / DDS header verification always runs)
  [switch]$DryRun,                  # print the plan, build nothing
  [int]$RoundtripSample = 0,        # 0 = compare every file in the round trip, N = N evenly spread files
  [switch]$KeepWork,                # keep ba2-stage\_work (the header-corrected DDS copies)
  [string]$LooseDir,
  [string]$StageDir,
  [string]$Archive2
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'common.ps1')
if (-not $LooseDir) { $LooseDir = Join-Path $root 'tool\output\loose' }
if (-not $StageDir) { $StageDir = Join-Path $root 'tool\output\ba2-stage' }
$Only = @($Only | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$tool = Join-Path $PSScriptRoot 'ba2_tool.py'
$stageDds = Join-Path $PSScriptRoot 'stage_dds.py'

# One row per archive. Sources are folders below $LooseDir; the archive keeps those paths (meshes\..., textures\...).
#   Default = install-output.ps1 uses the archive instead of the loose copy unless it is a risky one (-FaceTintArchive switch there).
$Groups = @(
  @{ Key = 'actors-main'; Name = 'CapitalActors - Main.ba2'; Plugin = 'CapitalActors.esp'; Format = 'General'; Dds = $false; Default = $true
     Sources = @('meshes\FO3Faces', 'meshes\Actors')
     Note = 'per-NPC head part meshes (meshes\FO3Faces, 6,306 nifs) + CK FaceGen geometry (meshes\Actors\Character\FaceGenData\FaceGeom\CapitalActors.esp)' },
  @{ Key = 'actors-facetint'; Name = 'CapitalActors - FaceTint.ba2'; Plugin = 'CapitalActors.esp'; Format = 'General'; Dds = $false; Default = $false
     Sources = @('textures\Actors')
     Note = 'CK FaceGen tint textures: 1,056 uncompressed 1024x1024 TGA (3.1 GB loose). Not installed by default: whether the engine reads .tga out of an archive is unverified' },
  @{ Key = 'items-main'; Name = 'CapitalItems - Main.ba2'; Plugin = 'CapitalItems.esp'; Format = 'General'; Dds = $false; Default = $true
     Sources = @('meshes\Capital', 'materials\Capital')
     Note = 'own-model outfits / hats / guns (meshes\Capital) and their BGSM materials' },
  @{ Key = 'items-textures'; Name = 'CapitalItems - Textures.ba2'; Plugin = 'CapitalItems.esp'; Format = 'DDS'; Dds = $true; Default = $true
     Sources = @('textures\Capital')
     Note = 'outfit / hat / gun textures (471 DDS, 1.7 GB loose)' }
)

function Step([string]$m) { Write-Host ("[{0}] {1}" -f (Get-Date -Format HH:mm:ss), $m) -ForegroundColor Cyan }
function Pick($g) { if (-not $Only) { return $true }; return ($Only -contains $g.Key) -or ($Only -contains $g.Name) -or ($Only -contains ($g.Name -replace '\.ba2$', '')) }
$sel = @($Groups | Where-Object { Pick $_ })
if (-not $sel) { throw "Nothing selected. Known keys: $(($Groups | ForEach-Object { $_.Key }) -join ', ')" }
if (-not (Test-Path $LooseDir)) { throw "Loose folder not found: $LooseDir" }
$LooseDir = (Resolve-Path $LooseDir).Path.TrimEnd('\')
$a2 = $null
if (-not $DryRun) { $a2 = Get-Archive2Path $Archive2; New-Item -ItemType Directory -Force $StageDir | Out-Null; $StageDir = (Resolve-Path $StageDir).Path }
$stageJson = Join-Path $StageDir 'stage.json'
$info = Read-StageInfo $StageDir
$entries = @{}
if ($info -and $info.archives) { foreach ($e in $info.archives) { $entries[$e.name] = $e } }

function Save-Stage {
  $arr = @($entries.Values | Sort-Object name)
  $obj = [ordered]@{ version = 1; written = (Get-Date).ToString('s'); archive2 = $a2; looseDir = $LooseDir; archives = $arr }
  ($obj | ConvertTo-Json -Depth 6) | Set-Content $stageJson -Encoding UTF8
}

$rows = @()
foreach ($g in $sel) {
  $sigNow = Get-SourceSig $LooseDir $g.Sources
  $dst = Join-Path $StageDir $g.Name
  $prev = $entries[$g.Name]
  $fresh = $prev -and ($prev.sig -eq $sigNow.Sig) -and $prev.verified -and (Test-Path $dst) -and ((Get-Item $dst).Length -eq $prev.archiveBytes)
  if ($sigNow.Files -eq 0) { Write-Warning "$($g.Name): no source files under $($g.Sources -join ', ') - skipped"; continue }
  if ($fresh -and -not $Force) {
    Step "$($g.Name): up to date ($($sigNow.Files) files, $(Format-Size (Get-Item $dst).Length))"
    $rows += [pscustomobject]@{ Archive = $g.Name; Files = $sigNow.Files; Loose = Format-Size $sigNow.Bytes; Packed = Format-Size (Get-Item $dst).Length; Result = 'up to date' }
    continue
  }
  if ($DryRun) {
    Step "$($g.Name): WOULD build [$($g.Format)] from $($g.Sources -join ', ') - $($sigNow.Files) files, $(Format-Size $sigNow.Bytes) loose$(if ($prev) { ' (stale or forced)' })"
    $rows += [pscustomobject]@{ Archive = $g.Name; Files = $sigNow.Files; Loose = Format-Size $sigNow.Bytes; Packed = '-'; Result = 'would build' }
    continue
  }

  Step "$($g.Name): building from $($g.Sources -join ', ') ($($sigNow.Files) files, $(Format-Size $sigNow.Bytes))"
  $log = Join-Path $StageDir ($g.Name -replace '\.ba2$', '.log')
  $buildDir = Join-Path $StageDir '_building'
  New-Item -ItemType Directory -Force $buildDir | Out-Null
  $tmp = Join-Path $buildDir $g.Name
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue

  # archive root + folders to add
  $archRoot = $LooseDir
  $folders = @($g.Sources | ForEach-Object { Join-Path $LooseDir $_ } | Where-Object { Test-Path $_ })
  $verifyDirs = $folders
  $work = $null
  if ($g.Dds) {
    $work = Join-Path $StageDir ('_work\' + $g.Key)
    if (Test-Path $work) { Remove-Item $work -Recurse -Force }
    New-Item -ItemType Directory -Force $work | Out-Null
    foreach ($s in $g.Sources) {
      Step "  header-correcting DDS copies of $s"
      & python -I $stageDds (Join-Path $LooseDir $s) (Join-Path $work $s)
      if ($LASTEXITCODE -ne 0) { throw "stage_dds.py failed for $s" }
      & python -I $stageDds --check (Join-Path $LooseDir $s) (Join-Path $work $s)
      if ($LASTEXITCODE -ne 0) { throw "staged DDS pixel data differs from the loose source for $s" }
    }
    $archRoot = $work
    $folders = @($g.Sources | ForEach-Object { Join-Path $work $_ })
    $verifyDirs = $folders
  }

  $fmt = $g.Format
  $argList = @(($folders -join ','), "-create=$tmp", "-format=$fmt", "-root=$archRoot", '-compression=Default', '-tempFiles', '-quiet')
  $t0 = Get-Date
  $o = & $a2 @argList 2>&1 | Out-String
  Set-Content $log $o -Encoding UTF8
  $skipped = @($o -split "`r?`n" | Where-Object { $_ -match '^Skipping ' })
  Step ("  Archive2 finished in {0:N0} s, exit {1}; {2} skipped file(s); log {3}" -f ((Get-Date) - $t0).TotalSeconds, $LASTEXITCODE, $skipped.Count, $log)
  if ($skipped.Count) { $skipped | Select-Object -First 5 | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }; throw "$($g.Name): Archive2 skipped $($skipped.Count) file(s) (see $log); not publishing a partial archive" }
  if (-not (Test-Path $tmp) -or (Get-Item $tmp).Length -lt 1024) { throw "$($g.Name): Archive2 produced no archive (see $log)" }

  Step '  verifying file list / sizes / DDS headers against the source'
  & python -I $tool verify $tmp --root $archRoot --sizes @verifyDirs
  if ($LASTEXITCODE -ne 0) { throw "$($g.Name): archive does not match its source" }
  if (-not $NoVerify) {
    Step '  Archive2 -extract round trip (byte compare)'
    $rtArgs = @('roundtrip', $tmp, '--root', $archRoot, '--archive2', $a2)
    if ($RoundtripSample -gt 0) { $rtArgs += @('--sample', $RoundtripSample) }
    & python -I $tool @rtArgs @verifyDirs
    if ($LASTEXITCODE -ne 0) { throw "$($g.Name): round trip failed" }
  }

  # publish: keep the previous archive once as .pre-pkg
  if (Test-Path $dst) { $bak = "$dst.pre-pkg"; if (-not (Test-Path $bak)) { Move-Item $dst $bak } else { Remove-Item $dst -Force } }
  Move-Item $tmp $dst
  $summary = (& python -I $tool json $dst) | ConvertFrom-Json
  $entries[$g.Name] = [pscustomobject]@{
    name = $g.Name; key = $g.Key; plugin = $g.Plugin; format = $g.Format; sources = $g.Sources; defaultInstall = $g.Default; note = $g.Note
    files = $summary.files; archiveBytes = (Get-Item $dst).Length; unpackedBytes = $summary.unpacked
    sourceFiles = $sigNow.Files; sourceBytes = $sigNow.Bytes; sig = $sigNow.Sig; built = (Get-Date).ToString('s'); verified = $true
    roundtrip = [bool](-not $NoVerify)
  }
  Save-Stage
  $rows += [pscustomobject]@{ Archive = $g.Name; Files = $summary.files; Loose = Format-Size $sigNow.Bytes; Packed = Format-Size (Get-Item $dst).Length; Result = 'built + verified' }
  if ($work -and -not $KeepWork) { Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue }
}
if (-not $DryRun) {
  Save-Stage
  Remove-Item (Join-Path $StageDir '_building') -Recurse -Force -ErrorAction SilentlyContinue
  if (-not $KeepWork) { Remove-Item (Join-Path $StageDir '_work') -Recurse -Force -ErrorAction SilentlyContinue }
}
Write-Host ''
$rows | Format-Table -AutoSize
if (-not $DryRun) { "Staged in $StageDir (stage.json written). Install with: powershell -File install-output.ps1" }
