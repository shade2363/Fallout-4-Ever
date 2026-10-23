# Switch this Fallout 4 install between Capital Convert and whatever else is in it (Solo76 ...): plugins.txt (the active load order) is the only thing swapped.
#   .\capital-profile.ps1 -Capital   saves the current plugins.txt as plugins.txt.pre-capital (unless it already is the Capital list) and writes the Capital load order
#   .\capital-profile.ps1 -Restore   puts plugins.txt.pre-capital back (the other project's load order)
# The Play Capital Wasteland *.bat launchers call -Capital first. Besides plugins.txt this swaps the FO3 main menu files (below); saves and ini are not touched.
param([switch]$Capital, [switch]$Restore)
$pl = Join-Path $env:LOCALAPPDATA 'Fallout4\plugins.txt'
$bak = $pl + '.pre-capital'
$order = 'Fallout3.esm', 'Anchorage.esm', 'ThePitt.esm', 'BrokenSteel.esm', 'PointLookout.esm', 'Zeta.esm', 'XDI.esm', 'CapitalNoBarks.esp', 'F3_Skills.esp', 'F3_Perks.esp', 'CapitalDLCActors.esp', 'CapitalCorpses.esp', 'CapitalActors.esp', 'CapitalNavmesh.esp', 'CapitalNavmeshDLC.esp', 'CapitalQuests.esp', 'CapitalItems.esp', 'CapitalFixes.esp', 'CapitalFurniture.esp', 'CapitalSounds.esp', 'CapitalDialogue.esp', 'CapitalChoices.esp', 'CapitalDLCDialogue.esp', 'CapitalAI.esp', 'CapitalDLCAI.esp', 'CapitalScripts.esp', 'CapitalRadio.esp', 'CapitalAnim.esp', 'CapitalChargen.esp'
$header = '# This file is used by Fallout 4 to keep track of your downloaded content.', '# Please do not modify this file.'
# FO3 main menu (ui\): backdrop video + restyled list. Loose files, so they come in with the Capital profile and go out again on -Restore.
# The vanilla Video\MainMenuLoop.bk2 is only ever RENAMED (to MainMenuLoop.fo4.bk2), never overwritten or deleted. Staged by ui\pack_menu.py.
$menuSrc = Join-Path $PSScriptRoot 'tool\output\menu'
$fo4Data = 'X:\__CAPITAL_FO4__\Data'
function Install-Menu {
  $srcVid = Join-Path $menuSrc 'Video\MainMenuLoop.bk2'
  if (-not (Test-Path $srcVid)) { 'FO3 main menu: nothing staged in tool\output\menu, skipped'; return }
  $vid = Join-Path $fo4Data 'Video\MainMenuLoop.bk2'; $aside = Join-Path $fo4Data 'Video\MainMenuLoop.fo4.bk2'
  try {
    if (-not (Test-Path $aside)) { Rename-Item $vid 'MainMenuLoop.fo4.bk2' -ErrorAction Stop }
    if (-not (Test-Path $vid) -or (Get-Item $vid).Length -ne (Get-Item $srcVid).Length) { Copy-Item $srcVid $vid -Force -ErrorAction Stop }
    foreach ($f in 'MainMenu.swf', 'Translate_en.txt', 'LooksMenu.swf') { Copy-Item (Join-Path $menuSrc "Interface\$f") (Join-Path $fo4Data "Interface\$f") -Force -ErrorAction Stop }
    'FO3 main menu installed (Video\MainMenuLoop.bk2, Interface\MainMenu.swf, Interface\Translate_en.txt)'
  } catch { "FO3 main menu NOT installed (is Fallout 4 running?): $($_.Exception.Message)" }
}
function Remove-Menu {
  $srcVid = Join-Path $menuSrc 'Video\MainMenuLoop.bk2'
  $vid = Join-Path $fo4Data 'Video\MainMenuLoop.bk2'; $aside = Join-Path $fo4Data 'Video\MainMenuLoop.fo4.bk2'
  try {
    if ((Test-Path $aside) -and (Test-Path $srcVid)) {
      if ((Test-Path $vid) -and ((Get-Item $vid).Length -eq (Get-Item $srcVid).Length)) { Remove-Item $vid -Force -ErrorAction Stop }
      if (-not (Test-Path $vid)) { Rename-Item $aside 'MainMenuLoop.bk2' -ErrorAction Stop; 'vanilla Video\MainMenuLoop.bk2 restored' }
    }
    foreach ($f in 'MainMenu.swf', 'Translate_en.txt', 'LooksMenu.swf') {
      $dst = Join-Path $fo4Data "Interface\$f"; $src = Join-Path $menuSrc "Interface\$f"
      if ((Test-Path $dst) -and (Test-Path $src) -and ((Get-Item $dst).Length -eq (Get-Item $src).Length)) { Remove-Item $dst -Force -ErrorAction Stop }
    }
  } catch { "FO3 main menu NOT removed (is Fallout 4 running?): $($_.Exception.Message)" }
}
if ($Restore) {
  if (Test-Path $bak) { Copy-Item $bak $pl -Force; 'plugins.txt restored from plugins.txt.pre-capital' } else { 'no plugins.txt.pre-capital to restore' }
  Remove-Menu
  return
}
if ($Capital) {
  $cur = if (Test-Path $pl) { Get-Content $pl } else { @() }
  $active = @($cur | Where-Object { $_ -match '^\*' } | ForEach-Object { $_.TrimStart('*') })
  $isCapital = ($active.Count -gt 0) -and (-not ($active | Where-Object { $_ -match '^Solo76' })) -and ($active -contains 'CapitalActors.esp') -and ($active -notcontains 'CapLabMode.esp')
  if (-not $isCapital -and (Test-Path $pl)) { Copy-Item $pl $bak -Force; 'saved the current plugins.txt as plugins.txt.pre-capital' }
  Set-Content $pl ($header + ($order | ForEach-Object { "*$_" })) -Encoding ascii
  'plugins.txt = the Capital Convert load order (' + $order.Count + ' plugins)'
  Install-Menu
  return
}
'usage: capital-profile.ps1 -Capital | -Restore'
