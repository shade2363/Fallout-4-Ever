"""Give the named FO3 NPCs their names in CapitalActors.esp.

build-actor-map.ps1 maps every human FO3 NPC without a better rule to a generic Fallout 4 settler (WorkshopNPC) or guard (WorkshopNPCGuard), so
Lucas Simms, Moira Brown, Three Dog ... all show up as "Settler". This post-process finds those placements in CapitalActors.esp (matched to the
FO3 placement list lab\\actors\\actors-map.csv by position), creates one NPC_ per FO3 character - a clone of vanilla REFarmerMale/REFarmerFemale (template =
WorkshopNPCMale/Female, so the face is a random settler face, the template flags leave name/base data to this record) with the FO3 name and
the FO3 essential flag - and points the placement at it.

  python name_actors.py [--in tool\\output\\CapitalActors.esp] [--out same]    (idempotent: refuses to run on an already-named plugin)
Reads: lab\\actors\\actors-map.csv, FO3 Fallout3.esm (names), Fallout4.esm (clone sources)."""
import argparse, collections, csv, struct, sys
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records, subrecords, sub, plugin_header

ap = argparse.ArgumentParser()
ap.add_argument('--in', dest='inp', default='X:/__CAPITAL_WORKDIR__/lab/actors/CapitalActors.esp.orig')
ap.add_argument('--out', default='X:/__CAPITAL_WORKDIR__/tool/output/CapitalActors.esp')
ap.add_argument('--map', default='X:/__CAPITAL_WORKDIR__/lab/actors/actors-map.csv')
ap.add_argument('--src', default='X:/__CAPITAL_FO3_DATA__/Fallout3.esm')
ap.add_argument('--fo4', default='X:/__CAPITAL_FO4__/Data/Fallout4.esm')
a = ap.parse_args()
def log(m): print(m, flush=True)

GENERIC_NAMES = {'wastelander', 'settler', 'citizen', 'guard', 'raider', 'scavenger', 'merchant', 'slave', 'resident', 'brotherhood soldier', 'talon company merc',
                 'regulator', 'enclave soldier', 'paladin', 'knight', 'scribe', 'initiate', 'tunnel snake', 'overseer guard', 'security guard', 'vault dweller',
                 'ghoul', 'caravan guard', 'caravan trader', 'stranger', 'mercenary', 'soldier', 'sentinel', 'protector', 'worker', 'child', 'kid', 'mourner'}

# ------------------------------------------------------------------ FO3 NPC names
src = open(a.src, 'rb').read()
npcs = {}
for r in iter_records(src):
    if r.sig == 'NPC_':
        s = dict(subrecords(src, r))
        edid = s.get('EDID', bytes(1)).rstrip(bytes(1)).decode('latin1')
        name = s.get('FULL', b'').rstrip(bytes(1))
        flags = struct.unpack_from('<I', s['ACBS'], 0)[0] if 'ACBS' in s and len(s['ACBS']) >= 4 else 0
        npcs[edid] = dict(name=name, female=bool(flags & 1), essential=bool(flags & 2))
del src

# ------------------------------------------------------------------ placements (CSV) keyed by position
rows = list(csv.DictReader(open(a.map, newline=''), delimiter=';'))
by_pos = {}
placements_per_base = collections.Counter()
for r in rows:
    placements_per_base[r['srcbase']] += 1
    by_pos[(round(float(r['x']), 1), round(float(r['y']), 1), round(float(r['z']), 1))] = r
def is_named(base):
    n = npcs.get(base)
    if not n or not n['name']: return False
    nm = n['name'].decode('latin1').strip().lower()
    return nm not in GENERIC_NAMES and placements_per_base[base] <= 3

# ------------------------------------------------------------------ clone sources
fo4 = open(a.fo4, 'rb').read()
clone_src = {}
for r in iter_records(fo4):
    if r.sig == 'NPC_':
        s = subrecords(fo4, r)
        e = dict(s).get('EDID', b'').rstrip(bytes(1)).decode('latin1')
        if e in ('REFarmerMale', 'REFarmerFemale'): clone_src[e] = (r, s)
del_fo4 = fo4
assert len(clone_src) == 2

def make_clone(fid, edid, name, female, essential):
    r, subs = clone_src['REFarmerFemale' if female else 'REFarmerMale']
    out = []
    for k, v in subs:
        if k == 'EDID': v = ('FO3_' + edid).encode('latin1') + bytes(1)
        elif k == 'FULL': v = name + bytes(1)
        elif k == 'ACBS' and essential: v = struct.pack('<I', struct.unpack_from('<I', v, 0)[0] | 0x2) + v[4:]
        elif k == 'VMAD': continue
        out.append(sub(k, v))
    body = b''.join(out)
    return b'NPC_' + struct.pack('<IIIIHH', len(body), r.flags & ~0x40000, fid, 0, r.ver, 0) + body

# ------------------------------------------------------------------ tree of CapitalActors.esp
data = open(a.inp, 'rb').read()
masters, _ = plugin_header(data)
own = len(masters)
def parse(q, end):
    items = []
    while q < end:
        sig = data[q:q + 4]; size = struct.unpack_from('<I', data, q + 4)[0]
        if sig == b'GRUP':
            items.append(['G', data[q + 8:q + 12], struct.unpack_from('<I', data, q + 12)[0], data[q + 16:q + 24], parse(q + 24, q + size)])
            q += size
        else:
            items.append(['R', bytearray(data[q:q + 24 + size]), sig, struct.unpack_from('<I', data, q + 12)[0]])
            q += 24 + size
    return items
def ser(it):
    if it[0] == 'R': return bytes(it[1])
    p = b''.join(ser(c) for c in it[4])
    return b'GRUP' + struct.pack('<I', 24 + len(p)) + it[1] + struct.pack('<I', it[2]) + it[3] + p
hdr_end = 24 + struct.unpack_from('<I', data, 4)[0]
top = parse(hdr_end, len(data))
if any(t[0] == 'G' and t[1] == b'NPC_' for t in top):
    sys.exit('plugin already has an NPC_ group - run on the .orig backup')
max_low = 0
def scan(items):
    global max_low
    for it in items:
        if it[0] == 'R':
            if (it[3] >> 24) == own: max_low = max(max_low, it[3] & 0xFFFFFF)
        else: scan(it[4])
scan(top)

new_ids = {}                       # srcbase -> npc formid
clones = []
retargeted = collections.Counter()
named_refs = set()                 # FormIDs of retargeted ACHRs (made persistent below)
def visit(items):
    global max_low
    for it in items:
        if it[0] == 'G': visit(it[4]); continue
        if it[2] != b'ACHR': continue
        rec = it[1]
        # locate DATA to get position
        p = 24; pos = None; name_off = None
        while p < len(rec):
            s = bytes(rec[p:p + 4]); sz = struct.unpack_from('<H', rec, p + 4)[0]
            if s == b'DATA' and sz >= 12: pos = struct.unpack_from('<3f', rec, p + 6)
            if s == b'NAME': name_off = p + 6
            p += 6 + sz
        if pos is None or name_off is None: continue
        row = by_pos.get((round(pos[0], 1), round(pos[1], 1), round(pos[2], 1)))
        if row is None or row['fo4edid'] not in ('WorkshopNPC', 'WorkshopNPCGuard') or not is_named(row['srcbase']): continue
        base = row['srcbase']
        if base not in new_ids:
            max_low += 1
            fid = (own << 24) | max_low
            n = npcs[base]
            clones.append(make_clone(fid, base, n['name'], n['female'], n['essential']))
            new_ids[base] = fid
        struct.pack_into('<I', rec, name_off, new_ids[base])
        retargeted[row['fo4edid']] += 1
        named_refs.add(struct.unpack_from('<I', rec, 12)[0])
visit(top)
world_persist = {}                 # world group label -> list of ACHR records (exterior named actors)
def persist(items, world=None):
    for it in items:
        if it[0] != 'G': continue
        if it[2] == 6:
            g9 = next((g for g in it[4] if g[0] == 'G' and g[2] == 9), None)
            if g9 is None: continue
            mine = [c for c in g9[4] if c[0] == 'R' and c[3] in named_refs]
            if not mine: continue
            g9[4] = [c for c in g9[4] if c not in mine]
            for c in mine:
                struct.pack_into('<I', c[1], 8, struct.unpack_from('<I', c[1], 8)[0] | 0x400)
            if world is None:
                g8 = next((g for g in it[4] if g[0] == 'G' and g[2] == 8), None)
                if g8 is None:
                    g8 = ['G', it[1], 8, g9[3], []]; it[4].insert(it[4].index(g9), g8)
                g8[4].extend(mine)
            else:
                world_persist.setdefault(world, []).extend(mine)      # exterior: belongs in the worldspace persistent cell
            it[4] = [g for g in it[4] if not (g[0] == 'G' and g[2] == 9 and not g[4])]
        else:
            persist(it[4], it[1] if it[2] == 1 else world)
persist(top)
# exterior named actors: add the worldspace persistent CELL (copied from the converted plugin) with them in its persistent group
conv_d = open('X:/__CAPITAL_WORKDIR__/tool/output/Fallout3.esm', 'rb').read()
pcell = {}
for r in iter_records(conv_d):
    if r.sig == 'CELL' and (r.flags & 0x400) and len(r.chain) == 2 and r.chain[1][1] == 1:
        pcell[r.chain[1][0]] = (r.fid, conv_d[r.off:r.off + 24 + r.size])
def add_world_persistent(items):
    for it in items:
        if it[0] != 'G': continue
        if it[2] == 1 and it[1] in world_persist:
            fid, rec = pcell[it[1]]
            g8 = ['G', struct.pack('<I', fid), 8, bytes(8), world_persist.pop(it[1])]
            g6 = ['G', struct.pack('<I', fid), 6, bytes(8), [g8]]
            it[4][0:0] = [['R', bytearray(rec), b'CELL', fid], g6]
        else:
            add_world_persistent(it[4])
add_world_persistent(top)
assert not world_persist, 'world group not found for %s' % list(world_persist)
grp = b''.join(clones)
npc_group = ['G', b'NPC_', 0, bytes(8), [['R', c, b'NPC_', struct.unpack_from('<I', c, 12)[0]] for c in clones]]
idx = next((i for i, t in enumerate(top) if t[0] == 'G' and t[1] in (b'CELL', b'WRLD')), 0)
top.insert(idx, npc_group)
log('named NPCs: %d characters, %d placements retargeted %s' % (len(new_ids), sum(retargeted.values()), dict(retargeted)))
log('sample names: ' + ', '.join(npcs[b]['name'].decode('latin1') for b in list(new_ids)[:12]))
with open(a.out, 'wb') as f:
    f.write(data[:hdr_end])
    for it in top: f.write(ser(it))
log('wrote ' + a.out)
