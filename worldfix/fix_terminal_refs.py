"""Turn and move the placed terminals by +-90 degrees to match the rotated terminal models (add_terminal_screen.py wraps the model so its screen faces -Y).

Idempotent: the new rotation is always (rotation in the original Fallout 3 plugin) + DELTA.  Patches tool/output/*.esm|esp in place for every REFR whose base is a TERM
that uses one of the patched models.  --dry only counts.
  python fix_terminal_refs.py [--delta 90] [--dry]"""
import sys, os, struct, math, collections, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'navmesh'))
from navlib import iter_records, subrecords
OUT = r'X:\__CAPITAL_WORKDIR__\tool\output'
SRC = r'X:\__CAPITAL_FO3_DATA__'
INFO = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'terminal_models.json')))   # model -> {'t': [x, y, z]} written by add_terminal_hybrid.py
MODELS = tuple(INFO)
delta = math.radians(float(sys.argv[sys.argv.index('--delta') + 1]) if '--delta' in sys.argv else 90.0); dry = '--dry' in sys.argv
def masters(d):
    p = 24; end = 24 + struct.unpack_from('<I', d, 4)[0]; m = []
    while p < end:
        sig = d[p:p+4]; sz = struct.unpack_from('<H', d, p + 4)[0]
        if sig == b'MAST': m.append(d[p+6:p+6+sz].rstrip(b'\0').decode('latin1').lower())
        p += 6 + sz
    return m
def owner(fid, ms, me):
    i = fid >> 24
    return (ms[i] if i < len(ms) else me), fid & 0xFFFFFF
files = [f for f in sorted(os.listdir(OUT)) if f.lower().endswith(('.esm', '.esp')) and f.lower() not in ('fallout3.esm.fixed2',)]
data = {f: open(os.path.join(OUT, f), 'rb').read() for f in files}
# 1. TERM identity -> model
term_model = {}
for f in files:
    d = data[f]; ms = masters(d); me = f.lower()
    for r in iter_records(d):
        if r.sig == 'TERM':
            m = dict(subrecords(d, r)).get('MODL', b'').rstrip(b'\0').decode('latin1').lower().replace(chr(92), '/')
            if m.startswith('new_vegas/'): m = m[len('new_vegas/'):]
            term_model[owner(r.fid, ms, me)] = m
targets = {k: m for k, m in term_model.items() if m in MODELS}
print('terminal bases using patched models:', len(targets))
# 2. original rotation of every REFR in the FO3 sources (only the ones we will need are looked up)
srcrot = {}
def load_src(name):
    if name in srcrot: return srcrot[name]
    path = os.path.join(SRC, name); res = {}
    if os.path.exists(path):
        d = open(path, 'rb').read()
        for r in iter_records(d):
            if r.sig == 'REFR':
                s = dict(subrecords(d, r))
                if 'DATA' in s and len(s['DATA']) == 24: res[r.fid & 0xFFFFFF] = struct.unpack_from('<6f', s['DATA'], 0)
        del d
    srcrot[name] = res; return res
total = collections.Counter()
for f in files:
    d = data[f]; ms = masters(d); me = f.lower(); buf = bytearray(d); n = 0; skipped = 0
    for r in iter_records(d):
        if r.sig != 'REFR': continue
        s = dict(subrecords(d, r))
        if 'NAME' not in s: continue
        tm = targets.get(owner(struct.unpack('<I', s['NAME'])[0], ms, me))
        if tm is None: continue
        if r.flags & 0x40000: skipped += 1; continue
        own, low = owner(r.fid, ms, me)
        src = load_src(own).get(low)
        if src is None: skipped += 1; continue                       # a reference created by our plugins: no original transform known
        sx, sy, sz, srx, sry, srz = src
        p = r.off + 24; end = p + r.size
        while p < end:
            sig = bytes(buf[p:p+4]); ssz = struct.unpack_from('<H', buf, p + 4)[0]
            if sig == b'DATA' and ssz == 24:
                new = (srz + delta) % (2 * math.pi); tx, ty, tz = INFO[tm]['t']; c, s_ = math.cos(new), math.sin(new)
                # visual world = pos' + R_b(new) (M v + t) must equal pos + R_b(orig) v  =>  pos' = pos - R_b(new) t   (R_b(a): x' = x cos a + y sin a, y' = -x sin a + y cos a)
                struct.pack_into('<3f', buf, p + 6, sx - (tx * c + ty * s_), sy - (-tx * s_ + ty * c), sz - tz)
                struct.pack_into('<f', buf, p + 6 + 20, new); n += 1; break
            p += 6 + ssz
    total[f] = (n, skipped)
    if n and not dry: open(os.path.join(OUT, f), 'wb').write(bytes(buf))
    if n or skipped: print(f, 'patched', n, 'skipped', skipped)
