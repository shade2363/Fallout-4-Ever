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

function Step($msg) { Write-Host "[$(Get-Date -Format HH:mm:ss)] $msg" -ForegroundColor Cyan }
function Run($exe, $argList, $cwd = $tool) {
  $p = Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $cwd -Wait -NoNewWindow -PassThru
  if ($p.ExitCode -ne 0) { Write-Warning "$([IO.Path]::GetFileName($exe)) exited with $($p.ExitCode)" }
}
function Clear-Work { foreach ($d in $temp, $extracted) { Remove-Item "$d\*" -Recurse -Force -ErrorAction SilentlyContinue } }

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

  if (Test-Path "$extracted\meshes") {
    Step 'Converting meshes (NifSkope)'
    Run "$tool\build\nifskope_converter\release\NifSkope.exe" @('--convert', "`"$temp`"", "`"$extracted`"", "`"$extracted`"")

    # Meshes known to crash Elric on FO3 (from upstream convert.ps1)
    @('architecture\megaton\megatonrampstraightreg.nif','architecture\megaton\megatonrampstraightreg02.nif',
      'architecture\megaton\megatonrampstraightsml.nif','architecture\megaton\megatonrampturn180reg.nif',
      'architecture\urban\streetdressing\busshelter01.nif','architecture\urban\streetdressing\busshelter02.nif',
      'clutter\operatinglight01.nif','clutter\food\apple01.nif','dungeons\vault\halls\vdoor01.nif',
      'dungeons\vaultruined\doors\vdoorr01.nif','vehicles\truck01.nif','vehicles\truck02.nif','vehicles\truck03.nif',
      'vehicles\truck04.nif','vehicles\truck05.nif','vehicles\truck06.nif','weapons\1handminedrop\minefrag.nif') |
      ForEach-Object { Remove-Item "$temp\meshes\new_vegas\$_" -ErrorAction SilentlyContinue }

    Step 'Optimizing meshes (Elric) - retries past meshes that crash it'
    $elricDir = "$tool\src\models-and-animations\elric"
    for ($i = 0; $i -lt 200; $i++) {
      Run "$fo4\Tools\Elric\Elrich.exe" @('.\Settings\PCMeshes.esf', "-ElricOptions.ConvertTarget=`"$temp\meshes`"", "-ElricOptions.OutputDirectory=`"$output\meshes`"") $elricDir
      $failed = $null
      foreach ($f in Get-ChildItem "$temp\meshes" -Recurse -File -ErrorAction SilentlyContinue) {
        $rel = $f.FullName.Substring("$temp\meshes".Length)
        if (Test-Path "$output\meshes$rel") { Remove-Item $f.FullName } else { $failed = $f; break }
      }
      if (-not $failed) { break }
      Write-Host "  skipped (Elric failed): meshes$($failed.FullName.Substring("$temp\meshes".Length))" -ForegroundColor Yellow
      Add-Content "$root\elric-failures.txt" "$plugin`t$($failed.FullName.Substring($temp.FullName.Length + 1))"
      Remove-Item $failed.FullName
      # drop already-converted files so the retry only processes the remainder
      Get-ChildItem "$temp\meshes" -Recurse -File | Where-Object { Test-Path ("$output\meshes" + $_.FullName.Substring("$temp\meshes".Length)) } | Remove-Item
    }

    if (Test-Path "$temp\materials") {
      Step 'Moving materials'
      Copy-Item "$temp\materials" $output -Recurse -Force
      Remove-Item "$temp\materials" -Recurse -Force
    }
  }

  if (-not $SkipBa2) {
    Step 'Packing BA2 archives'
    $a2 = "$fo4\Tools\Archive2\Archive2.exe"
    $main = @('meshes','materials') | ForEach-Object { "$output\$_" } | Where-Object { Test-Path $_ }
    if ($main) { Run $a2 ((($main | ForEach-Object { "`"$_`"" }) -join ',') , "-create=`"$plugin - Main.ba2`"", "-root=`"$output`"", '-format=General', '-compression=Default', '-maxSizeMB=4095', '-tempFiles') $output }
    if (Test-Path "$output\textures") { Run $a2 @("`"$output\textures`"", "-create=`"$plugin - Textures.ba2`"", "-root=`"$output`"", '-format=DDS', '-compression=Default', '-maxSizeMB=4095', '-tempFiles') $output }
    foreach ($d in 'meshes','materials','textures') { Remove-Item "$output\$d" -Recurse -Force -ErrorAction SilentlyContinue }
  }
  Clear-Work
  Step "$plugin done"
}
Step 'All asset conversion done. Output:'
Get-ChildItem $output -File | Format-Table Name, @{n='MB';e={[math]::Round($_.Length/1MB)}}
