"""Place the Fallout 3 actors that start DISABLED (ambush raiders, Vault 106 visions, Moriarty's customers, quest-spawned guards ...) into CapitalActors.esp.

FO3 scripts bring them in with `Ref.Enable`; build-actor-map.ps1 / the xEdit placer skipped every actor with the 'initially disabled' flag, so those scripts had nothing to enable.
Each disabled ACHR / ACRE is mapped with the same rule sets as worldfix/restore_actors.py (human / creature -> vanilla FO4 leveled NPC_), placed at its original position with the
'initially disabled' flag (0x800) in the same cell (the cell is added to the plugin as an override copied from the converted Fallout3.esm when CapitalActors.esp has none yet).
Run AFTER actors/name_actors.py (it rewrites CapitalActors.esp from the .orig); refuses to run twice.
  python place_disabled_actors.py [--plugin tool\\output\\CapitalActors.esp]"""
import argparse, collections, math, re, struct, sys, os
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records, subrecords, sub, plugin_header, record_bytes
ap = argparse.ArgumentParser()
ap.add_argument('--plugin', default='X:/__CAPITAL_WORKDIR__/tool/output/CapitalActors.esp')
ap.add_argument('--src', default='X:/__CAPITAL_FO3_DATA__/Fallout3.esm')
ap.add_argument('--conv', default='X:/__CAPITAL_WORKDIR__/tool/output/Fallout3.esm')
ap.add_argument('--fo4', default='X:/__CAPITAL_FO4__/Data/Fallout4.esm')
a = ap.parse_args()
def log(m): print(m, flush=True)

# ---- rule sets shared with restore_actors.py (WASTELAND / CREATURE / HUMAN / pick)
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'restore_actors.py'), encoding='utf-8').read()
_ns = {'re': re}
exec(_src[_src.index('WASTELAND = ['):_src.index('# ------------------------------------------------------------------ source info')], _ns)
pick = _ns['pick']; CREATURE = _ns['CREATURE']; HUMAN = _ns['HUMAN']

fo4 = open(a.fo4, 'rb').read(); fo4_npc = {}
for r in iter_records(fo4):
    if r.sig == 'NPC_':
        for k, b in subrecords(fo4, r):
            if k == 'EDID': fo4_npc[b.rstrip(bytes(1)).decode('latin1')] = r.fid; break
del fo4

src = open(a.src, 'rb').read()
race = {}; npcs = {}
for r in iter_records(src):
    if r.sig == 'RACE': race[r.fid & 0xFFFFFF] = dict(subrecords(src, r)).get('EDID', bytes(1)).rstrip(bytes(1)).decode('latin1')
for r in iter_records(src):
    if r.sig in ('NPC_', 'CREA'):
        s = dict(subrecords(src, r))
        rk = race.get(struct.unpack('<I', s['RNAM'])[0] & 0xFFFFFF, '') if 'RNAM' in s and len(s['RNAM']) == 4 else ''
        female = (struct.unpack_from('<I', s['ACBS'], 0)[0] & 1) if r.sig == 'NPC_' and 'ACBS' in s and len(s['ACBS']) >= 4 else 0
        npcs[r.fid & 0xFFFFFF] = dict(edid=s.get('EDID', bytes(1)).rstrip(bytes(1)).decode('latin1'), name=s.get('FULL', bytes(1)).rstrip(bytes(1)).decode('latin1'), race=rk, female=female)

# ---- disabled placements
placed = []; stat = collections.Counter(); unmapped = collections.Counter()
for r in iter_records(src):
    if r.sig not in ('ACHR', 'ACRE') or not (r.flags & 0x800) or (r.flags & 0x20): continue
    s = dict(subrecords(src, r))
    if 'NAME' not in s or 'DATA' not in s or len(s['DATA']) < 24: continue
    base = struct.unpack('<I', s['NAME'])[0] & 0xFFFFFF; inf = npcs.get(base)
    key = ('%s %s %s' % (inf['edid'], inf['name'], inf['race'])) if inf else ''
    if r.sig == 'ACRE':
        t = pick(CREATURE, key, r.fid & 0xFFFFFF)
        if t == '*DEFAULT': unmapped[inf['edid'] if inf else '?'] += 1; t = None
    else:
        t = pick(HUMAN, key, r.fid & 0xFFFFFF)
        if t == '*DEFAULT': t = 'WorkshopNPC'
    if t is None: stat['no mapping / ignored (%s)' % r.sig] += 1; continue
    if t not in fo4_npc: stat['no FO4 target ' + t] += 1; continue
    cell = 0; world = 0
    for l, tt in r.chain:
        if tt in (6, 8, 9, 10): cell = struct.unpack('<I', l)[0] & 0xFFFFFF
        if tt == 1: world = struct.unpack('<I', l)[0] & 0xFFFFFF
    x, y = struct.unpack_from('<2f', s['DATA'])
    scale = struct.unpack('<f', s['XSCL'])[0] if 'XSCL' in s and len(s['XSCL']) == 4 else 1.0
    placed.append(dict(target=t, cell=cell, world=world, data=s['DATA'][:24], x=x, y=y, scale=scale, edid=(s.get('EDID', bytes(1)).rstrip(bytes(1)).decode('latin1'))))
    stat['mapped -> ' + t] += 1
log('disabled placements mapped: %d' % len(placed))

# ---- converted Fallout3.esm cells (override sources)
conv = open(a.conv, 'rb').read()
conv_cell = {}; conv_ext = {}
for r in iter_records(conv):
    if r.sig == 'CELL':
        low = r.fid & 0xFFFFFF; conv_cell[low] = record_bytes(conv, r)
        s = dict(subrecords(conv, r))
        if 'XCLC' in s and len(s['XCLC']) >= 8:
            w = [struct.unpack('<I', l)[0] & 0xFFFFFF for l, t in r.chain if t == 1]
            gx, gy = struct.unpack_from('<ii', s['XCLC']); conv_ext[((w[0] if w else 0), gx, gy)] = low
del conv

# ---- CapitalActors.esp tree
data = open(a.plugin, 'rb').read()
masters, _ = plugin_header(data)
F3 = masters.index('Fallout3.esm'); OWN = len(masters)
def parse(q, end):
    items = []
    while q < end:
        sig = data[q:q + 4]; size = struct.unpack_from('<I', data, q + 4)[0]
        if sig == b'GRUP':
            gtype = struct.unpack_from('<I', data, q + 12)[0]; label = data[q + 8:q + 12]
            items.append(['G', label, gtype, data[q + 16:q + 24], parse(q + 24, q + size)])
            q += size
        else:
            items.append(['R', data[q:q + 24 + size], sig, struct.unpack_from('<I', data, q + 12)[0]]); q += 24 + size
    return items
def ser(it):
    if it[0] == 'R': return it[1]
    p = b''.join(ser(c) for c in it[4])
    return b'GRUP' + struct.pack('<I', 24 + len(p)) + it[1] + struct.pack('<I', it[2]) + it[3] + p
hdr_end = 24 + struct.unpack_from('<I', data, 4)[0]
top = parse(hdr_end, len(data))
max_low = 0; already = 0
for r in iter_records(data):
    if (r.fid >> 24) == OWN: max_low = max(max_low, r.fid & 0xFFFFFF)
    if r.sig == 'ACHR' and (r.flags & 0x800): already += 1
if already: log('CapitalActors.esp already holds %d initially-disabled actors: run actors/name_actors.py first (it rebuilds the plugin from the .orig)' % already); sys.exit(1)
stamp = {}
def find_group(items, gtype, label=None):
    for it in items:
        if it[0] == 'G' and it[2] == gtype and (label is None or it[1] == label): return it
def top_group(label):
    for it in top:
        if it[0] == 'G' and it[2] == 0 and it[1] == label: return it
cell_top = top_group(b'CELL'); wrld_top = top_group(b'WRLD')
for it in cell_top[4]: stamp.setdefault(2, it[3])
def group_stamp(t): return stamp.get(t, bytes(8))
# index existing cells: low -> (items list, index)
cell_at = {}
def index(items):
    for i, it in enumerate(items):
        if it[0] == 'R' and it[2] == b'CELL': cell_at[it[3] & 0xFFFFFF] = (items, i)
        elif it[0] == 'G' and it[2] in (0, 1, 2, 3, 4, 5): stamp.setdefault(it[2], it[3]); index(it[4])
index(top)

def insert_sorted(items, grp):
    """insert a (block / sub-block) group keeping the label order of its siblings"""
    items.append(grp)
    return grp
def ensure_cell(low, world, gx, gy):
    if low in cell_at: return
    rec = conv_cell[low]
    fid = struct.unpack_from('<I', rec, 12)[0]
    interior = world == 0
    if interior:
        blk = low % 10; sb = (low // 10) % 10
        g2 = next((g for g in cell_top[4] if g[0] == 'G' and g[2] == 2 and struct.unpack('<I', g[1])[0] == blk), None)
        if g2 is None: g2 = ['G', struct.pack('<I', blk), 2, group_stamp(2), []]; cell_top[4].append(g2)
        g3 = next((g for g in g2[4] if g[0] == 'G' and g[2] == 3 and struct.unpack('<I', g[1])[0] == sb), None)
        if g3 is None: g3 = ['G', struct.pack('<I', sb), 3, group_stamp(3), []]; g2[4].append(g3)
        target = g3[4]
    else:
        wr_fid = (F3 << 24) | world
        wg = next((g for g in wrld_top[4] if g[0] == 'G' and g[2] == 1 and struct.unpack('<I', g[1])[0] == wr_fid), None)
        if wg is None: raise KeyError('world %06X has no children group in the plugin' % world)
        b4 = struct.pack('<hh', gy // 32, gx // 32); b5 = struct.pack('<hh', gy // 8, gx // 8)
        g4 = next((g for g in wg[4] if g[0] == 'G' and g[2] == 4 and g[1] == b4), None)
        if g4 is None: g4 = ['G', b4, 4, group_stamp(4), []]; wg[4].append(g4)
        g5 = next((g for g in g4[4] if g[0] == 'G' and g[2] == 5 and g[1] == b5), None)
        if g5 is None: g5 = ['G', b5, 5, group_stamp(5), []]; g4[4].append(g5)
        target = g5[4]
    target.append(['R', rec, b'CELL', fid])
    cell_at[low] = (target, len(target) - 1)

targets = collections.defaultdict(list)
for p in placed:
    if p['world']:
        gx = int(math.floor(p['x'] / 4096)); gy = int(math.floor(p['y'] / 4096))
        low = conv_ext.get((p['world'], gx, gy))
        if low is None: stat['skipped: exterior cell not in converted esm'] += 1; continue
        try: ensure_cell(low, p['world'], gx, gy)
        except KeyError as e: stat['skipped: ' + str(e)] += 1; continue
    else:
        low = p['cell']
        if low not in conv_cell: stat['skipped: interior cell not in converted esm'] += 1; continue
        ensure_cell(low, 0, 0, 0)
    targets[low].append(p)

next_low = max_low + 1; added = 0
for low, plist in targets.items():
    items, i = cell_at[low]
    cf = items[i][3]
    g6 = items[i + 1] if i + 1 < len(items) and items[i + 1][0] == 'G' and items[i + 1][2] == 6 else None
    if g6 is None:
        g6 = ['G', struct.pack('<I', cf), 6, group_stamp(6), []]; items.insert(i + 1, g6)
        for k, (its, j) in list(cell_at.items()):
            if its is items and j > i: cell_at[k] = (its, j + 1)
    g9 = next((g for g in g6[4] if g[0] == 'G' and g[2] == 9), None)
    if g9 is None: g9 = ['G', struct.pack('<I', cf), 9, group_stamp(9), []]; g6[4].append(g9)
    for p in plist:
        subs = [sub('NAME', struct.pack('<I', fo4_npc[p['target']]))]
        if abs(p['scale'] - 1.0) > 1e-4: subs.append(sub('XSCL', struct.pack('<f', p['scale'])))
        subs.append(sub('DATA', p['data']))
        body = b''.join(subs)
        fid = (OWN << 24) | next_low; next_low += 1
        g9[4].append(['R', b'ACHR' + struct.pack('<IIIIHH', len(body), 0x800, fid, 0, 131, 0) + body, b'ACHR', fid]); added += 1
log('added %d initially-disabled actors into %d cells' % (added, len(targets)))
for k, v in sorted(stat.items(), key=lambda kv: -kv[1])[:30]: log('  %5d  %s' % (v, k))
if unmapped: log('unmapped creature bases: ' + ', '.join('%s x%d' % kv for kv in unmapped.most_common(12)))
with open(a.plugin, 'wb') as f:
    f.write(data[:hdr_end])
    for it in top: f.write(ser(it))
log('wrote ' + a.plugin)
