"""Which MODL meshes referenced by the converted plugins do not exist (neither in the converted BA2s nor loose)?
  python audit_meshes.py [--detail Vault101]   -> counts per record type + list of missing meshes (with example EDIDs)"""
import sys, os, struct, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'navmesh'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navlib import iter_records, subrecords
from ba2_extract import open_ba2
OUT = r'X:\__CAPITAL_WORKDIR__\tool\output'
names = set()
for f in os.listdir(OUT):
    if f.lower().endswith(' - main.ba2'):
        _, n, _ = open_ba2(os.path.join(OUT, f)); names.update(x.lower().replace(chr(92), '/') for x in n)
loose = os.path.join(OUT, 'loose')
for root, _, files in os.walk(loose):
    for fn in files:
        names.add(os.path.relpath(os.path.join(root, fn), loose).lower().replace(chr(92), '/'))
fo4 = r'X:\__CAPITAL_FO4__\Data'
miss = collections.defaultdict(list); total = 0
for esm in ('Fallout3.esm', 'Anchorage.esm', 'ThePitt.esm', 'BrokenSteel.esm', 'PointLookout.esm', 'Zeta.esm', 'CapitalItems.esp', 'CapitalActors.esp'):
    d = open(os.path.join(OUT, esm), 'rb').read()
    for r in iter_records(d):
        if r.sig in ('REFR', 'ACHR', 'ACRE', 'CELL', 'LAND', 'NAVM', 'WRLD', 'NAVI', 'PGRE', 'PMIS', 'INFO', 'DIAL', 'QUST'): continue
        try: s = subrecords(d, r)
        except Exception: continue
        edid = ''
        for k, v in s:
            if k == 'EDID': edid = v.rstrip(bytes(1)).decode('latin1')
            if k == 'MODL' and len(v) > 4:
                p = v.rstrip(bytes(1)).decode('latin1').lower().replace(chr(92), '/')
                total += 1
                if ('meshes/' + p) not in names and not os.path.exists(os.path.join(fo4, 'Meshes', *p.split('/'))):
                    miss[p].append((esm, r.sig, hex(r.fid), edid))
print('MODL refs:', total, ' missing distinct meshes:', len(miss), ' records affected:', sum(len(v) for v in miss.values()))
bysig = collections.Counter(x[1] for v in miss.values() for x in v); print(dict(bysig))
for p, v in sorted(miss.items(), key=lambda kv: -len(kv[1])):
    print(len(v), p, v[0])
