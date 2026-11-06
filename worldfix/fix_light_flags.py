r"""Converted LIGH records lost their FO3 flags and carry near-clip 0: all 368 base-game lights had flags 0 / near clip 0, while 98% of vanilla FO4 lights set flag bit 0x1 and
97% have a near clip (7.22 most common) and every vanilla light has Scalar 1.0 / Exponent 2.0 (converted: both 0).  The converter also dropped FO3 flicker-slow (0x40), pulse-slow (0x100) and moved spot-light.  This rebuilds the DATA flags from the FO3 original
(matched by EDID) and sets the near clip:   fo4 flags = (fo3 & 0x1FF) | 0x1 | (0x400 if fo3 spot light 0x200),  near clip 7.22 (omni) .
Idempotent, in place on tool\output (backup lab/light-backup-<stamp>/).
  python worldfix/fix_light_flags.py [--installed] [--dry] [--clip 7.22] [--noflag]"""
import os, shutil, struct, sys, time, collections
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh'); sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/actors')
from navlib import iter_records, subrecords
from esp_rewrite import rebuild
R = 'X:/__CAPITAL_WORKDIR__/'; FO4D = 'X:/__CAPITAL_FO4__/Data/'; FO3D = 'X:/__CAPITAL_FO3_DATA__/'
inst = '--installed' in sys.argv; dry = '--dry' in sys.argv; noflag = '--noflag' in sys.argv
clip = float(sys.argv[sys.argv.index('--clip') + 1]) if '--clip' in sys.argv else 7.22
bk = R + 'lab/light-backup-' + time.strftime('%Y%m%d-%H%M'); stat = collections.Counter()
for n in ('Fallout3', 'Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta'):
    src = open(FO3D + n + '.esm', 'rb').read(); fo3 = {}
    for r in iter_records(src):
        if r.sig == 'LIGH':
            s = dict(subrecords(src, r)); fo3[s['EDID'].rstrip(b'\0')] = struct.unpack_from('<I', s['DATA'], 12)[0]
    for base in [R + 'tool/output/'] + ([FO4D] if inst else []):
        p = base + n + '.esm'
        if not os.path.exists(p): continue
        d = open(p, 'rb').read(); edits = {}
        for r in iter_records(d):
            if r.sig != 'LIGH': continue
            e = dict(subrecords(d, r))['EDID'].rstrip(b'\0')
            if e not in fo3: stat['no FO3 match'] += 1; continue
            f3 = fo3[e]
            def fix(subs, f3=f3):
                out = []
                for k, v in subs:
                    if k == b'DATA' and len(v) >= 28:
                        v = bytearray(v); fl = struct.unpack_from('<I', v, 12)[0]
                        if not noflag: struct.pack_into('<I', v, 12, (f3 & 0x1FF) | 1 | (0x400 if f3 & 0x200 else 0) | (fl & 0xFFFFFC00 & ~0x400))
                        struct.pack_into('<f', v, 24, clip)
                        if len(v) >= 64:                                       # FO4 attenuation: scalar 1, exponent 2 (vanilla; the converter left both 0 = degenerate falloff / hard-edged circles)
                            struct.pack_into('<3f', v, 40, 0.0, 1.0, 2.0)
                            if f3 & (0x08 | 0x80) and struct.unpack_from('<f', v, 28)[0] == 0: struct.pack_into('<3f', v, 28, 0.5, 0.5, 0.0)   # flicker / pulse timing
                        v = bytes(v)
                    out.append((k, v))
                return out
            edits[r.fid] = fix; stat['lights'] += 1
        print(p, 'lights to fix:', len(edits), flush=True)
        if edits and not dry:
            os.makedirs(bk, exist_ok=True); b = bk + '/' + ('inst_' if base == FO4D else '') + n + '.esm'
            if not os.path.exists(b): shutil.copy(p, b)
            open(p, 'wb').write(rebuild(d, edits, {b'LIGH'}))
print(dict(stat))
