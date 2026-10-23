# Map exported FO3 placed actors (lab\actors\placed.csv + actors.csv) to Fallout 4 leveled actors / NPCs.
#   powershell -File .\build-actor-map.ps1   ->  lab\actors\actors-map.csv, lab\actors\actors-map-report.txt
# Only base-game (FalloutNV.esm in the lab) enabled placements for now; DLC needs full FormIDs in the export.
$ErrorActionPreference = 'Stop'
$dir = Join-Path $PSScriptRoot 'lab\actors'
$base = Import-Csv "$dir\actors.csv" -Delimiter ';'
$fo4 = (Import-Csv "$dir\fo4_actors.csv" -Delimiter ';' | Where-Object { $_.file -eq 'Fallout4.esm' }).edid
$fo4set = @{}; $fo4 | ForEach-Object { $fo4set[$_] = $true }
$byId = @{}; $base | ForEach-Object { $byId[$_.id + '|' + $_.sig] = $_ }

# ordered rules: first regex that matches (against "<baseedid> <name> <race>") wins. Target must exist in Fallout4.esm.
$creature = @(
  @('(?i)dead|corpse|ragdoll|caged|marker|spidermine|spider|alien|chimera|rubble',            $null),
  @('(?i)radroach|roach',                                                                  'LCharRadroach'),
  @('(?i)bloatfly|bloat',                                                                  'LCharBloatfly'),
  @('(?i)molerat|mole',                                                                    'LCharMolerat'),
  @('(?i)radscorp|scorpion',                                                               'LCharRadScorpion'),
  @('(?i)mirelurk',                                                                        'LCharMirelurkAll'),
  @('(?i)deathclaw',                                                                       'LCharDeathclaw'),
  @('(?i)yao',                                                                             'LCharYaoGuai'),
  @('(?i)brahmin',                                                                         'EncBrahminTemplate'),
  @('(?i)raider.?dog',                                                                     'LCharRaiderDog'),
  @('(?i)dog|hound',                                                                       'LCharViciousDog'),
  @('(?i)centaur',                                                                         'LCharMutantHound'),
  @('(?i)feral|ghoul|trog',                                                                'LCharFeralGhoul'),
  @('(?i)minigun',                                                                         'LCharSuperMutantMinigun'),
  @('(?i)supermutant.*melee|melee.*supermutant',                                           'LCharSuperMutantMelee'),
  @('(?i)supermutant|super mutant|mutant',                                                 'LCharSupermutantMixedWeapons'),
  @('(?i)\bant\b|ant$|lvlant|forager|fireant',                                             'LCharRadroach'),
  @('(?i)eyebot',                                                                          'EncEyeBot'),
  @('(?i)turret',                                                                          'LCharTurretTripod'),
  @('(?i)sentry',                                                                          'LCharSentryBot'),
  @('(?i)assaultron',                                                                      'LCharAssaultron'),
  @('(?i)gutsy',                                                                           'LCharMrGutsy'),
  @('(?i)handy',                                                                           'LCharMrHandy_Random'),
  @('(?i)robot|protectron|robco|robobrain|combatdroid|maintenance',                         'LCharProtectron'),
  @('(?i)wasteland|critter|random',                                                        '*WASTELAND')
)
$human = @(
  @('(?i)dead|corpse|^loot\d|ragdoll|captive|dummy|test',                                  $null),
  @('(?i)enclave|talon|mercenary|merc\b|hunter|slaver|hitsquad.*talon|ffhitsquaddctalon',    'LCharGunner'),
  @('(?i)raider|lunatic|insane|scavenger',                                                 'LCharRaider'),
  @('(?i)regulator|ffhitsquaddcreg',                                                       'LCharMinutemen'),
  @('(?i)brotherhood|paladin|knight|scribe|outcast|elder',                                 'LCharBoSSoldier'),
  @('(?i)guard|security|sheriff|police|soldier',                                           '*GUARD'),
  @('(?i)ghoul',                                                                           'LCharRaiderGhoulFaceAndGender')
)
# Fallout 4 cannot place a leveled list (LVLN) directly: ACHR -> LVLN crashes the game at load. Vanilla places NPC_ records
# whose template is the leveled list (Lvl*), so translate every LChar* target to such an NPC_.
$toNpc = @{
  'LCharFeralGhoul' = 'LvlFeralGhoul'; 'LCharRaider' = 'LvlRaider'; 'LCharViciousDog' = 'LvlViciousDog'
  'LCharWorkshopNPCMale' = 'WorkshopNPC'; 'LCharWorkshopNPCFemale' = 'WorkshopNPC'
  'LCharGunner' = 'LvlGunner'; 'LCharRaiderGhoulFaceAndGender' = 'LvlTriggermanGhoulOnly'
  'LCharTurretTripod' = 'LvlTurretTripod'; 'LCharProtectron' = 'LvlProtectron'
  'LCharBoSSoldier' = 'LvlBoSSoldier_CombatArmor_Semi'; 'LCharMrHandy_Random' = 'LvlMrHandy_Random'
  'LCharRadroach' = 'LvlRadRoach'; 'LCharMolerat' = 'LvlMolerat'; 'LCharMirelurkAll' = 'LvlMirelurkAll'
  'LCharSupermutantMixedWeapons' = 'LvlSupermutantAllRanged'; 'LCharSuperMutantMelee' = 'LvlSupermutantMelee'
  'LCharSuperMutantMinigun' = 'LvlSupermutantMinigun'; 'LCharWorkshopGuardMale' = 'WorkshopNPCGuard'
  'LCharWorkshopGuardFemale' = 'WorkshopNPCGuard'; 'LCharMutantHound' = 'LvlMutantHound'; 'LCharYaoGuai' = 'LvlYaoGuai'
  'LCharRadScorpion' = 'LvlRadscorpion'; 'LCharDeathclaw' = 'LvlDeathclaw'; 'LCharBloatfly' = 'LvlBloatfly'
  'LCharSentryBot' = 'LvlSentryBot'; 'LCharMrGutsy' = 'LvlMrGutsy'; 'LCharMinutemen' = 'LvlMinuteman'
  'LCharRaiderDog' = 'LvlRaiderDog'; 'LCharAssaultron' = 'LvlAssaultron'
}
$npcOk = @{}; (Import-Csv "$dir\fo4_npc_templates.csv" -Delimiter ';').edid | ForEach-Object { $npcOk[$_] = $true }
$wasteland = 'LCharRadroach', 'LCharMolerat', 'LCharBloatfly', 'LCharViciousDog', 'LCharRadScorpion'

function Pick($rules, $key, $refid, $sex) {
  foreach ($r in $rules) {
    if ($key -match $r[0]) {
      $t = $r[1]
      if ($null -eq $t) { return $null }
      if ($t -eq '*WASTELAND') { return $wasteland[[Convert]::ToInt32($refid, 16) % $wasteland.Count] }
      if ($t -eq '*GUARD') { if ($sex -eq 'F') { return 'LCharWorkshopGuardFemale' } else { return 'LCharWorkshopGuardMale' } }
      return $t
    }
  }
  return '*DEFAULT'
}

$out = New-Object Collections.Generic.List[string]
$out.Add('header placeholder')
$stat = @{}; $unmapped = @{}
$placed = Import-Csv "$dir\placed.csv" -Delimiter ';' | Where-Object { $_.file -eq 'FalloutNV.esm' }
foreach ($p in $placed) {
  if (([int]$p.recflags -band 0x800) -ne 0) { $stat['skipped: initially disabled']++; continue }
  $npc = $byId[$p.baseid + '|NPC_']; $crea = $byId[$p.baseid + '|CREA']
  $rec = if ($npc) { $npc } else { $crea }
  $name = if ($rec) { $rec.name } else { '' }; $race = if ($rec) { $rec.race } else { '' }; $sex = if ($rec) { $rec.sex } else { 'M' }
  $key = "$($p.baseedid) $name $race"
  if ($p.sig -eq 'ACRE') { $t = Pick $creature $key $p.refid $sex; if ($t -eq '*DEFAULT') { $t = $null; $unmapped[$p.baseedid]++ } }
  else {
    $t = Pick $human $key $p.refid $sex
    if ($t -eq '*DEFAULT') { $t = if ($sex -eq 'F') { 'LCharWorkshopNPCFemale' } else { 'LCharWorkshopNPCMale' } }
  }
  if ($null -eq $t) { $stat["skipped: no mapping/ignored ($($p.sig))"]++; continue }
  if ($toNpc.ContainsKey($t)) { $t = $toNpc[$t] }
  if (-not $npcOk[$t]) { $stat["skipped: no NPC_ target ($t)"]++; continue }
  $stat["mapped -> $t"]++
  # exterior refs are filed by the map grid cell containing their position (FO3's worldspace persistent cell has no grid)
  $gx = ''; $gy = ''; $wid = ''
  if ($p.world) {
    $gx = [int][math]::Floor([double]$p.x / 4096); $gy = [int][math]::Floor([double]$p.y / 4096)
    $wid = ($p.world -split ':')[1]
    $key = "W$wid,$gx,$gy"
  } else { $key = "I$($p.cellid)" }
  $out.Add(($key, $p.refid, $p.cellid, $wid, $gx, $gy, $t, $p.x, $p.y, $p.z, $p.rx, $p.ry, $p.rz, $p.scale, $p.baseedid) -join ';')
}
# sort by target cell so the xEdit script creates each cell override once
$hdr = 'key;refid;cellid;worldid;gx;gy;fo4edid;x;y;z;rx;ry;rz;scale;srcbase'
$rows = $out | Select-Object -Skip 1 | Sort-Object { ($_ -split ';')[0] }
(@($hdr) + $rows) | Set-Content "$dir\actors-map.csv" -Encoding ascii
$rep = @("placements considered: $($placed.Count); written: $($out.Count - 1)", '') + ($stat.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { "{0,5}  {1}" -f $_.Value, $_.Key }) + @('', 'unmapped creature bases (top):') + ($unmapped.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 25 | ForEach-Object { "{0,5}  {1}" -f $_.Value, $_.Key })
$rep | Set-Content "$dir\actors-map-report.txt"
$rep
