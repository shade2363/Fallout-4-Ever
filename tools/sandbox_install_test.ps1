# Sandbox install test: install the build into a THROW-AWAY folder (never your game), check it, reinstall, uninstall, and prove the uninstall is exact.
#   powershell -ExecutionPolicy Bypass -File tools\sandbox_install_test.ps1 -Work D:\work [-Sandbox D:\sbx]
# -Work = the work folder of a finished build (the folder that holds install-output.ps1 and tool\output).  Exit code 0 = all checks passed.
param([Parameter(Mandatory = $true)][string]$Work, [string]$Sandbox = (Join-Path ([IO.Path]::GetTempPath()) 'f4ever-sandbox'))
$ErrorActionPreference = 'Stop'
$script:fails = @()
function Check($name, $ok, $detail = '') { if ($ok) { Write-Host ("PASS  " + $name) } else { Write-Host ("FAIL  " + $name + $(if ($detail) { '  - ' + $detail })); $script:fails += $name } }
$ps1 = Join-Path $Work 'install-output.ps1'; $out = Join-Path $Work 'tool\output'
if (-not (Test-Path $ps1) -or -not (Test-Path $out)) { throw "not a finished work folder: $Work" }
Remove-Item $Sandbox -Recurse -Force -ErrorAction SilentlyContinue
$data = Join-Path $Sandbox 'Data'; $my = Join-Path $Sandbox 'MyGames'
New-Item -ItemType Directory -Force (Join-Path $data 'Meshes\Capital'), (Join-Path $data 'Sound\fo3'), $my | Out-Null
'someone elses file' | Set-Content (Join-Path $data 'Meshes\Capital\keep1.txt'); 'someone elses file' | Set-Content (Join-Path $data 'Sound\fo3\keep2.txt')
[IO.File]::WriteAllText((Join-Path $my 'Fallout4Prefs.ini'), "[Launcher]`r`nbEnableFileSelection=0`r`n[Display]`r`niSize W=1920`r`n")
$prefsBefore = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $my 'Fallout4Prefs.ini')))
function Run($more) { & powershell -NoProfile -ExecutionPolicy Bypass -File $ps1 -Sandbox $Sandbox -OutDir $out @more 2>&1 | Out-String }

$t = Run @(); $m = [regex]::Match($t, 'Done: (\d+) files copied.*?(\d+) failed')
Check 'install finishes without failures' ($m.Success -and [int]$m.Groups[1].Value -gt 300 -and [int]$m.Groups[2].Value -eq 0) $t.Substring([Math]::Max(0, $t.Length - 300))
foreach ($f in 'Fallout3.esm', 'Anchorage.esm', 'ThePitt.esm', 'BrokenSteel.esm', 'PointLookout.esm', 'Zeta.esm', 'CapitalActors.esp', 'CapitalNavmesh.esp', 'CapitalFixes.esp', 'CapitalStart.esp', 'Scripts\CapStartDemo.pex', 'Scripts\Fragments\Quests\QF_MQ101_0001ED86.pex', 'Video\F3Blank.bik') {
  Check ("installed: $f") (Test-Path (Join-Path $data $f)) }
$frag = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes((Join-Path $data 'Scripts\Fragments\Quests\QF_MQ101_0001ED86.pex')))
Check 'the installed intro script is ours, not the game original' ($frag.Contains('F4EVER') -and -not $frag.Contains('Fade the game in'))
$pl = Get-Content (Join-Path $Sandbox 'LocalAppData\Fallout4\plugins.txt') -ErrorAction SilentlyContinue
$want = 'Fallout3.esm', 'Anchorage.esm', 'ThePitt.esm', 'BrokenSteel.esm', 'PointLookout.esm', 'Zeta.esm', 'CapitalActors.esp', 'CapitalNavmesh.esp', 'CapitalFixes.esp', 'CapitalStart.esp'
$got = @($pl | Where-Object { $_ -match '^\*' } | ForEach-Object { $_.TrimStart('*') })
Check 'plugins.txt enables exactly the demo plugins, in order' (($got -join ',') -eq ($want -join ',')) ($got -join ',')
Check 'Fallout4Custom.ini created with the loose-file settings' ((Get-Content (Join-Path $my 'Fallout4Custom.ini') -Raw -ErrorAction SilentlyContinue) -match 'bInvalidateOlderFiles=1')
Check 'Fallout4Prefs.ini now enables plugin selection' ((Get-Content (Join-Path $my 'Fallout4Prefs.ini') -Raw) -match 'bEnableFileSelection=1')
$noGame = @(Get-ChildItem $data -Recurse -File | Where-Object { $_.Extension -in '.exe', '.dll' }).Count
Check 'no programs were installed into Data' ($noGame -eq 0)

$t = Run @(); Check 'a second install copies nothing new' ($t -match 'Done: 0 files copied') $t.Substring([Math]::Max(0, $t.Length - 200))
$t = Run @('-Uninstall'); $m = [regex]::Match($t, 'Uninstalled: (\d+) files removed.*?(\d+) failed')
Check 'uninstall removes files without failures' ($m.Success -and [int]$m.Groups[1].Value -gt 300 -and [int]$m.Groups[2].Value -eq 0) $t.Substring([Math]::Max(0, $t.Length - 300))
$left = @(Get-ChildItem $data -Recurse -File | Where-Object { $_.Name -notin 'keep1.txt', 'keep2.txt' })
Check 'nothing of ours is left behind' ($left.Count -eq 0) (($left | Select-Object -First 3 | ForEach-Object Name) -join ', ')
Check "someone else's files in the same folders survive" ((Test-Path (Join-Path $data 'Meshes\Capital\keep1.txt')) -and (Test-Path (Join-Path $data 'Sound\fo3\keep2.txt')))
Check 'Fallout4Prefs.ini is byte-identical to before' ([Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $my 'Fallout4Prefs.ini'))) -eq $prefsBefore)
Check 'Fallout4Custom.ini created by the install is removed again' (-not (Test-Path (Join-Path $my 'Fallout4Custom.ini')))
Remove-Item $Sandbox -Recurse -Force -ErrorAction SilentlyContinue
if ($script:fails.Count) { Write-Host ("`nFAILED: " + ($script:fails -join '; ')); exit 1 } else { Write-Host "`nALL PASSED"; exit 0 }
