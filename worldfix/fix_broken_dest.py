r"""Converted base records whose destructible header (DEST) declares stages but carries NO stage records (DSTD/DSTA) crash the game when they are activated or damaged
(found 2026-10-27 by the DLC quest-stage test: `activate` on the Broken Steel Repulsion Field Control Panel = access violation).  94 records in the six converted esms
(ACTI 55, MSTT 31, TACT 3, DOOR 1, PROJ 4: Rivet City entrance doors, Harold, cars ...).  This removes DEST + DAMC (+ DSTD/DSTA/DSTF/DMDL if any) from exactly those
records, in place, idempotent (backup lab/dest-backup-<stamp>/).
  python worldfix/fix_broken_dest.py [--installed] [--dry]
Run it after every esm (re)build (apply-fixes.ps1 step) and re-copy the esms to Data."""
import os, shutil, struct, sys, time, collections
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh'); sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/actors')
from navlib import iter_records, subrecords
from esp_rewrite import rebuild
R = 'X:/__CAPITAL_WORKDIR__/'; FO4D = 'X:/__CAPITAL_FO4__/Data/'
inst = '--installed' in sys.argv; dry = '--dry' in sys.argv
DROP = {b'DEST', b'DAMC', b'DSTD', b'DSTA', b'DSTF', b'DMDL', b'DMDT', b'DMDC', b'DMDS'}
bk = R + 'lab/dest-backup-' + time.strftime('%Y%m%d-%H%M'); stat = collections.Counter()
def strip(subs): return [(k, v) for k, v in subs if k not in DROP]
for n, ext in [(x, '.esm') for x in ('Fallout3', 'Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta')] + [(x, '.esp') for x in ('CapitalScripts', 'CapitalSounds', 'CapitalFixes', 'CapitalItems')]:      # + the plugins that carry COPIES of converted base records (attach.py copies ACTI/TACT ... into CapitalScripts.esp)
    for base in [R + 'tool/output/'] + ([FO4D] if inst else []):
        p = base + n + ext
        if not os.path.exists(p): continue
        d = open(p, 'rb').read(); edits = {}
        for r in iter_records(d):
            s = subrecords(d, r); keys = [k for k, v in s]
            if 'DEST' in keys:
                dest = dict(s)['DEST']; cnt = dest[4] if len(dest) >= 5 else 0
                if cnt and keys.count('DSTD') + keys.count('DSTA') == 0: edits[r.fid] = strip; stat[r.sig] += 1
        print(p, 'records to fix:', len(edits), flush=True)
        if edits and not dry:
            os.makedirs(bk, exist_ok=True); b = bk + '/' + ('inst_' if base == FO4D else '') + n + ext
            if not os.path.exists(b): shutil.copy(p, b)
            nb = rebuild(d, edits, {b'ACTI', b'MSTT', b'TACT', b'DOOR', b'PROJ'}); open(p, 'wb').write(nb)
print(dict(stat))
