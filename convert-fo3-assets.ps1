# Convert Fallout 3 meshes/textures to Fallout 4 formats (same steps as fnv-to-fo4's WorkerThread).
#   powershell -ExecutionPolicy Bypass -File .\convert-fo3-assets.ps1 [-Plugins Fallout3,Anchorage,...] [-SkipBa2]
# Output: tool\output\<Plugin> - Main.ba2 / - Textures.ba2. Reads FO3 archives only; never writes to game folders.
param(
  [string[]]$Plugins = @('Fallout3'),
  [switch]$SkipBa2
)
$ErrorActionPreference = 'Stop'
# powershell -File passes "A,B,C" as one string
$Plugins = $Plugins | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ }
$root = $PSScriptRoot
. (Join-Path $root 'packaging\common.ps1')
$tool = Join-Path $root 'tool'
$fo3Data = 'X:\__CAPITAL_FO3_DATA__'
$fo4 = 'X:\__CAPITAL_FO4__'

# BSAs belonging to each FO3 plugin
$bsaMap = @{
  'Fallout3'     = 'Fallout - Meshes.bsa','Fallout - Textures.bsa','Fallout - Misc.bsa','Fallout - Sound.bsa','Fallout - MenuVoices.bsa','Fallout - Voices.bsa'
  'Anchorage'    = 'Anchorage - Main.bsa','Anchorage - Sounds.bsa'
  'ThePitt'      = 'ThePitt - Main.bsa','ThePitt - Sounds.bsa'
  'BrokenSteel'  = 'BrokenSteel - Main.bsa','BrokenSteel - Sounds.bsa'
  'PointLookout' = 'PointLookout - Main.bsa','PointLookout - Sounds.bsa'
  'Zeta'         = 'Zeta - Main.bsa','Zeta - Sounds.bsa'
}

$temp = New-Item -ItemType Directory -Force "$tool\temp"
$extracted = New-Item -ItemType Directory -Force "$tool\extracted"
$output = New-Item -ItemType Directory -Force "$tool\output"
$a2 = "$fo4\Tools\Archive2\Archive2.exe"
$failList = "$root\elric-failures.txt"            # meshes Elric still could not do: step 15 (loose meshes) converts them one by one
$skipList = "$root\archive2-skipped.txt"          # files Archive2 left out of a texture archive
Remove-Item $failList, $skipList -ErrorAction SilentlyContinue

function Step($msg) { Write-Host "[$(Get-Date -Format HH:mm:ss)] $msg" -ForegroundColor Cyan }
$script:LastExit = 0
function Run($exe, $argList, $cwd = $tool) {
  $p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $cwd -Wait -NoNewWindow -PassThru
  $script:LastExit = $p.ExitCode
  if ($p.ExitCode -ne 0) { Write-Warning "$([IO.Path]::GetFileName($exe)) exited with $($p.ExitCode)" }
}
function Clear-Work { foreach ($d in $temp, $extracted) { Remove-Item "$d\*" -Recurse -Force -ErrorAction SilentlyContinue } }
# a crashing Elric makes Windows write a ~33 MB dump into %LOCALAPPDATA%\CrashDumps each time: remove the ones this run just caused (never older ones)
function Remove-ElricDumps([datetime]$since) {
  $d = Join-Path $env:LOCALAPPDATA 'CrashDumps'
  if (Test-Path $d) { Get-ChildItem $d -Filter 'Elrich.exe.*.dmp' -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -ge $since } | Remove-Item -Force -ErrorAction SilentlyContinue }
}
# Archive2 with its output kept in a log (the thousands of "Adding" lines are not shown): a skipped file or a non-zero exit is judged here instead of being ignored.
# Fonts and interface art of Fallout 3 are the only things it may leave out silently (Fallout 4 draws its own interface); anything else is listed as a warning.
function Invoke-Archive2([string]$label, [string[]]$a2Args, [string]$archive) {
  $log = Join-Path $tool ('archive2-' + ($label -replace '[^A-Za-z0-9]+', '_') + '.log')
  $p = Start-Process -FilePath $a2 -ArgumentList $a2Args -WorkingDirectory $output -Wait -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError "$log.err"
  $lines = @(Get-Content $log -ErrorAction SilentlyContinue) + @(Get-Content "$log.err" -ErrorAction SilentlyContinue)
  foreach ($l in $lines) { if ($l -and $l -notmatch '^\s*Adding ') { Write-Host "    $l" } }
  $made = (Test-Path $archive) -and ((Get-Item $archive).Length -gt 24)
  $skipped = @($lines | Where-Object { $_ -match '^\s*(Skipping|Skipped file) ' })
  if ($p.ExitCode -ne 0 -and -not ($made -and $skipped.Count -gt 0)) { throw "$label : Archive2 exited with $($p.ExitCode) and no usable archive was made (see $log)" }
  if ($made -and $p.ExitCode -ne 0) { Write-Host "    Archive2 exit code $($p.ExitCode) is only because of the $($skipped.Count) skipped file(s) above; the archive was written." }
  if (-not $made) { throw "$label : Archive2 produced no archive (see $log)" }
  $other = @($skipped | Where-Object { $_ -match '"([^"]+)"' -and $Matches[1] -notmatch '^textures/new_vegas/(interface|fonts)/' })
  if ($skipped.Count) { Add-Content $skipList (@("$label") + $skipped) }
  if ($other.Count) { Write-Warning "$label : $($other.Count) texture(s) outside the Fallout 3 interface art could not be packed and are missing (list: archive2-skipped.txt)" }
}

# Elric over $temp\meshes -> $output\meshes. Elric stops at the first mesh it crashes on, so it is started again for the rest. The mesh it stopped on is the first one without
# an output: it is retried once without any collision (when Elric really crashed), and if it fails again it is dropped and listed in elric-failures.txt.
function Invoke-ElricPass([string]$plugin) {
  $elricDir = "$tool\src\models-and-animations\elric"
  $retried = @{}
  for ($i = 0; $i -lt 200; $i++) {
    $since = (Get-Date).AddSeconds(-2)
    Run "$fo4\Tools\Elric\Elrich.exe" @('.\Settings\PCMeshes.esf', "-ElricOptions.ConvertTarget=`"$temp\meshes`"", "-ElricOptions.OutputDirectory=`"$output\meshes`"") $elricDir
    $crashed = ($script:LastExit -ne 0)
    $failed = $null
    foreach ($f in Get-ChildItem "$temp\meshes" -Recurse -File -ErrorAction SilentlyContinue) {
      $rel = $f.FullName.Substring("$temp\meshes".Length)
      if (Test-Path "$output\meshes$rel") { Remove-Item $f.FullName } else { $failed = $f; break }
    }
    if (-not $failed) { break }
    Remove-ElricDumps $since
    $failedRel = $failed.FullName.Substring("$temp\meshes".Length)
    if ($crashed -and -not $retried.ContainsKey($failedRel)) {
      $retried[$failedRel] = 1
      Write-Host "  Elric crashed on meshes$failedRel : trying it again without any collision" -ForegroundColor Yellow
      [void](Invoke-CapitalPy (Join-Path $root 'worldfix\elric_prep.py') @($failed.FullName, '--all-collision'))
      continue
    }
    Write-Host "  skipped (Elric failed): meshes$failedRel" -ForegroundColor Yellow
    Add-Content $failList "$plugin`t$($failed.FullName.Substring($temp.FullName.Length + 1))"
    Remove-Item $failed.FullName
    # drop already-converted files so the retry only processes the remainder
    Get-ChildItem "$temp\meshes" -Recurse -File | Where-Object { Test-Path ("$output\meshes" + $_.FullName.Substring("$temp\meshes".Length)) } | Remove-Item
  }
}

foreach ($plugin in $Plugins) {
  if (-not $bsaMap.ContainsKey($plugin)) { Write-Warning "Unknown plugin $plugin"; continue }
  $bsas = $bsaMap[$plugin] | ForEach-Object { Join-Path $fo3Data $_ } | Where-Object { Test-Path $_ }
  if (-not $bsas) { Write-Warning "No archives for $plugin"; continue }
  Step "=== $plugin ($($bsas.Count) archives) ==="
  Clear-Work

  Step 'Extracting meshes'
  Run "$tool\bin\bsab\bsab.exe" (@('-e','-f','meshes') + ($bsas | ForEach-Object { "`"$_`"" }) + "`"$extracted`"")
  Step 'Extracting textures'
  $outTex = New-Item -ItemType Directory -Force "$output\textures"
  Run "$tool\bin\bsab\bsab.exe" (@('-e','-f','textures') + ($bsas | ForEach-Object { "`"$_`"" }) + "`"$outTex`"")
  # bsab nests textures\textures; the converter's material paths expect textures\new_vegas
  if (Test-Path "$outTex\textures") {
    if (Test-Path "$outTex\new_vegas") { Copy-Item "$outTex\textures\*" "$outTex\new_vegas" -Recurse -Force; Remove-Item "$outTex\textures" -Recurse -Force }
    else { Rename-Item "$outTex\textures" 'new_vegas' }
  }
  # the Fallout 3 archives also hold files a Fallout 4 texture archive cannot take and the game never reads: font definitions (.fnt .tex) and their atlases, the editor's
  # .psd / .tai / dirinfo.txt files. They used to make Archive2 print an error for every one of them and exit with 1; they are left out here instead.
  $unusable = @(Get-ChildItem $outTex -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -ne '.dds' -or $_.FullName -match '\\new_vegas\\fonts\\' })
  if ($unusable.Count) {
    $unusable | Remove-Item -Force
    Write-Host "  left out $($unusable.Count) Fallout 3 font / editor files (not DDS textures; Fallout 4 never reads them)"
  }

  if (Test-Path "$extracted\meshes") {
    Step 'Converting meshes (NifSkope)'
    Run "$tool\build\nifskope_converter\release\NifSkope.exe" @('--convert', "`"$temp`"", "`"$extracted`"", "`"$extracted`"")

    # Elric (the mesh optimizer) dies with an access violation on a mesh whose collision points at a rigid body without a shape. Fallout 3 has such bodies on 49 meshes
    # (hats, helmets, glasses, the baby carriage, the metro and vault doors ...) and on the 17 that used to be removed here by name: their collision link is cut first
    # (a body without a shape collided with nothing in Fallout 3 either), so every mesh goes through Elric and none is skipped or left unoptimized.
    Step 'Making the meshes safe for Elric'
    $rc = Invoke-CapitalPy (Join-Path $root 'worldfix\elric_prep.py') @("$temp\meshes")
    if ($rc -ne 0) { Write-Warning "elric_prep.py exited with ${rc}: Elric may crash on some meshes (each one is retried below)" }

    Step 'Optimizing meshes (Elric) - a mesh that still crashes it is retried without collision, then skipped'
    Invoke-ElricPass $plugin

    if (Test-Path "$temp\materials") {
      Step 'Moving materials'
      Copy-Item "$temp\materials" $output -Recurse -Force
      Remove-Item "$temp\materials" -Recurse -Force
    }
  }

  if (-not $SkipBa2) {
    Step 'Packing BA2 archives'
    $main = @('meshes','materials') | ForEach-Object { "$output\$_" } | Where-Object { Test-Path $_ }
    if ($main) {
      $mainBa2 = "$output\$plugin - Main.ba2"
      Invoke-Archive2 "$plugin - Main" ((($main | ForEach-Object { "`"$_`"" }) -join ',') , "-create=`"$plugin - Main.ba2`"", "-root=`"$output`"", '-format=General', '-compression=Default', '-maxSizeMB=4095', '-tempFiles') $mainBa2
    }
    if (Test-Path "$output\textures") {
      $texBa2 = "$output\$plugin - Textures.ba2"
      Invoke-Archive2 "$plugin - Textures" @("`"$output\textures`"", "-create=`"$plugin - Textures.ba2`"", "-root=`"$output`"", '-format=DDS', '-compression=Default', '-maxSizeMB=4095', '-tempFiles') $texBa2
    }
    foreach ($d in 'meshes','materials','textures') { Remove-Item "$output\$d" -Recurse -Force -ErrorAction SilentlyContinue }     # only reached when both archives were written
  }
  Clear-Work
  Step "$plugin done"
}
if (Test-Path $failList) { Write-Warning "$((Get-Content $failList).Count) mesh(es) could not be optimized (elric-failures.txt): the loose-meshes step converts them one by one" }
Step 'All asset conversion done. Output:'
Get-ChildItem $output -File | Format-Table Name, @{n='MB';e={[math]::Round($_.Length/1MB)}}
