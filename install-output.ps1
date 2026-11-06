# Step 3: install converted output into Fallout 4\Data and activate it.
#   powershell -ExecutionPolicy Bypass -File .\install-output.ps1                 # install (staged BA2s where fresh, the rest loose)
#   powershell -ExecutionPolicy Bypass -File .\install-output.ps1 -Loose          # the old behaviour: no staged BA2s, textures / faces / materials loose
#   powershell -ExecutionPolicy Bypass -File .\install-output.ps1 -DryRun         # print everything that would be copied / backed up / removed; writes nothing
#   powershell -ExecutionPolicy Bypass -File .\install-output.ps1 -Uninstall      # remove exactly what was installed, restore backed-up originals (add -DryRun to preview)
# Never silently overwrites: a file in Data that did not come from us and differs is first copied to backup\Data-<timestamp>\ (with the same relative path).
# installed-files.txt lists EVERY file placed in Data (plugins, archives, loose meshes / textures / materials / sound / music / scripts / video / F4SE / LODSettings); -Uninstall removes those.
#
# Archives: packaging\pack_ba2.ps1 stages CapitalActors - Main.ba2, CapitalItems - Main.ba2, CapitalItems - Textures.ba2 (+ CapitalActors - FaceTint.ba2) in tool\output\ba2-stage\.
# An archive is used only when it is fresh (stage.json signature = the loose sources it was built from, or the sources are gone); then its loose twin is NOT installed and
# the loose copy of an earlier install is removed from Data (a loose file would shadow the archive). tool\output\loose\meshes\new_vegas (the keyframed door / terminal / gate nifs)
# is ALWAYS installed loose: loose files override the converted meshes inside Fallout3 - Main.ba2 and the DLC archives, which is the point of those fixes.
# Audio keeps its previous behaviour: the top-level tool\output\*.ba2 (CapitalDialogue / CapitalRadio / Fallout3 - Sounds from audio\pack_audio.ps1) are installed, and the loose
# Sound\Voice and Music copies are skipped when CapitalDialogue - Main.ba2 exists; Sound\fo3 (3,138 SFX wavs) stays loose unless pack_audio.ps1 -All packed it.
#
# Test without touching a game: -Sandbox <dir> redirects Data, plugins.txt, the ini files, backups and installed-files.txt into <dir>; -OutDir points at another tool\output.
[CmdletBinding()]
param(
  [switch]$Uninstall,
  [switch]$IncludeLegacy,               # uninstall ONLY: also remove files recognised by name/size and the project-only folders (older installs without a manifest). Off by default: -Uninstall removes exactly the files in the manifest.
  [switch]$Loose,
  [switch]$FaceTintArchive,            # also use CapitalActors - FaceTint.ba2 (the 1,056 FaceGen tint TGAs); default = those TGAs stay loose (archive use of .tga unverified)
  [Alias('WhatIf')][switch]$DryRun,
  [string]$Sandbox,
  [string]$OutDir,
  [string]$Fo3Data,                    # where the FO3 videos come from (default: found like setup.ps1 does)
  [string[]]$AlsoPlugins               # extra plugin file names from tool\output (e.g. F3_Perks.esp): installed and activated AFTER the Capital plugins (end of the load order)
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
. (Join-Path $root 'packaging\common.ps1')
$out = if ($OutDir) { (Resolve-Path $OutDir).Path.TrimEnd('\') } else { Join-Path $root 'tool\output' }
$stageDir = Join-Path $out 'ba2-stage'
$stamp = Get-Date -Format yyyyMMdd-HHmmss

if ($Sandbox) {
  $sb = if (Test-Path $Sandbox) { (Resolve-Path $Sandbox).Path } else { New-Item -ItemType Directory -Force $Sandbox | Select-Object -ExpandProperty FullName }
  $data = Join-Path $sb 'Data'; New-Item -ItemType Directory -Force $data | Out-Null
  $pluginsDir = Join-Path $sb 'LocalAppData\Fallout4'
  $myGames = Join-Path $sb 'MyGames'
  $backupRoot = Join-Path $sb 'backup'
  $manifest = Join-Path $sb 'installed-files.txt'
  $logDir = $sb
  Write-Host "SANDBOX: everything goes to $sb (the real Fallout 4 folder is not touched)" -ForegroundColor Yellow
} else {
  $fo4 = Get-Fo4Root
  if (-not $fo4) { throw 'Fallout 4 Data not found (Steam library / registry). Set FO4_DIR to the Fallout 4 folder.' }
  $data = Join-Path $fo4 'Data'
  $pluginsDir = Join-Path $env:LOCALAPPDATA 'Fallout4'
  $myGames = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'My Games\Fallout4'
  $backupRoot = Join-Path $root 'backup'
  $manifest = Join-Path $root 'installed-files.txt'
  $logDir = Join-Path $root 'Logs'
  if (-not (Test-Path "$data\Fallout4.esm")) { throw "Fallout 4 Data not found at $data" }
}
$pluginsTxt = Join-Path $pluginsDir 'plugins.txt'
$customIni = Join-Path $myGames 'Fallout4Custom.ini'
$prefsIni = Join-Path $myGames 'Fallout4Prefs.ini'
New-Item -ItemType Directory -Force $logDir | Out-Null
$logFile = Join-Path $logDir ("install-output-$stamp$(if ($DryRun) { '-dryrun' }).log")
$script:logLines = New-Object 'System.Collections.Generic.List[string]'
function Log([string]$m, [string]$color = '') {
  $script:logLines.Add($m)
  if ($color) { Write-Host $m -ForegroundColor $color } else { Write-Host $m }
}
function Detail([string]$m) { $script:logLines.Add($m) }       # log file only
function Flush-Log { try { [IO.File]::WriteAllLines($logFile, $script:logLines.ToArray()) } catch { } }
if ($DryRun) { Log 'DRY RUN: nothing will be written, copied, removed or restored.' 'Yellow' }

# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------
# constants
# the plugins of the port (CapitalClimate/Lighting/LOD/Water are old experiments and are NOT installed); archives and the plugins listed in $order below
$pluginSet = 'Fallout3.esm', 'Anchorage.esm', 'ThePitt.esm', 'BrokenSteel.esm', 'PointLookout.esm', 'Zeta.esm', 'CapitalNoBarks.esp', 'F3_Skills.esp', 'F3_Perks.esp', 'CapitalDLCActors.esp', 'CapitalCorpses.esp', 'CapitalActors.esp', 'CapitalNavmesh.esp', 'CapitalNavmeshDLC.esp', 'CapitalQuests.esp', 'CapitalItems.esp', 'CapitalFixes.esp', 'CapitalStart.esp', 'CapitalFurniture.esp', 'CapitalSounds.esp', 'CapitalDialogue.esp', 'CapitalChoices.esp', 'CapitalDLCDialogue.esp', 'CapitalAI.esp', 'CapitalDLCAI.esp', 'CapitalScripts.esp', 'CapitalRadio.esp', 'CapitalAnim.esp', 'CapitalChargen.esp'
# load order for plugins.txt (XDI.esm is not ours: the user's F4SE/XDI copy, see README)
$order = 'Fallout3.esm', 'Anchorage.esm', 'ThePitt.esm', 'BrokenSteel.esm', 'PointLookout.esm', 'Zeta.esm', 'XDI.esm', 'CapitalNoBarks.esp', 'F3_Skills.esp', 'F3_Perks.esp', 'CapitalDLCActors.esp', 'CapitalCorpses.esp', 'CapitalActors.esp', 'CapitalNavmesh.esp', 'CapitalNavmeshDLC.esp', 'CapitalQuests.esp', 'CapitalItems.esp', 'CapitalFixes.esp', 'CapitalStart.esp', 'CapitalFurniture.esp', 'CapitalSounds.esp', 'CapitalDialogue.esp', 'CapitalChoices.esp', 'CapitalDLCDialogue.esp', 'CapitalAI.esp', 'CapitalDLCAI.esp', 'CapitalScripts.esp', 'CapitalRadio.esp', 'CapitalAnim.esp', 'CapitalChargen.esp'
$AlsoPlugins = @($AlsoPlugins | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
foreach ($a in $AlsoPlugins) { if ($order -notcontains $a) { $order = @($order) + $a }; if ($pluginSet -notcontains $a) { $pluginSet = @($pluginSet) + $a } }
$ourPlugins = @($order | Where-Object { $_ -ne 'XDI.esm' })
# folders below Data that only this project writes (named after it / after its plugins): files there are ours even when no manifest says so (installs before the manifest was complete)
$privateRx = @('^Meshes\\FO3Faces\\', '^Meshes\\Capital\\', '^Materials\\Capital\\', '^Textures\\Capital\\',
  '^Meshes\\Actors\\Character\\FaceGenData\\FaceGeom\\CapitalActors\.esp\\', '^Textures\\Actors\\Character\\FaceCustomization\\CapitalActors\.esp\\',
  '^Sound\\fo3\\', '^Music\\fo3\\', '^Sound\\Voice\\Capital(Dialogue|Radio)\.esp\\', '^Video\\F3')
# the same folders as whole trees (wiped when their content moves into an archive, and by -Uninstall)
$privateDirs = @('Meshes\FO3Faces', 'Meshes\Capital', 'Materials\Capital', 'Textures\Capital',
  'Meshes\Actors\Character\FaceGenData\FaceGeom\CapitalActors.esp', 'Textures\Actors\Character\FaceCustomization\CapitalActors.esp',
  'Sound\fo3', 'Music\fo3', 'Sound\Voice\CapitalDialogue.esp', 'Sound\Voice\CapitalRadio.esp')
# loose source folder (below tool\output\loose) -> the private Data folder that holds its installed twin
$looseToDataDir = @{ 'meshes\fo3faces' = 'Meshes\FO3Faces'; 'meshes\actors' = 'Meshes\Actors\Character\FaceGenData\FaceGeom\CapitalActors.esp'; 'meshes\capital' = 'Meshes\Capital'
  'materials\capital' = 'Materials\Capital'; 'textures\capital' = 'Textures\Capital'; 'textures\actors' = 'Textures\Actors\Character\FaceCustomization\CapitalActors.esp' }
# files this script generates in Data (not in the plan): recorded and removed with the rest
$generatedRel = 'Video\F3Blank.bik', 'F4SE\Plugins\FrameCap.ini'
$knownStageNames = 'CapitalActors - Main.ba2', 'CapitalActors - FaceTint.ba2', 'CapitalItems - Main.ba2', 'CapitalItems - Textures.ba2'
$dataDirNames = @{ meshes = 'Meshes'; materials = 'Materials'; textures = 'Textures'; Sound = 'Sound'; Music = 'Music' }

function Test-Private([string]$rel) { foreach ($rx in $privateRx) { if ($rel -match $rx) { return $true } }; return $false }
function Get-Owned { $s = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase); if (Test-Path $manifest) { foreach ($l in Get-Content $manifest) { if ($l -and -not $l.StartsWith('#')) { [void]$s.Add($l.Trim()) } } }; return ,$s }   # the comma keeps an empty set from being unrolled to $null
$owned = Get-Owned

# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------
# operations (all game-folder writes go through these so -DryRun is airtight)
$script:made = @{}
$script:st = [ordered]@{ copied = 0; copiedBytes = [int64]0; unchanged = 0; adopted = 0; backedUp = 0; removed = 0; restored = 0; failed = 0 }
$script:bakDir = $null
function Ensure-Dir([string]$d) {
  if ($DryRun -or $script:made.ContainsKey($d)) { return }
  [IO.Directory]::CreateDirectory($d) | Out-Null; $script:made[$d] = 1
}
function Same-File([string]$a, [string]$b) {
  $fa = New-Object IO.FileInfo $a; $fb = New-Object IO.FileInfo $b
  return ($fa.Length -eq $fb.Length) -and ([math]::Abs(($fa.LastWriteTimeUtc - $fb.LastWriteTimeUtc).TotalSeconds) -lt 2)
}
$script:backed = @{}
function Backup-File([string]$dstFull, [string]$rel) {
  if ($script:backed.ContainsKey($rel)) { return }
  $script:backed[$rel] = 1
  if (-not $script:bakDir) {
    $script:bakDir = Join-Path $backupRoot "Data-$stamp"
    if (-not $DryRun) { New-Item -ItemType Directory -Force $script:bakDir | Out-Null; Set-Content (Join-Path $script:bakDir '_capital-backup.txt') "originals that install-output.ps1 replaced; -Uninstall restores them" -Encoding ascii }
  }
  $t = Join-Path $script:bakDir $rel
  Log "  backup  $rel  ->  $t"
  if (-not $DryRun) { [IO.Directory]::CreateDirectory((Split-Path $t -Parent)) | Out-Null; [IO.File]::Copy($dstFull, $t, $true) }
  $script:st.backedUp++
}
# copy $src to Data\$rel; returns 'copied' | 'unchanged' | 'adopted'
function Install-File([string]$src, [string]$rel, [switch]$KeepIfExists) {
  $dst = Join-Path $data $rel
  if ([IO.File]::Exists($dst)) {
    if ($KeepIfExists) { $script:st.adopted++; return 'adopted' }
    if (Same-File $src $dst) { $script:st.unchanged++; return 'unchanged' }
    if (-not $owned.Contains($rel) -and -not (Test-Private $rel)) { Backup-File $dst $rel }
  }
  $len = (New-Object IO.FileInfo $src).Length
  if (-not $DryRun) {
    Ensure-Dir (Split-Path $dst -Parent)
    try { [IO.File]::Copy($src, $dst, $true) } catch { Log "  FAILED  $rel : $($_.Exception.Message)" 'Red'; $script:st.failed++; return 'failed' }
  }
  $script:st.copied++; $script:st.copiedBytes += $len
  return 'copied'
}
$script:dryTrees = New-Object 'System.Collections.Generic.List[string]'   # -DryRun only: trees already counted as removed
function Remove-Owned([string]$rel, [string]$why) {
  $p = Join-Path $data $rel
  if (-not [IO.File]::Exists($p)) { return $false }
  if ($DryRun) { foreach ($t in $script:dryTrees) { if ($rel.StartsWith($t + '\', [StringComparison]::OrdinalIgnoreCase)) { return $false } } }
  Detail "  remove  $rel  ($why)"
  if (-not $DryRun) { try { [IO.File]::Delete($p) } catch { Log "  FAILED to remove $rel : $($_.Exception.Message)" 'Red'; $script:st.failed++; return $false } }
  $script:st.removed++
  return $true
}
function Remove-OwnedTree([string]$relDir, [string]$why) {
  $p = Join-Path $data $relDir
  if (-not [IO.Directory]::Exists($p)) { return }
  $n = ([IO.Directory]::EnumerateFiles($p, '*', [IO.SearchOption]::AllDirectories) | Measure-Object).Count
  Log "  remove folder Data\$relDir ($n files, $why)"
  if ($DryRun) { $script:dryTrees.Add($relDir) }
  else { try { [IO.Directory]::Delete($p, $true) } catch { Log "  FAILED to remove Data\$relDir : $($_.Exception.Message)" 'Red'; $script:st.failed++ } }
  $script:st.removed += $n
  Prune-EmptyDirs ($relDir + '\x')
}
function Prune-EmptyDirs([string]$rel) {   # remove now-empty parents below the first level of Data
  if ($DryRun) { return }
  $d = Split-Path (Join-Path $data $rel) -Parent
  while ($d -and $d.Length -gt $data.Length + 1) {
    $parent = Split-Path $d -Parent
    if ((Split-Path $parent -Parent) -eq $null -or $parent -eq $data) { break }       # keep Data\<first level>
    if (-not [IO.Directory]::Exists($d)) { $d = $parent; continue }
    if ([IO.Directory]::Exists($d) -and -not ([IO.Directory]::EnumerateFileSystemEntries($d) | Select-Object -First 1)) { [IO.Directory]::Delete($d); $d = $parent } else { break }
  }
}
function Backup-Dirs { if (-not (Test-Path $backupRoot)) { return @() }; return @(Get-ChildItem $backupRoot -Directory -Filter 'Data-*' | Where-Object { Test-Path (Join-Path $_.FullName '_capital-backup.txt') } | Sort-Object Name) }
function Restore-Backup([string]$rel) {
  foreach ($b in Backup-Dirs) {
    $f = Join-Path $b.FullName $rel
    if ([IO.File]::Exists($f)) {
      Log "  restore $rel  <-  $($b.Name)"
      if (-not $DryRun) { [IO.Directory]::CreateDirectory((Split-Path (Join-Path $data $rel) -Parent)) | Out-Null; [IO.File]::Copy($f, (Join-Path $data $rel), $true) }
      $script:st.restored++
      return $true
    }
  }
  return $false
}

# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------
# the install plan (read-only): Src, Rel, Group, Keep (adopt an existing file instead of overwriting)
function New-Plan {
  param([switch]$ForUninstall)
  $plan = New-Object 'System.Collections.Generic.List[object]'
  function Add([string]$src, [string]$rel, [string]$group, [bool]$keep = $false) { $plan.Add([pscustomobject]@{ Src = $src; Rel = $rel; Group = $group; Keep = $keep }) }
  function Add-Tree([string]$srcDir, [string]$dataSub, [string]$group, [string[]]$skip = @(), [string]$skipTop = $null) {
    if (-not [IO.Directory]::Exists($srcDir)) { return }
    $base = $srcDir.TrimEnd('\')
    foreach ($f in [IO.Directory]::EnumerateFiles($base, '*', [IO.SearchOption]::AllDirectories)) {
      $sub = $f.Substring($base.Length + 1)
      if ($skipTop -and $sub.StartsWith($skipTop + '\', [StringComparison]::OrdinalIgnoreCase)) { continue }
      $key = ($dataSub + '\' + $sub).ToLowerInvariant()
      $hit = $false; foreach ($s in $skip) { if ($key.StartsWith($s + '\')) { $hit = $true; break } }
      if ($hit) { continue }
      Add $f ($dataSub + '\' + $sub) $group
    }
  }
  # 1. plugins + top-level archives (base converter archives, audio archives from audio\pack_audio.ps1)
  $top = @(Get-ChildItem $out -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -eq '.ba2' -or $pluginSet -contains $_.Name })
  foreach ($f in $top) { Add $f.FullName $f.Name $(if ($f.Extension -eq '.ba2') { 'archives' } else { 'plugins' }) }
  # 2. terrain LOD settings
  foreach ($f in @(Get-ChildItem (Join-Path $out 'LODSettings') -File -ErrorAction SilentlyContinue)) { Add $f.FullName "LODSettings\$($f.Name)" 'lodsettings' }
  # 3. staged archives (fresh ones only) and the loose folders they replace
  $skipKeys = New-Object 'System.Collections.Generic.List[string]'
  $script:usedStage = New-Object 'System.Collections.Generic.List[object]'
  $script:staleStage = New-Object 'System.Collections.Generic.List[string]'
  $info = if ($Loose) { $null } else { Read-StageInfo $stageDir }
  if (-not $Loose -and -not $info) { $script:noStage = $true }
  if ($info -and $info.archives) {
    foreach ($e in $info.archives) {
      $file = Join-Path $stageDir $e.name
      $use = ($e.defaultInstall -or ($FaceTintArchive -and $e.key -eq 'actors-facetint'))
      if (-not $use) { continue }
      if (-not (Test-Path $file) -or (Get-Item $file).Length -ne $e.archiveBytes -or -not $e.verified) { $script:staleStage.Add("$($e.name) (missing / changed / unverified archive file)"); continue }
      $looseDir = Join-Path $out 'loose'
      $haveSources = $false; foreach ($s in $e.sources) { if (Test-Path (Join-Path $looseDir $s)) { $haveSources = $true } }
      if ($haveSources) {
        $now = Get-SourceSig $looseDir @($e.sources)
        if ($now.Sig -ne $e.sig) { $script:staleStage.Add("$($e.name) (loose sources changed since it was built: rerun packaging\pack_ba2.ps1)"); continue }
      }
      Add $file $e.name 'staged archives'
      $script:usedStage.Add($e)
      foreach ($s in $e.sources) { $skipKeys.Add(($dataDirNames[($s -split '\\')[0]] + '\' + (($s -split '\\', 2)[1])).ToLowerInvariant()) }
    }
  }
  # 4. loose payload
  $packedAudio = Test-Path (Join-Path $out 'CapitalDialogue - Main.ba2')
  $loose = Join-Path $out 'loose'
  foreach ($sub in 'meshes', 'materials', 'textures', 'Sound', 'Music') {
    if ($packedAudio -and $sub -eq 'Music') { continue }
    $skipTop = if ($packedAudio -and $sub -eq 'Sound') { 'Voice' } else { $null }
    Add-Tree (Join-Path $loose $sub) $dataDirNames[$sub] "loose $sub" $skipKeys.ToArray() $skipTop
  }
  if (-not $packedAudio) { Add-Tree (Join-Path $out 'voice\Sound') 'Sound' 'loose voice' }
  $script:packedAudio = $packedAudio
  # 5. FO3 videos (the player's own install), compiled scripts, FrameCap
  $fo3d = if ($Fo3Data) { $Fo3Data } else { Get-Fo3Data }
  $script:fo3Data = $fo3d
  $script:f3vids = [ordered]@{ 'Fallout INTRO Vsk.bik' = 'F3Intro.bik'; '1 year later.bik' = 'F3_1yr.bik'; '9 years later.bik' = 'F3_9yr.bik'; '6 years later.bik' = 'F3_6yr.bik'; '3 years later.bik' = 'F3_3yr.bik' }
  if ($fo3d) {
    foreach ($kv in $script:f3vids.GetEnumerator()) { $s = Join-Path (Join-Path $fo3d 'Video') $kv.Key; if (Test-Path $s) { Add $s ('Video\' + $kv.Value) 'video' $true } }
  }
  Add-Tree (Join-Path $root 'scripts\out') 'Scripts' 'scripts'
  $fc = Join-Path $root 'tools\framecap\FrameCap.dll'
  if (Test-Path $fc) { Add $fc 'F4SE\Plugins\FrameCap.dll' 'f4se' }
  return $plan
}

# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------
if ($Uninstall) {
  Log "Uninstall from $data" 'Cyan'
  $plan = New-Plan
  $targets = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
  foreach ($r in $owned) { [void]$targets.Add($r) }
  $legacy = 0
  # installs made before the manifest was complete: planned files that are in Data with the same size, and anything in the project-only folders
  foreach ($p in $plan) {
    if (-not $IncludeLegacy) { break }
    if ($targets.Contains($p.Rel)) { continue }
    $dst = Join-Path $data $p.Rel
    if (-not [IO.File]::Exists($dst)) { continue }
    if ((Test-Private $p.Rel) -or ((New-Object IO.FileInfo $dst).Length -eq (New-Object IO.FileInfo $p.Src).Length)) { [void]$targets.Add($p.Rel); $legacy++ }
  }
  $stageInfo = Read-StageInfo $stageDir
  $stageNames = @($knownStageNames) + @(if ($stageInfo -and $stageInfo.archives) { $stageInfo.archives | ForEach-Object { $_.name } })
  if ($IncludeLegacy) {
  foreach ($g in $generatedRel) { if ([IO.File]::Exists((Join-Path $data $g)) -and -not $targets.Contains($g)) { [void]$targets.Add($g); $legacy++ } }
  foreach ($n in ($stageNames | Select-Object -Unique)) { if ([IO.File]::Exists((Join-Path $data $n)) -and -not $targets.Contains($n)) { [void]$targets.Add($n); $legacy++ } }
  }
  if (-not $targets.Count -and -not $owned.Count) { Log 'installed-files.txt is missing or empty and no installed files were recognised; nothing to uninstall.' 'Yellow' }
  Log "$($owned.Count) files in installed-files.txt, $legacy more recognised from earlier installs (same name + size / project-only folders)"
  if ($IncludeLegacy) { foreach ($d in $privateDirs) { Remove-OwnedTree $d 'project-only folder' } }
  else { Log 'Only the files in installed-files.txt are removed (pass -IncludeLegacy to also remove files of older installs that have no manifest).' }
  $noRestore = 0
  foreach ($rel in ($targets | Sort-Object)) {
    $had = Remove-Owned $rel 'installed by install-output.ps1'
    if ($had) { Prune-EmptyDirs $rel }
    if (-not (Restore-Backup $rel) -and $had) { $noRestore++ }
  }
  if (Test-Path $pluginsTxt) {
    $manifestPlugins = @($owned | Where-Object { $_ -notmatch '\\' -and $_ -match '\.(esp|esm|esl)$' })      # every plugin the manifest recorded (incl. -AlsoPlugins ones)
    $rx = '^\*?(' + ((@($ourPlugins) + $manifestPlugins | Select-Object -Unique | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')\s*$'
    $before = @(Get-Content $pluginsTxt); $after = @($before | Where-Object { $_ -notmatch $rx })
    Log "plugins.txt: removing $($before.Count - $after.Count) of our plugin lines"
    if (-not $DryRun) { Set-Content $pluginsTxt $after -Encoding ascii }
  }
  if (-not $DryRun -and (Test-Path $manifest)) { Remove-Item $manifest }
  $legacyBak = @(Get-ChildItem $backupRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'Data-*' -and -not (Test-Path (Join-Path $_.FullName '_capital-backup.txt')) })
  if ($legacyBak) { Log "$($legacyBak.Count) older backup folder(s) in backup\ were NOT restored: they predate this script and hold earlier port builds (not game originals)." }
  Log ("{0}: {1} files {2}, {3} originals restored, {4} failed." -f $(if ($DryRun) { 'DRY RUN would' } else { 'Uninstalled' }), $script:st.removed, $(if ($DryRun) { 'remove' } else { 'removed' }), $script:st.restored, $script:st.failed)
  # ini edits: put back what the first install changed (a Custom.ini we created is removed only while it still holds exactly what we wrote)
  $undoFile = Join-Path (Split-Path $manifest) 'installed-ini-undo.json'
  if (Test-Path $undoFile) {
    $u = Get-Content $undoFile -Raw | ConvertFrom-Json
    if ($u.customCreated -and (Test-Path $customIni)) {
      $c = (Get-Content $customIni -Raw) -replace '\s+', ''
      if ($c -eq '[Archive]bInvalidateOlderFiles=1sResourceDataDirsFinal=') {
        if ($DryRun) { Log "would remove $customIni (created by the install)" } else { Remove-Item $customIni; Log 'removed Fallout4Custom.ini (created by the install)' }
      } else { Log 'Fallout4Custom.ini was edited since the install: left as it is.' }
    }
    if ($u.prefsKey -ne 'untouched' -and (Test-Path $prefsIni)) {
      $t = Get-Content $prefsIni -Raw
      if ($u.prefsKey -eq 'absent') { $t = $t -replace '(?m)^bEnableFileSelection=.*\r?\n?', '' } else { $t = $t -replace '(?m)^bEnableFileSelection=[^\r\n]*', ('bEnableFileSelection=' + $u.prefsKey) }
      if ($DryRun) { Log "would restore bEnableFileSelection ($($u.prefsKey)) in Fallout4Prefs.ini" } else { Set-Content $prefsIni $t -NoNewline; Log "Fallout4Prefs.ini: bEnableFileSelection restored ($($u.prefsKey))" }
    }
    if (-not $DryRun) { Remove-Item $undoFile }
  }
  Log 'Not reverted: Data files that are not ours (XDI, F4SE, MCM).'
  Flush-Log
  return
}

# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------
$plan = New-Plan
if (-not $plan.Count) { throw "tool\output has no .esm/.ba2 files yet ($out)." }
if (-not ($plan | Where-Object { $_.Group -eq 'plugins' })) { throw "no converted plugins in $out" }
if ($script:noStage) { Log 'Installing the textures / faces / materials as loose files (the demo does not pack them into archives). This is normal.' }
foreach ($w in $script:staleStage) { Log "Staged archive NOT used: $w - its loose files are installed instead" 'Yellow' }
if ($Loose) { Log '-Loose: no staged archives; textures / faces / materials / own models go in loose.' }

# summary of the plan per group
Log ("Plan: {0} files -> {1}" -f $plan.Count, $data) 'Cyan'
$plan | Group-Object Group | ForEach-Object {
  $bytes = ($_.Group | ForEach-Object { (New-Object IO.FileInfo $_.Src).Length } | Measure-Object -Sum).Sum
  Log ("  {0,-16} {1,6} files  {2}" -f $_.Name, $_.Count, (Format-Size $bytes))
}

# originals first: a file in Data that is not ours and would be replaced is backed up BEFORE the manifest names it as ours, so an interrupted install can never lose one
foreach ($p in $plan) {
  if ($p.Keep) { continue }
  $dst = Join-Path $data $p.Rel
  if ([IO.File]::Exists($dst) -and -not $owned.Contains($p.Rel) -and -not (Test-Private $p.Rel) -and -not (Same-File $p.Src $dst)) { Backup-File $dst $p.Rel }
}

# manifest first (so an interrupted install can still be uninstalled): old entries + every planned file
$newOwned = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($r in $owned) { [void]$newOwned.Add($r) }
foreach ($p in $plan) { [void]$newOwned.Add($p.Rel) }

# a switch between loose and archive modes: remove what would shadow / duplicate
if ($Loose) {
  foreach ($n in $knownStageNames) { if ($owned.Contains($n) -and [IO.File]::Exists((Join-Path $data $n))) { if (Remove-Owned $n 'staged archive, -Loose install') { [void]$newOwned.Remove($n) } } }
}
foreach ($e in $script:usedStage) {
  foreach ($s in $e.sources) {
    $dd = $looseToDataDir[$s.ToLowerInvariant()]
    if ($dd) { Remove-OwnedTree $dd "now inside $($e.name)" } else { Log "  (no loose-twin folder mapping for source $s)" }
  }
}

if (-not $DryRun) {
  $lines = @('# install-output.ps1 manifest: every file below is placed in Fallout 4\Data by this project (relative paths); -Uninstall removes them', "# written $(Get-Date -Format s)") + @($newOwned | Sort-Object)
  [IO.File]::WriteAllLines($manifest, $lines)
}

# copy
$done = 0; $seenGroup = @{}
foreach ($p in $plan) {
  $r = Install-File $p.Src $p.Rel -KeepIfExists:$p.Keep
  if (-not $seenGroup.ContainsKey($p.Group)) { $seenGroup[$p.Group] = 1; Log "installing $($p.Group) ..." }
  Detail ("  {0,-9} {1}" -f $r, $p.Rel)
  $done++
}
$mb = [math]::Round($script:st.copiedBytes / 1MB)
Log ("{0}: {1} files {2} ({3} MB), {4} already up to date, {5} existing kept, {6} originals backed up, {7} failed" -f $(if ($DryRun) { 'DRY RUN' } else { 'Done' }), $script:st.copied, $(if ($DryRun) { 'to copy' } else { 'copied' }), $mb, $script:st.unchanged, $script:st.adopted, $script:st.backedUp, $script:st.failed)

# generated video helpers
$vdir = Join-Path $data 'Video'
if ($DryRun) { Log 'would run tools\make_blank_bik.py (F3Blank.bik, if missing) and tools\patch_bink_track.py (Bink audio track id 1 on the F3 videos, idempotent)' }
elseif (Test-Path (Join-Path $vdir 'F3Intro.bik')) {
  # the New Game movie call of FO4 needs a REAL movie (a missing file hangs the load): a 2-frame cut of the FO3 '2 weeks later' card
  $blank = Join-Path $vdir 'F3Blank.bik'
  $twoWeeks = if ($script:fo3Data) { Join-Path $script:fo3Data 'Video\2 weeks later.bik' } else { $null }
  if (-not (Test-Path $blank) -and $twoWeeks -and (Test-Path $twoWeeks)) { & python (Join-Path $root 'tools\make_blank_bik.py') $twoWeeks $blank 36 1; [void]$newOwned.Add('Video\F3Blank.bik'); $generated = $true }
  # FO4 plays only the Bink audio track whose id matches its language (vanilla videos: ids 1..5); FO3 movies have one track with id 0 -> silent. Idempotent in-place header patch.
  $vids = @($script:f3vids.Values | ForEach-Object { Join-Path $vdir $_ } | Where-Object { Test-Path $_ })
  if ($vids) { & python (Join-Path $root 'tools\patch_bink_track.py') 1 @vids }
  if ($generated) { [IO.File]::WriteAllLines($manifest, (@('# install-output.ps1 manifest: every file below is placed in Fallout 4\Data by this project (relative paths); -Uninstall removes them', "# written $(Get-Date -Format s)") + @($newOwned | Sort-Object))) }
}
# FrameCap: F4SE plugin that caps the game at 60 fps (above 60 fps FO4 runs its simulation faster than real time); the ini is kept if it already exists (fps=0 turns the cap off)
$fcIni = Join-Path $data 'F4SE\Plugins\FrameCap.ini'
if ((Test-Path (Join-Path $root 'tools\framecap\FrameCap.dll')) -and -not (Test-Path $fcIni)) {
  if ($DryRun) { Log 'would create F4SE\Plugins\FrameCap.ini (fps=60)' }
  else { Set-Content $fcIni "[Limiter]`r`nfps=60`r`n" -Encoding ascii; [void]$newOwned.Add('F4SE\Plugins\FrameCap.ini'); [IO.File]::WriteAllLines($manifest, (@('# install-output.ps1 manifest: every file below is placed in Fallout 4\Data by this project (relative paths); -Uninstall removes them', "# written $(Get-Date -Format s)") + @($newOwned | Sort-Object))); Log 'installed FrameCap (60 fps cap)' }
}

# Activate plugins (load order: masters first). FO4 reads *Name lines from plugins.txt.
# XDI.esm (Extended Dialogue Interface, FO3-style option list) must already be in Data (see README: it is copied from a separate install, with F4SE).
$header = '# This file is used by Fallout4 to keep track of your downloaded content.'
$existing = if (Test-Path $pluginsTxt) { @(Get-Content $pluginsTxt) } else { @() }
$active = @($order | Where-Object { Test-Path (Join-Path $data $_) })
if ($DryRun) { $active = @($order | Where-Object { $n = $_; (Test-Path (Join-Path $data $n)) -or ($plan | Where-Object { $_.Rel -eq $n }) }) }
# keep other mods' lines; drop our plugins and any comment line (re-added as the header)
$keep = @($existing | Where-Object { $_ -notmatch '^#' -and $_.Trim() -and $_ -notmatch ('^\*?(' + (($order | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')') })
if ($DryRun) { Log "would write plugins.txt: $($active -join ', ')" }
else {
  New-Item -ItemType Directory -Force $pluginsDir | Out-Null
  if ((Test-Path $pluginsTxt) -and -not (Test-Path (Join-Path $backupRoot 'plugins.txt.pre-capital'))) { New-Item -ItemType Directory -Force $backupRoot | Out-Null; Copy-Item $pluginsTxt (Join-Path $backupRoot 'plugins.txt.pre-capital') }
  (@($header) + $keep + @($active | ForEach-Object { "*$_" })) | Set-Content $pluginsTxt -Encoding ascii
  Log "plugins.txt: $($active -join ', ')"
}

# Loose-file / plugin-selection settings (custom ini is never touched by the launcher)
if ($DryRun) {
  Log "would ensure $customIni ([Archive] bInvalidateOlderFiles=1, sResourceDataDirsFinal=) and Fallout4Prefs.ini bEnableFileSelection=1"
} else {
  New-Item -ItemType Directory -Force $myGames | Out-Null
  # what -Uninstall must undo: written once (the first install), so an update never records our own edit as the "original"
  $undoFile = Join-Path (Split-Path $manifest) 'installed-ini-undo.json'
  $undo = @{ customCreated = $false; prefsKey = 'untouched' }
  if (Test-Path $undoFile) { $o = Get-Content $undoFile -Raw | ConvertFrom-Json; $undo.customCreated = [bool]$o.customCreated; $undo.prefsKey = [string]$o.prefsKey }
  if (-not (Test-Path $customIni)) {
    Set-Content $customIni "[Archive]`r`nbInvalidateOlderFiles=1`r`nsResourceDataDirsFinal=`r`n" -Encoding ascii; 'created Fallout4Custom.ini'
    $undo.customCreated = $true
  }
  if (Test-Path $prefsIni) {
    $t = Get-Content $prefsIni -Raw
    if ($t -notmatch '(?m)^bEnableFileSelection=1') {
      if ($undo.prefsKey -eq 'untouched') { $undo.prefsKey = if ($t -match '(?m)^bEnableFileSelection=(.*?)\s*$') { $Matches[1] } else { 'absent' } }
      Copy-Item $prefsIni "$prefsIni.bak" -Force
      if ($t -match '(?m)^bEnableFileSelection=') { $t = $t -replace '(?m)^bEnableFileSelection=[^\r\n]*', 'bEnableFileSelection=1' }
      elseif ($t -match '(?m)^\[Launcher\]') { $t = $t -replace '(?m)^\[Launcher\]\s*$', "[Launcher]`r`nbEnableFileSelection=1" }
      else { $t += "`r`n[Launcher]`r`nbEnableFileSelection=1`r`n" }
      Set-Content $prefsIni $t -NoNewline
      'Fallout4Prefs.ini: bEnableFileSelection=1 (backup .bak)'
    }
  } else {
    Write-Warning 'Fallout4Prefs.ini does not exist yet: launch Fallout 4 once from Steam (to the main menu), then re-run this script so mods get enabled.'
  }
  [IO.File]::WriteAllText($undoFile, ($undo | ConvertTo-Json))
}
foreach ($g in $generatedRel) { if (-not $DryRun -and [IO.File]::Exists((Join-Path $data $g))) { [void]$newOwned.Add($g) } }
# final manifest: drop entries whose file is no longer in Data (loose twins that moved into an archive and back)
if (-not $DryRun) {
  $final = @($newOwned | Where-Object { [IO.File]::Exists((Join-Path $data $_)) } | Sort-Object)
  [IO.File]::WriteAllLines($manifest, (@('# install-output.ps1 manifest: every file below is placed in Fallout 4\Data by this project (relative paths); -Uninstall removes them', "# written $(Get-Date -Format s)") + $final))
  Log "installed-files.txt: $($final.Count) files"
}
Flush-Log
Log "Log: $logFile"
if (-not $DryRun) { "Done. Start Fallout 4 from Steam, choose New Game, and you start outside Vault 101." }
Flush-Log
