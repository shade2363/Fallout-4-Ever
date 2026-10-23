"""Build CapitalFixes.esp: overrides for converted base records that crash the game when spawned (tests\\crashers.txt, from tools-spawn-loop.ps1).
Each listed record is cloned without its model subrecords (MODL/MODT/MODC/MODS/MODF), so it exists but is invisible instead of crashing.
  python fix_crashers.py"""
import struct, sys
sys.path.insert(0, r'X:\__CAPITAL_WORKDIR__\navmesh')
from navlib import iter_records, subrecords, sub, record, group
OUT = r'X:\__CAPITAL_WORKDIR__\tool\output'
plugins = ['Fallout3', 'Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta']
rows = [l.rstrip('\n').split('\t') for l in open(r'X:\__CAPITAL_WORKDIR__\tests\crashers.txt', encoding='utf-8') if l.strip()]
need = {}                                        # (plugin, fid) -> sig
for li, ci, plug, sig, fid, edid in rows:
    need[(plug, int(fid, 16) & 0xFFFFFF)] = sig
used = sorted({p for p, _ in need}, key=plugins.index)
masters = ['Fallout4.esm', 'Fallout3.esm'] + [p + '.esm' for p in used if p != 'Fallout3']
mindex = {p: (1 if p == 'Fallout3' else masters.index(p + '.esm')) for p in used}
recs = {}
MODEL = {'MODL', 'MODT', 'MODC', 'MODS', 'MODF'}
for plug in used:
    d = open(r'%s\%s.esm' % (OUT, plug), 'rb').read()
    own = 1 if plug == 'Fallout3' else 2
    for r in iter_records(d):
        key = (plug, r.fid & 0xFFFFFF)
        if r.sig in ('ACTI', 'CONT', 'STAT', 'MSTT', 'FURN', 'DOOR', 'MISC', 'TERM') and key in need and (r.fid >> 24) == own:
            subs = [sub(k, b) for k, b in subrecords(d, r) if k not in MODEL]
            fid = (mindex[plug] << 24) | (r.fid & 0xFFFFFF)
            recs.setdefault(r.sig, []).append(record(r.sig, fid, subs, flags=r.flags & ~0x40000, ver=r.ver))
n = sum(len(v) for v in recs.values())
print('fixed records:', n, 'of', len(need), 'masters', masters)
body = b''.join(group(sig.encode(), 0, b''.join(v)) for sig, v in sorted(recs.items()))
hs = [sub('HEDR', struct.pack('<fII', 1.0, n, 0x800)), sub('CNAM', b'CapitalConvert' + bytes(1))]
for m in masters:
    hs += [sub('MAST', m.encode() + bytes(1)), sub('DATA', bytes(8))]
open(OUT + r'\CapitalFixes.esp', 'wb').write(record('TES4', 0, hs, ver=131) + body)
print('wrote', OUT + r'\CapitalFixes.esp')
