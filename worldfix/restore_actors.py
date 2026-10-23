"""Place the DLC actors (the converter drops every NPC/creature reference) into a converted DLC .esm.

Every ACHR/ACRE a DLC plugin defines is mapped (by base EDID / name / race text, same rule set as build-actor-map.ps1 plus DLC-specific rules)
to a vanilla Fallout 4 leveled NPC_ (Lvl*/Workshop*/Enc*) and added to the converted plugin as a new ACHR in the same cell, at the same position.
Initially-disabled refs are skipped (as for the base game). Exterior refs are filed by the grid cell containing their position and need that cell to exist
in the converted DLC plugin; anything else is counted as skipped.

  python restore_actors.py --src <FO3 DLC esm> --src-base <FO3 Fallout3.esm> --in <converted DLC esm> --out <esm with actors> [--fo4 Fallout4.esm]
New FormIDs are allocated above the highest FormID of the converted plugin (own master index)."""
import argparse, collections, math, re, struct, sys
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records, subrecords, sub, plugin_header

ap = argparse.ArgumentParser()
ap.add_argument('--src', required=True); ap.add_argument('--src-base', required=True)
ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--fo4', default='X:/__CAPITAL_FO4__/Data/Fallout4.esm')
a = ap.parse_args()
def log(m): print(m, flush=True)

# ------------------------------------------------------------------ Fallout 4 targets
fo4 = open(a.fo4, 'rb').read()
fo4_npc = {}
for r in iter_records(fo4):
    if r.sig == 'NPC_':
        for k, b in subrecords(fo4, r):
            if k == 'EDID':
                fo4_npc[b.rstrip(bytes(1)).decode('latin1')] = r.fid
                break
del fo4

# ------------------------------------------------------------------ mapping rules (build-actor-map.ps1 + DLC additions)
WASTELAND = ['LvlRadRoach', 'LvlMolerat', 'LvlBloatfly', 'LvlViciousDog', 'LvlRadscorpion']
CREATURE = [
    (r'dead|corpse|ragdoll|caged|marker|spidermine|spider|chimera|rubble', None),
    (r'radroach|roach', 'LvlRadRoach'), (r'bloatfly|bloat', 'LvlBloatfly'), (r'molerat|mole', 'LvlMolerat'),
    (r'radscorp|scorpion', 'LvlRadscorpion'), (r'mirelurk|crab|lobster', 'LvlMirelurkAll'), (r'deathclaw', 'LvlDeathclaw'),
    (r'yao', 'LvlYaoGuai'), (r'brahmin|bighorn|mutant ?cow|cow', 'EncBrahminTemplate'),
    (r'raider.?dog', 'LvlRaiderDog'), (r'dog|hound|wolf|coyote', 'LvlViciousDog'), (r'centaur', 'LvlMutantHound'),
    (r'feral|ghoul|trog|wildman|savage', 'LvlFeralGhoul'),
    (r'minigun', 'LvlSupermutantMinigun'), (r'supermutant.*melee|melee.*supermutant', 'LvlSupermutantMelee'),
    (r'supermutant|super mutant|mutant|behemoth|overlord|nightkin', 'LvlSupermutantAllRanged'),
    (r'\bant\b|ant$|lvlant|forager|fireant', 'LvlRadRoach'),
    (r'alien|zeta|abductee', 'LvlGunner'),                       # Mothership Zeta aliens: hostile humanoid shooters
    (r'swamp|angler|anglers|stalker', 'LvlFeralGhoul'),
    (r'eyebot', 'EncEyeBot'), (r'turret', 'LvlTurretTripod'), (r'sentry', 'LvlSentryBot'), (r'assaultron', 'LvlAssaultron'),
    (r'gutsy', 'LvlMrGutsy'), (r'handy', 'LvlMrHandy_Random'),
    (r'robot|protectron|robco|robobrain|combatdroid|maintenance|droid', 'LvlProtectron'),
    (r'wasteland|critter|random|creature', '*WASTELAND'),
]
HUMAN = [
    (r'dead|corpse|^loot\d|ragdoll|captive|dummy|test|mannequin', None),
    (r'enclave|talon|mercenary|merc\b|hunter|slaver|chinese|china|chinaman|pitt.*(guard|raider)|marauder|ironclad|reaver', 'LvlGunner'),
    (r'raider|lunatic|insane|scavenger|wildman|crazy|cultist|feral', 'LvlRaider'),
    (r'regulator|minuteman', 'LvlMinuteman'),
    (r'brotherhood|paladin|knight|scribe|outcast|elder|bos\b|sentinel|lyons|initiate|squire', 'LvlBoSSoldier_CombatArmor_Semi'),
    (r'guard|security|sheriff|police|soldier|army|marine|trooper|officer', '*GUARD'),
    (r'ghoul', 'LvlTriggermanGhoulOnly'),
]
def pick(rules, key, ref_low):
    for rx, t in rules:
        if re.search(rx, key, re.I):
            if t is None: return None
            if t == '*WASTELAND': return WASTELAND[ref_low % len(WASTELAND)]
            return 'WorkshopNPCGuard' if t == '*GUARD' else t
    return '*DEFAULT'

# ------------------------------------------------------------------ source info
def load_source(path, tag, masters_tags):
    d = open(path, 'rb').read()
    masters, _ = plugin_header(d)
    own = len(masters)
    def res(fid):
        i = fid >> 24
        return (masters_tags[i] if i < own else tag, fid & 0xFFFFFF)
    return d, masters, own, res
base_d, base_ms, base_own, base_res = load_source(a.src_base, 'F3', [])
dlc_d, dlc_ms, dlc_own, dlc_res = load_source(a.src, 'DLC', ['F3'])
info = {}                 # (tag, low24) -> dict
def collect(d, res, tag):
    race = {}
    npcs = []
    for r in iter_records(d):
        if r.sig in ('NPC_', 'CREA', 'RACE'):
            s = dict(subrecords(d, r))
            edid = s.get('EDID', bytes(1)).rstrip(bytes(1)).decode('latin1')
            key = res(r.fid)
            if r.sig == 'RACE':
                race[key] = edid
            else:
                npcs.append((key, r.sig, edid, s))
    return race, npcs
race_b, npcs_b = collect(base_d, base_res, 'F3')
race_d, npcs_d = collect(dlc_d, dlc_res, 'DLC')
race_all = dict(race_b); race_all.update(race_d)
for (key, sig, edid, s) in npcs_b + npcs_d:
    name = s.get('FULL', bytes(1)).rstrip(bytes(1)).decode('latin1')
    rkey = None
    if 'RNAM' in s and len(s['RNAM']) == 4:
        rf = struct.unpack('<I', s['RNAM'])[0]
        rkey = (dlc_res(rf) if key[0] == 'DLC' else base_res(rf))
    female = 0
    if sig == 'NPC_' and 'ACBS' in s and len(s['ACBS']) >= 4:
        female = struct.unpack_from('<I', s['ACBS'], 0)[0] & 1
    info[key] = dict(sig=sig, edid=edid, name=name, race=race_all.get(rkey, ''), female=female)
del base_d

# ------------------------------------------------------------------ source cells and placements of the DLC
src_cells = {}          # dlc-local cell fid -> (interior, world fid or 0, gx, gy)
for r in iter_records(dlc_d):
    if r.sig == 'CELL':
        s = dict(subrecords(dlc_d, r))
        interior = bool(s.get('DATA', bytes(2))[0] & 1) if s.get('DATA') else False
        world = 0
        for l, t in r.chain:
            if t == 1: world = struct.unpack('<I', l)[0]
        gx = gy = None
        if 'XCLC' in s and len(s['XCLC']) >= 8: gx, gy = struct.unpack_from('<ii', s['XCLC'])
        src_cells[r.fid] = (interior, world, gx, gy)
placed = []
stat = collections.Counter(); unmapped = collections.Counter()
for r in iter_records(dlc_d):
    if r.sig not in ('ACHR', 'ACRE'): continue
    if (r.fid >> 24) < dlc_own:
        stat['override of base ref (skipped)'] += 1; continue
    if r.flags & 0x20: stat['deleted'] += 1; continue
    if r.flags & 0x800: stat['initially disabled (skipped)'] += 1; continue
    s = dict(subrecords(dlc_d, r))
    if 'NAME' not in s or 'DATA' not in s or len(s['DATA']) < 24: stat['no NAME/DATA'] += 1; continue
    base = dlc_res(struct.unpack('<I', s['NAME'])[0])
    inf = info.get(base)
    key = ('%s %s %s' % (inf['edid'], inf['name'], inf['race'])) if inf else ''
    female = inf['female'] if inf else 0
    if r.sig == 'ACRE':
        t = pick(CREATURE, key, r.fid & 0xFFFFFF)
        if t == '*DEFAULT': unmapped[inf['edid'] if inf else '?'] += 1; t = None
    else:
        t = pick(HUMAN, key, r.fid & 0xFFFFFF)
        if t == '*DEFAULT': t = 'WorkshopNPC'
    if t is None: stat['no mapping/ignored (%s)' % r.sig] += 1; continue
    if t not in fo4_npc: stat['no FO4 target ' + t] += 1; continue
    cell = 0; world = 0
    for l, tt in r.chain:
        if tt in (6, 8, 9, 10): cell = struct.unpack('<I', l)[0]
        if tt == 1: world = struct.unpack('<I', l)[0]
    x, y, z, rx, ry, rz = struct.unpack_from('<6f', s['DATA'])
    scale = struct.unpack('<f', s['XSCL'])[0] if 'XSCL' in s and len(s['XSCL']) == 4 else 1.0
    placed.append(dict(sig=r.sig, target=t, cell=cell, world=world, data=s['DATA'][:24], pos=(x, y), scale=scale))
    stat['mapped -> ' + t] += 1
log('DLC source: own placed %d' % len(placed))

# ------------------------------------------------------------------ converted plugin
data = open(a.inp, 'rb').read()
conv_ms, _ = plugin_header(data)
conv_own = len(conv_ms)
def src_to_conv(fid):                       # DLC-local FormID -> converted-plugin FormID
    i = fid >> 24
    return ((conv_own if i >= dlc_own else conv_ms.index('Fallout3.esm')) << 24) | (fid & 0xFFFFFF)
conv_ext = {}                               # (world conv fid, gx, gy) -> cell conv fid
conv_cells = set()
max_low = 0
for r in iter_records(data):
    if (r.fid >> 24) == conv_own: max_low = max(max_low, r.fid & 0xFFFFFF)
    if r.sig == 'CELL':
        conv_cells.add(r.fid)
        s = dict(subrecords(data, r))
        if 'XCLC' in s and len(s['XCLC']) >= 8:
            world = 0
            for l, t in r.chain:
                if t == 1: world = struct.unpack('<I', l)[0]
            if world:
                gx, gy = struct.unpack_from('<ii', s['XCLC'])
                conv_ext[(world, gx, gy)] = r.fid

targets = collections.defaultdict(list)
for p in placed:
    if p['cell'] in src_cells and not src_cells[p['cell']][0] and src_cells[p['cell']][2] is not None:
        pass
    # decide target cell
    cinfo = src_cells.get(p['cell'])
    if p['world'] or (cinfo and not cinfo[0] and cinfo[1]):
        world = p['world'] or cinfo[1]
        gx = int(math.floor(p['pos'][0] / 4096)); gy = int(math.floor(p['pos'][1] / 4096))
        cf = conv_ext.get((src_to_conv(world), gx, gy))
        if cf is None:
            stat['skipped: exterior cell not in plugin'] += 1; continue
    else:
        cf = src_to_conv(p['cell'])
        if cf not in conv_cells:
            stat['skipped: interior cell not in plugin'] += 1; continue
    targets[cf].append(p)

# ------------------------------------------------------------------ tree
def parse(q, end):
    items = []
    while q < end:
        sig = data[q:q + 4]; size = struct.unpack_from('<I', data, q + 4)[0]
        if sig == b'GRUP':
            gtype = struct.unpack_from('<I', data, q + 12)[0]; label = data[q + 8:q + 12]
            if gtype in (0, 1, 2, 3, 4, 5, 6, 8, 9, 10) and (gtype != 0 or label in (b'CELL', b'WRLD')):
                items.append(['G', label, gtype, data[q + 16:q + 24], parse(q + 24, q + size)])
            else:
                items.append(['RAW', data[q:q + size]])
            q += size
        else:
            items.append(['R', data[q:q + 24 + size], sig, struct.unpack_from('<I', data, q + 12)[0]])
            q += 24 + size
    return items
def ser(it):
    if it[0] in ('R', 'RAW'): return it[1]
    p = b''.join(ser(c) for c in it[4])
    return b'GRUP' + struct.pack('<I', 24 + len(p)) + it[1] + struct.pack('<I', it[2]) + it[3] + p
hdr_end = 24 + struct.unpack_from('<I', data, 4)[0]
top = parse(hdr_end, len(data))
cell_pos = {}; stamps = {}
def index_cells(items):
    for i, it in enumerate(items):
        if it[0] == 'R' and it[2] == b'CELL': cell_pos[it[3]] = (items, i)
        elif it[0] == 'G':
            stamps.setdefault(it[2], it[3])
            if it[2] in (0, 1, 2, 3, 4, 5): index_cells(it[4])
index_cells(top)

next_low = max_low + 1
added = 0
for cf, plist in targets.items():
    items, i = cell_pos[cf]
    g6 = items[i + 1] if i + 1 < len(items) and items[i + 1][0] == 'G' and items[i + 1][2] == 6 else None
    if g6 is None:
        g6 = ['G', struct.pack('<I', cf), 6, stamps.get(6, bytes(8)), []]
        items.insert(i + 1, g6)
        for k, (its, j) in list(cell_pos.items()):
            if its is items and j > i: cell_pos[k] = (its, j + 1)
    g9 = next((g for g in g6[4] if g[0] == 'G' and g[2] == 9), None)
    if g9 is None:
        g9 = ['G', struct.pack('<I', cf), 9, stamps.get(9, bytes(8)), []]
        g6[4].append(g9)
    for p in plist:
        subs = [sub('NAME', struct.pack('<I', fo4_npc[p['target']]))]
        if abs(p['scale'] - 1.0) > 1e-4: subs.append(sub('XSCL', struct.pack('<f', p['scale'])))
        subs.append(sub('DATA', p['data']))
        body = b''.join(subs)
        fid = (conv_own << 24) | next_low; next_low += 1
        rec = b'ACHR' + struct.pack('<IIIIHH', len(body), 0, fid, 0, 131, 0) + body
        g9[4].append(['R', rec, b'ACHR', fid])
        added += 1
log('added %d ACHR into %d cells' % (added, len(targets)))
for k, v in sorted(stat.items(), key=lambda kv: -kv[1])[:40]: log('  %5d  %s' % (v, k))
if unmapped: log('unmapped creature bases: ' + ', '.join('%s x%d' % kv for kv in unmapped.most_common(12)))
with open(a.out, 'wb') as f:
    f.write(data[:hdr_end])
    for it in top: f.write(ser(it))
log('wrote ' + a.out)
