# Post-conversion repairs for the converter's plugin output (run after xConvert, before install-output.ps1).
#   powershell -ExecutionPolicy Bypass -File worldfix\apply-fixes.ps1
# Reads the RAW converter output from lab\worldfix\raw\ (seeded on first run from tool\output / lab\worldfix\backup) and writes the fixed
# plugins into tool\output\:
#   1. Fallout3.esm : fix_stub_cells.py  - ~35,000 exterior cells xConvert wrote as stub interior cells go back into their worldspaces
#   1b. Fallout3.esm: restore_refs.py    - map markers, bottle caps and refs in unconverted cells that xConvert dropped are put back
#   1c. 5 DLC .esm  : restore_actors.py  - DLC actors (dropped by xConvert) re-added as vanilla-FO4 leveled NPCs at their original spots
#   2. all 6 .esm   : fix_regions.py    - RDAT 6->8 bytes, stray ICON dropped, Border Region flag cleared (FO4 refuses travel into a border region)
#   3. all 6 .esm   : fix_enable_state.py - XESP enable parents were stripped by xConvert, so quest-state objects (destroyed Megaton ...) all
#                     showed at once; their initial disabled state is baked into the 'Initially Disabled' record flag
#   4. all 6 .esm   : fix_interior_lighting.py - zero ambient-cube colours in interior XCLL made every actor a black silhouette
# CapitalActors.esp is untouched.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$raw = Join-Path $root 'lab\worldfix\raw'
$out = Join-Path $root 'tool\output'
$fo3src = 'X:\__CAPITAL_FO3_DATA__\Fallout3.esm'
New-Item -ItemType Directory -Force $raw | Out-Null
$esms = 'Fallout3.esm', 'Anchorage.esm', 'ThePitt.esm', 'BrokenSteel.esm', 'PointLookout.esm', 'Zeta.esm'
foreach ($n in $esms) {
  $dst = Join-Path $raw $n
  if (-not (Test-Path $dst)) {
    $seed = if ($n -eq 'Fallout3.esm') { Join-Path $root 'lab\worldfix\backup\Fallout3.esm.before-cellfix' } else { Join-Path $out $n }
    Copy-Item $seed $dst
    "seeded raw $n"
  }
}
$work = Join-Path $root 'lab\worldfix\work'; New-Item -ItemType Directory -Force $work | Out-Null
python (Join-Path $PSScriptRoot 'fix_stub_cells.py') --conv (Join-Path $raw 'Fallout3.esm') --src $fo3src --out (Join-Path $work 'Fallout3.cells.esm')
python (Join-Path $PSScriptRoot 'restore_refs.py') --src $fo3src --in (Join-Path $work 'Fallout3.cells.esm') --out (Join-Path $work 'Fallout3.refs.esm')
python (Join-Path $PSScriptRoot 'fix_regions.py') --in (Join-Path $work 'Fallout3.refs.esm') --out (Join-Path $work 'Fallout3.regions.esm') --clear-border
python (Join-Path $PSScriptRoot 'fix_enable_state.py') --src $fo3src --in (Join-Path $work 'Fallout3.regions.esm') --out (Join-Path $out 'Fallout3.esm')
$fo3data = Split-Path $fo3src -Parent
foreach ($n in $esms | Where-Object { $_ -ne 'Fallout3.esm' }) {
  python (Join-Path $PSScriptRoot 'fix_regions.py') --in (Join-Path $raw $n) --out (Join-Path $work "$n.regions") --clear-border
  python (Join-Path $PSScriptRoot 'restore_actors.py') --src (Join-Path $fo3data $n) --src-base $fo3src --in (Join-Path $work "$n.regions") --out (Join-Path $work "$n.actors")
  python (Join-Path $PSScriptRoot 'fix_enable_state.py') --src (Join-Path $fo3data $n) --master-src $fo3src --in (Join-Path $work "$n.actors") --out (Join-Path $out $n)
}
# 4. all 6 .esm: fix_interior_lighting.py - interior XCLL ambient cube colours were zero => actors black in interiors
foreach ($n in $esms) {
  $f = Join-Path $out $n; $t = Join-Path $work "$n.lit"
  python (Join-Path $PSScriptRoot 'fix_interior_lighting.py') --in $f --out $t
  Copy-Item $t $f -Force
}
# The Capital*.esp plugins carry full copies of cell records (actor placement / navmesh overrides) that win over the esm: patch their lighting too
foreach ($n in 'CapitalActors.esp', 'CapitalNavmesh.esp') {
  $f = Join-Path $out $n; if (-not (Test-Path $f)) { continue }
  $t = Join-Path $work "$n.lit"
  python (Join-Path $PSScriptRoot 'fix_interior_lighting.py') --in $f --out $t
  Copy-Item $t $f -Force
}
'done: fixed plugins written to tool\output'
