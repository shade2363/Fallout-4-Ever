"""Lock the placed terminals that are locked in Fallout 3 (hack minigame / Science), in place on tool\\output\\*.esm.

FO3 TERM DNAM = [base hack difficulty (0 very easy .. 4 very hard, 5 = key), flags (0x02 = Unlocked), server type, 0].  xConvert drops the lock and our rebuilt FO4 TERMs have no
lock field, so every terminal was open (audit2 player-systems #5).  A FO4 terminal is locked / hackable through an XLOC on its REFR (12 bytes: level, key, flags).
Levels follow the converter's lock tiers (0 / 25 / 50 / 75 / 100): very easy 0, easy 25, average 50, hard 75, very hard 100; "requires key" has no key record here -> 100.
Idempotent: refs that already carry an XLOC are left alone.   python worldfix\\lock_terminals.py [--dry]"""
import sys, os, struct, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'navmesh'))
from navlib import iter_records, subrecords, sub, record, plugin_header
OUT = r'X:\__CAPITAL_WORKDIR__\tool\output'
SRC = r'X:\__CAPITAL_FO3_DATA__'
PLUGS = ['Fallout3', 'Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta']
LEVEL = {0: 0, 1: 25, 2: 50, 3: 75, 4: 100, 5: 100}
BEFORE = ('XLYR', 'XLKR', 'XOWN', 'XRNK', 'XSCL', 'DATA')           # vanilla order: NAME ... XLOC ... XLYR / XLKR / XOWN / XSCL / DATA
dry = '--dry' in sys.argv

locked = {}                                                                   # (plugin lower, low fid) -> lock level
for p in PLUGS:
    d = open(os.path.join(SRC, p + '.esm'), 'rb').read()
    for r in iter_records(d):
        if r.sig != 'TERM': continue
        dn = dict(subrecords(d, r)).get('DNAM', b'')
        if len(dn) >= 2 and not (dn[1] & 2): locked[(p.lower() + '.esm', r.fid & 0xFFFFFF)] = LEVEL.get(dn[0], 100)
print('locked terminal bases in the FO3 plugins:', len(locked))

total = 0
for p in PLUGS:
    path = os.path.join(OUT, p + '.esm')
    data = open(path, 'rb').read(); masters, _ = plugin_header(data); ms = [m.lower() for m in masters]; me = p.lower() + '.esm'
    patches = {}; skipped = 0
    for r in iter_records(data):
        if r.sig != 'REFR': continue
        if r.flags & 0x40000: skipped += 1; continue
        subs = subrecords(data, r)
        d = dict(subs)
        if 'NAME' not in d or 'XLOC' in d: continue
        b = struct.unpack('<I', d['NAME'])[0]; bi = b >> 24
        lvl = locked.get(((ms[bi] if bi < len(ms) else me), b & 0xFFFFFF))
        if lvl is None: continue
        xloc = struct.pack('<B3xI4s', lvl, 0, bytes(4))
        out = []; done = False
        for k, v in subs:
            if not done and k in BEFORE: out.append(('XLOC', xloc)); done = True
            out.append((k, v))
        if not done: out.append(('XLOC', xloc))
        patches[r.off] = record('REFR', r.fid, [sub(k, v) for k, v in out], flags=r.flags, vc=r.vc, ver=r.ver)
    print('%-13s terminals locked %d (compressed refs skipped %d)' % (p, len(patches), skipped))
    total += len(patches)
    if not patches or dry: continue
    hdr = 24 + struct.unpack_from('<I', data, 4)[0]
    def walk(q, end):
        res = []
        while q < end:
            sig = data[q:q + 4]; size, = struct.unpack_from('<I', data, q + 4)
            if sig == b'GRUP':
                body = walk(q + 24, q + size)
                res.append(data[q:q + 4] + struct.pack('<I', 24 + len(body)) + data[q + 8:q + 24] + body); q += size
            else: res.append(patches.get(q, data[q:q + 24 + size])); q += 24 + size
        return b''.join(res)
    open(path, 'wb').write(data[:hdr] + walk(hdr, len(data)))
print('total', total, '(dry run: nothing written)' if dry else '')
