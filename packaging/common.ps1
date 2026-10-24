# Shared helpers for the packaging / install / build-all scripts (dot-source: . "$PSScriptRoot\packaging\common.ps1").
# Windows PowerShell 5.1 compatible. Nothing in here writes anywhere.

function Get-SteamLibraries {
  $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
  if (-not $steam) { return @() }
  $libs = @($steam -replace '/', '\')
  $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
  if (Test-Path $vdf) {
    $libs += @(Get-Content $vdf | Select-String '"path"\s+"([^"]+)"' | ForEach-Object { $_.Matches[0].Groups[1].Value -replace '\\\\', '\' })
  }
  return @($libs | Select-Object -Unique)
}

function Find-GameFolder([string]$RegKey, [string[]]$SteamDirs, [string]$MustHave) {
  $p = try { Get-ItemPropertyValue "HKLM:\SOFTWARE\Wow6432Node\Bethesda Softworks\$RegKey" -Name 'installed path' -ErrorAction Stop } catch { $null }
  if ($p -and (Test-Path (Join-Path $p $MustHave))) { return $p.TrimEnd('\') }
  foreach ($l in Get-SteamLibraries) { foreach ($d in $SteamDirs) { $c = Join-Path $l "steamapps\common\$d"; if (Test-Path (Join-Path $c $MustHave)) { return $c } } }
  return $null
}

# Fallout 4 install folder (env FO4_DIR wins), $null when not found
function Get-Fo4Root {
  if ($env:FO4_DIR -and (Test-Path (Join-Path $env:FO4_DIR 'Data\Fallout4.esm'))) { return $env:FO4_DIR.TrimEnd('\') }
  $r = Find-GameFolder 'Fallout4' @('Fallout 4') 'Data\Fallout4.esm'
  if ($r) { return $r }
  $d = 'X:\__CAPITAL_FO4__'
  if (Test-Path (Join-Path $d 'Data\Fallout4.esm')) { return $d }
  return $null
}

# Fallout 3 Data folder (env FO3_DATA wins), $null when not found
function Get-Fo3Data {
  if ($env:FO3_DATA -and (Test-Path (Join-Path $env:FO3_DATA 'Fallout3.esm'))) { return $env:FO3_DATA.TrimEnd('\') }
  $r = Find-GameFolder 'fallout3' @('Fallout 3 goty', 'Fallout 3') 'Data\Fallout3.esm'
  if ($r) { return (Join-Path $r 'Data') }
  $d = 'X:\__CAPITAL_FO3_DATA__'
  if (Test-Path (Join-Path $d 'Fallout3.esm')) { return $d }
  return $null
}

# Runs one of our python scripts and returns its exit code (its output goes to the host). The packaged program has no python on the PATH: it runs scripts itself
# ("CapitalConvert.exe --script file.py ...") and tells the PowerShell steps how through CAPITAL_PY (+ CAPITAL_PY_ARGS); a source checkout uses the python on the PATH.
function Invoke-CapitalPy([string]$Script, [string[]]$ScriptArgs = @()) {
  if ($env:CAPITAL_PY) {
    $pre = @(); if ($env:CAPITAL_PY_ARGS) { $pre = @($env:CAPITAL_PY_ARGS) }
    & $env:CAPITAL_PY @pre $Script @ScriptArgs | ForEach-Object { Write-Host $_ }
  } else {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { throw 'python was not found: run this through CapitalConvert.exe, or install Python 3 when working from a source checkout.' }
    & $py.Source -I $Script @ScriptArgs | ForEach-Object { Write-Host $_ }
  }
  return $LASTEXITCODE
}

function Get-Archive2Path([string]$Override) {
  if ($Override) { if (Test-Path $Override) { return $Override } else { throw "Archive2.exe not found at $Override" } }
  if ($env:ARCHIVE2_EXE -and (Test-Path $env:ARCHIVE2_EXE)) { return $env:ARCHIVE2_EXE }
  $fo4 = Get-Fo4Root
  if ($fo4) { $a = Join-Path $fo4 'Tools\Archive2\Archive2.exe'; if (Test-Path $a) { return $a } }
  throw 'Archive2.exe not found (install the Fallout 4 Creation Kit from Steam, or set ARCHIVE2_EXE).'
}

# Signature of a set of source folders below $LooseDir: sha256 over "relpath|size|mtime-ticks" of every file. Used to decide whether a staged archive is still fresh.
function Get-SourceSig([string]$LooseDir, [string[]]$Sources) {
  $base = (Resolve-Path $LooseDir).Path.TrimEnd('\')
  $lines = New-Object 'System.Collections.Generic.List[string]'
  $bytes = [int64]0
  foreach ($s in $Sources) {
    $d = Join-Path $base $s
    if (-not (Test-Path $d)) { continue }
    foreach ($f in [IO.Directory]::EnumerateFiles($d, '*', [IO.SearchOption]::AllDirectories)) {
      $fi = New-Object IO.FileInfo $f
      $lines.Add($f.Substring($base.Length + 1).ToLowerInvariant() + '|' + $fi.Length + '|' + $fi.LastWriteTimeUtc.Ticks)
      $bytes += $fi.Length
    }
  }
  $lines.Sort([StringComparer]::Ordinal)
  $sha = [Security.Cryptography.SHA256]::Create()
  $h = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes(($lines -join "`n")))).Replace('-', '').ToLowerInvariant()
  return [pscustomobject]@{ Sig = $h; Files = $lines.Count; Bytes = $bytes }
}

function Format-Size([double]$b) {
  if ($b -ge 1GB) { return ('{0:N2} GB' -f ($b / 1GB)) }
  if ($b -ge 1MB) { return ('{0:N1} MB' -f ($b / 1MB)) }
  return ('{0:N0} KB' -f ($b / 1KB))
}

# the stage description written by packaging\pack_ba2.ps1 (tool\output\ba2-stage\stage.json); $null when absent
function Read-StageInfo([string]$StageDir) {
  $p = Join-Path $StageDir 'stage.json'
  if (-not (Test-Path $p)) { return $null }
  try { return (Get-Content $p -Raw | ConvertFrom-Json) } catch { return $null }
}
