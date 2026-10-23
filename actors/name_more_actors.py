"""Give the named FO3 characters that name_actors.py skipped their own NPC_ record (post-pass on tool\\output\\CapitalActors.esp, in place).

name_actors.py only clones characters the actor map turned into a generic SETTLER (WorkshopNPC / WorkshopNPCGuard).  Characters mapped to other leveled lists stayed generic
spawns: all the Brotherhood of Steel cast (Elder Lyons, scribes, paladins, knights), the ghoul cast of Underworld / Tenpenny / Bigtown (Ahzrukhal, Winthrop, Greta, Gob, Crowley, Roy Phillips ...),
slavers, a few raiders.  Their dialogue (about 2,300 INFOs, most of the main quest) needs a speaker that is one individual with a persistent placement, so for every FO3 NPC_ that
 - has dialogue (it is the GetIsID speaker of at least one INFO with a response), and
 - has 1-3 placements in lab\\actors\\actors-map.csv, none of them already retargeted
this makes an NPC_ clone (human: the REFarmerMale/Female settler template like name_actors; ghoul: a vanilla Fallout 4 ghoul NPC with a leveled face template), points every placement at it
and makes the placements persistent (a speaker alias needs a persistent reference).  Idempotent (skips placements whose base is already an FO3_* clone).

  python actors\\name_more_actors.py [--plugin tool\\output\\CapitalActors.esp] [--dry-run]
After it: rebuild the dialogue (dialogue\\build_all_dialogue.py: new ids come from the reserved range), ai\\build_ai.py, install."""
import argparse, collections, csv, shutil, struct, sys
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records, subrecords, sub, plugin_header

ap = argparse.ArgumentParser()
ap.add_argument('--plugin', default='X:/__CAPITAL_WORKDIR__/tool/output/CapitalActors.esp')
ap.add_argument('--map', default='X:/__CAPITAL_WORKDIR__/lab/actors/actors-map.csv')
ap.add_argument('--src', default='X:/__CAPITAL_FO3_DATA__/Fallout3.esm')
ap.add_argument('--fo4', default='X:/__CAPITAL_FO4__/Data/Fallout4.esm')
ap.add_argument('--conv', default='X:/__CAPITAL_WORKDIR__/tool/output/Fallout3.esm')
ap.add_argument('--dry-run', action='store_true')
ap.add_argument('--list', default='X:/__CAPITAL_WORKDIR__/actors/more_named.json')
a = ap.parse_args()
def log(m): print(m, flush=True)

GENERIC_NAMES = {'wastelander', 'settler', 'citizen', 'guard', 'raider', 'scavenger', 'merchant', 'slave', 'resident', 'brotherhood soldier', 'talon company merc',
                 'regulator', 'enclave soldier', 'paladin', 'knight', 'scribe', 'initiate', 'tunnel snake', 'overseer guard', 'security guard', 'vault dweller',
                 'ghoul', 'caravan guard', 'caravan trader', 'stranger', 'mercenary', 'soldier', 'sentinel', 'protector', 'worker', 'child', 'kid', 'mourner',
                 'slaver', 'hitman', 'hunter', 'underworld resident', 'wasteland settler', 'enclave officer', 'crazed wastelander', 'caravan trader'}

# ------------------------------------------------------------------ FO3: NPCs, races, who has dialogue
src = open(a.src, 'rb').read()
ghoul_races = set()
for r in iter_records(src):
    if r.sig == 'RACE':
        e = dict(subrecords(src, r)).get('EDID', b'').rstrip(bytes(1)).decode('latin1')
        if 'ghoul' in e.lower(): ghoul_races.add(r.fid & 0xFFFFFF)
npcs = {}
by_fid = {}
for r in iter_records(src):
    if r.sig == 'NPC_':
        s = dict(subrecords(src, r))
        edid = s.get('EDID', bytes(1)).rstrip(bytes(1)).decode('latin1')
        flags = struct.unpack_from('<I', s['ACBS'], 0)[0] if 'ACBS' in s and len(s['ACBS']) >= 4 else 0
        race = struct.unpack_from('<I', s['RNAM'])[0] & 0xFFFFFF if 'RNAM' in s and len(s['RNAM']) == 4 else 0
        npcs[edid] = dict(name=s.get('FULL', b'').rstrip(bytes(1)), female=bool(flags & 1), essential=bool(flags & 2), race=race, fid=r.fid & 0xFFFFFF)
        by_fid[r.fid & 0xFFFFFF] = edid
speakers = collections.Counter()
for r in iter_records(src):
    if r.sig != 'INFO': continue
    subs = subrecords(src, r)
    if not any(k == 'NAM1' and v.strip(bytes(1)) for k, v in subs): continue
    for k, v in subs:
        if k == 'CTDA' and len(v) >= 16 and struct.unpack_from('<I', v, 8)[0] == 72 and struct.unpack_from('<f', v, 4)[0] == 1.0 and (v[0] & 0xE0) == 0:
            speakers[struct.unpack_from('<I', v, 12)[0] & 0xFFFFFF] += 1
del src

rows = list(csv.DictReader(open(a.map, newline=''), delimiter=';'))
by_pos = {}
per_base = collections.Counter()
for r in rows:
    per_base[r['srcbase']] += 1
    by_pos[(round(float(r['x']), 1), round(float(r['y']), 1), round(float(r['z']), 1))] = r
targets = {}
for edid, n in npcs.items():
    if not n['name'] or speakers[n['fid']] == 0: continue
    nm = n['name'].decode('latin1').strip().lower()
    if (nm in GENERIC_NAMES and speakers[n['fid']] < 5) or not (1 <= per_base[edid] <= 3): continue      # a generic NAME with a real conversation (Richter the slaver boss, the Enclave officer ...) is still one individual
    targets[edid] = n
log('candidate characters with dialogue and 1-3 placements: %d' % len(targets))

# ------------------------------------------------------------------ Fallout 4 clone sources
fo4 = open(a.fo4, 'rb').read()
names = {}
want = {'REFarmerMale', 'REFarmerFemale', 'GoodneighborDrifterM04Ghoul', 'GoodneighborDrifterF03GhoulStatehouse'}
clone_src = {}
for r in iter_records(fo4):
    s = subrecords(fo4, r)
    e = dict(s).get('EDID', b'').rstrip(bytes(1)).decode('latin1')
    if e: names[e] = r.fid
    if r.sig == 'NPC_' and e in want: clone_src[e] = (r, s)
assert len(clone_src) == 4, clone_src.keys()
farmer_doft = next(v for k, v in clone_src['REFarmerMale'][1] if k == 'DOFT')
generic_fac = names['GenericNPCFaction']

def make_clone(fid, edid, n):
    ghoul = n['race'] in ghoul_races
    key = ('GoodneighborDrifterF03GhoulStatehouse' if n['female'] else 'GoodneighborDrifterM04Ghoul') if ghoul else ('REFarmerFemale' if n['female'] else 'REFarmerMale')
    r, subs = clone_src[key]
    out = []
    for k, v in subs:
        if k == 'EDID': v = ('FO3_' + edid).encode('latin1') + bytes(1)
        elif k == 'ACBS' and n['essential']: v = struct.pack('<I', struct.unpack_from('<I', v, 0)[0] | 0x2) + v[4:]
        elif k == 'VMAD': continue
        if ghoul:
            if k == 'SNAM': continue                 # Goodneighbor factions / chat factions: replaced by one generic faction below
            if k == 'PKID': continue                 # the Goodneighbor sandbox package: CapitalAI gives the routines
            if k == 'DOFT': v = farmer_doft
        out.append((k, v))
    res = []
    for k, v in out:
        if k == 'CNAM':
            res.append(sub(k, v)); res.append(sub('FULL', n['name'] + bytes(1))); continue
        if k == 'FULL': continue
        res.append(sub(k, v))
    if ghoul:                                          # one faction, inserted before VTCK (record order: ... SNAM, VTCK ...)
        i = next(j for j, x in enumerate(res) if x[:4] == b'VTCK')
        res.insert(i, sub('SNAM', struct.pack('<IB3x', generic_fac, 0)[:5]))
    body = b''.join(res)
    return b'NPC_' + struct.pack('<IIIIHH', len(body), r.flags & ~0x40000, fid, 0, r.ver, 0) + body, ('ghoul' if ghoul else 'human')

# ------------------------------------------------------------------ the plugin tree
data = open(a.plugin, 'rb').read()
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
assert b''.join([data[:hdr_end]] + [ser(t) for t in top]) == data, 'round trip mismatch'
npc_group = next(t for t in top if t[0] == 'G' and t[1] == b'NPC_')
existing_clone_ids = {c[3] for c in npc_group[4]}
existing_edids = set()
max_low = 0
def scan(items):
    global max_low
    for it in items:
        if it[0] == 'R':
            if (it[3] >> 24) == own: max_low = max(max_low, it[3] & 0xFFFFFF)
        else: scan(it[4])
scan(top)
for c in npc_group[4]:
    p = 24
    rec = c[1]
    while p < len(rec):
        s = bytes(rec[p:p + 4]); sz = struct.unpack_from('<H', rec, p + 4)[0]
        if s == b'EDID': existing_edids.add(bytes(rec[p + 6:p + 6 + sz]).rstrip(bytes(1)).decode('latin1'))
        p += 6 + sz

new_ids = {}; clones = []; retargeted = collections.Counter(); named_refs = set(); kinds = {}
def visit(items):
    global max_low
    for it in items:
        if it[0] == 'G': visit(it[4]); continue
        if it[2] != b'ACHR': continue
        rec = it[1]
        p = 24; pos = None; name_off = None
        while p < len(rec):
            s = bytes(rec[p:p + 4]); sz = struct.unpack_from('<H', rec, p + 4)[0]
            if s == b'DATA' and sz >= 12: pos = struct.unpack_from('<3f', rec, p + 6)
            if s == b'NAME': name_off = p + 6
            p += 6 + sz
        if pos is None or name_off is None: continue
        row = by_pos.get((round(pos[0], 1), round(pos[1], 1), round(pos[2], 1)))
        if row is None or row['srcbase'] not in targets or 'FO3_' + row['srcbase'] in existing_edids: continue
        base = row['srcbase']
        if base not in new_ids:
            max_low += 1
            fid = (own << 24) | max_low
            clone, kind = make_clone(fid, base, targets[base])
            clones.append(clone); new_ids[base] = fid; kinds[base] = kind
        struct.pack_into('<I', rec, name_off, new_ids[base])
        retargeted[kinds[base]] += 1
        named_refs.add(struct.unpack_from('<I', rec, 12)[0])
visit(top)
# ---- clones whose placements are ALL non-persistent (disabled / quest-placed actors of name_actors / name_disabled): a dialogue speaker alias needs a persistent reference, so these
# characters (Ronald Laren, Ian West, Victoria Watts, the Project Purity scientists ...) got no conversation at all.  Make their placements persistent too (not the childhood cast CG0x / Vault106*).
clone_base = {}
for c in npc_group[4]:
    rec = c[1]; p = 24
    while p < len(rec):
        sg = bytes(rec[p:p + 4]); sz = struct.unpack_from('<H', rec, p + 4)[0]
        if sg == b'EDID':
            e_ = bytes(rec[p + 6:p + 6 + sz]).rstrip(bytes(1)).decode('latin1')
            if e_.startswith('FO3_'): clone_base[c[3] & 0xFFFFFF] = e_[4:]
        p += 6 + sz
refs_of = collections.defaultdict(list)
def collect(items):
    for it in items:
        if it[0] == 'G': collect(it[4]); continue
        if it[2] != b'ACHR': continue
        rec = it[1]; p = 24
        while p < len(rec):
            sg = bytes(rec[p:p + 4]); sz = struct.unpack_from('<H', rec, p + 4)[0]
            if sg == b'NAME': refs_of[struct.unpack_from('<I', rec, p + 6)[0] & 0xFFFFFF].append((struct.unpack_from('<I', rec, 12)[0], bool(struct.unpack_from('<I', rec, 8)[0] & 0x400)))
            p += 6 + sz
collect(top)
persisted = []
for low, edid in clone_base.items():
    rs = refs_of.get(low, [])
    if not rs or any(pp for _, pp in rs) or edid.upper().startswith(('CG0', 'VAULT106', 'V106')): continue
    npcs_ = npcs.get(edid)
    if npcs_ is None or speakers[npcs_['fid']] == 0: continue
    for fidr, _ in rs: named_refs.add(fidr)
    persisted.append(edid)
log('placements made persistent for %d existing characters with dialogue: %s' % (len(persisted), ', '.join(persisted)))
log('new characters: %d (%s), %d placements retargeted' % (len(new_ids), dict(collections.Counter(kinds.values())), sum(retargeted.values())))
if a.dry_run or not (new_ids or persisted):
    log('names: ' + ', '.join(sorted(targets[b]['name'].decode('latin1') for b in new_ids)[:60]))
    sys.exit(0)

# ---- persistence: the retargeted placements move into the persistent children of their cell (interior) / of the worldspace persistent cell (exterior)
world_persist = {}
def persist(items, world=None):
    for it in items:
        if it[0] != 'G': continue
        if it[2] == 6:
            g9 = next((g for g in it[4] if g[0] == 'G' and g[2] == 9), None)
            if g9 is None: continue
            mine = [c for c in g9[4] if c[0] == 'R' and c[3] in named_refs]
            if not mine: continue
            g9[4] = [c for c in g9[4] if c not in mine]
            for c in mine: struct.pack_into('<I', c[1], 8, struct.unpack_from('<I', c[1], 8)[0] | 0x400)
            if world is None:
                g8 = next((g for g in it[4] if g[0] == 'G' and g[2] == 8), None)
                if g8 is None:
                    g8 = ['G', it[1], 8, g9[3], []]; it[4].insert(it[4].index(g9), g8)
                g8[4].extend(mine)
            else:
                world_persist.setdefault(world, []).extend(mine)
            it[4] = [g for g in it[4] if not (g[0] == 'G' and g[2] == 9 and not g[4])]
        else:
            persist(it[4], it[1] if it[2] == 1 else world)
persist(top)
# refs that were ALREADY persistent (name_actors / attach) just keep their place: only temporary ones moved above
conv_d = open(a.conv, 'rb').read()
pcell = {}
for r in iter_records(conv_d):
    if r.sig == 'CELL' and (r.flags & 0x400) and len(r.chain) == 2 and r.chain[1][1] == 1:
        pcell[r.chain[1][0]] = (r.fid, conv_d[r.off:r.off + 24 + r.size])
def add_world_persistent(items):
    for it in items:
        if it[0] != 'G': continue
        if it[2] == 1 and it[1] in world_persist:
            fid, rec = pcell[it[1]]
            # does this world already have its persistent cell (from name_actors)?  [R CELL(0x400), G type6 [G type8 [...]]]
            done = False
            for k, ch in enumerate(it[4]):
                if ch[0] == 'R' and ch[2] == b'CELL' and (struct.unpack_from('<I', ch[1], 8)[0] & 0x400) and k + 1 < len(it[4]) and it[4][k + 1][0] == 'G' and it[4][k + 1][2] == 6:
                    g6 = it[4][k + 1]
                    g8 = next((g for g in g6[4] if g[0] == 'G' and g[2] == 8), None)
                    if g8 is None:
                        g8 = ['G', g6[1], 8, bytes(8), []]; g6[4].insert(0, g8)
                    g8[4].extend(world_persist.pop(it[1])); done = True; break
            if not done:
                g8 = ['G', struct.pack('<I', fid), 8, bytes(8), world_persist.pop(it[1])]
                g6 = ['G', struct.pack('<I', fid), 6, bytes(8), [g8]]
                it[4][0:0] = [['R', bytearray(rec), b'CELL', fid], g6]
        else:
            add_world_persistent(it[4])
add_world_persistent(top)
assert not world_persist, 'world group not found for %s' % list(world_persist)
for c in clones: npc_group[4].append(['R', c, b'NPC_', struct.unpack_from('<I', c, 12)[0]])
shutil.copyfile(a.plugin, a.plugin + '.pre-more-named') if not __import__('os').path.exists(a.plugin + '.pre-more-named') else None
with open(a.plugin, 'wb') as f:
    f.write(data[:hdr_end])
    for it in top: f.write(ser(it))
import json
json.dump({'persisted': persisted}, open(a.list.replace('more_named', 'persisted_late'), 'w'))
if new_ids: json.dump({b: {'name': targets[b]['name'].decode('latin1'), 'kind': kinds[b], 'form': '%08X' % new_ids[b]} for b in new_ids}, open(a.list, 'w'), indent=1)
log('wrote %s (+%d NPC_ records); list -> %s' % (a.plugin, len(clones), a.list))
