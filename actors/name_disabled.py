"""Give the named FO3 characters that start DISABLED (the childhood Dads, Beatrice, Stevie/Susie Mack, Colonel Autumn ...) their own NPC_ clone like actors/name_actors.py does for the enabled ones.

worldfix/place_disabled_actors.py placed the initially-disabled FO3 actors in CapitalActors.esp as generic WorkshopNPC / WorkshopNPCGuard references without a name or an FO3 voice type.
This post-pass finds those placements (flag 0x800, base WorkshopNPC or WorkshopNPCGuard, matched to the FO3 ACHR by position), creates one clone NPC_ `FO3_<fo3 edid>` of REFarmerMale / REFarmerFemale with the
FO3 name per named character (an NPC base that is not generic and has at most 3 placements), and points the placement at it. The placements stay initially disabled and non-persistent (scripts enable them).
Run AFTER actors/name_actors.py and worldfix/place_disabled_actors.py (and BEFORE the dialogue / quest / object-script builders, which look the clones up by name).
  python name_disabled.py [--plugin tool\\output\\CapitalActors.esp]      (refuses to run twice: it looks for an existing FO3_CG01Dad)"""
import argparse, collections, struct, sys
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records, subrecords, sub, plugin_header

ap = argparse.ArgumentParser()
ap.add_argument('--plugin', default='X:/__CAPITAL_WORKDIR__/tool/output/CapitalActors.esp')
ap.add_argument('--src', default='X:/__CAPITAL_FO3_DATA__/Fallout3.esm')
ap.add_argument('--fo4', default='X:/__CAPITAL_FO4__/Data/Fallout4.esm')
a = ap.parse_args()
def log(m): print(m, flush=True)

GENERIC_NAMES = {'wastelander', 'settler', 'citizen', 'guard', 'raider', 'scavenger', 'merchant', 'slave', 'resident', 'brotherhood soldier', 'talon company merc',
                 'regulator', 'enclave soldier', 'paladin', 'knight', 'scribe', 'initiate', 'tunnel snake', 'overseer guard', 'security guard', 'vault dweller',
                 'ghoul', 'caravan guard', 'caravan trader', 'stranger', 'mercenary', 'soldier', 'sentinel', 'protector', 'worker', 'child', 'kid', 'mourner',
                 'megaton settler', 'tenpenny resident', 'brotherhood of steel paladin', 'enclave officer', 'enclave scientist', 'chinese commando', 'dead settler',
                 'child slaver', 'child of atom', 'prime'}

# ---- FO3: NPC bases (name / sex / essential), placements per base, and the disabled placements by position
src = open(a.src, 'rb').read()
npcs = {}; place_count = collections.Counter(); disabled_at = {}
for r in iter_records(src):
    if r.sig == 'NPC_':
        s = dict(subrecords(src, r))
        flags = struct.unpack_from('<I', s['ACBS'], 0)[0] if 'ACBS' in s and len(s['ACBS']) >= 4 else 0
        npcs[r.fid & 0xFFFFFF] = dict(edid=s.get('EDID', bytes(1)).rstrip(bytes(1)).decode('latin1'), name=s.get('FULL', b'').rstrip(bytes(1)), female=bool(flags & 1), essential=bool(flags & 2))
for r in iter_records(src):
    if r.sig != 'ACHR': continue
    s = dict(subrecords(src, r))
    if 'NAME' not in s or 'DATA' not in s or len(s['DATA']) < 12: continue
    base = struct.unpack('<I', s['NAME'])[0] & 0xFFFFFF
    place_count[base] += 1
    if (r.flags & 0x800) and not (r.flags & 0x20):
        disabled_at[tuple(round(x, 1) for x in struct.unpack_from('<3f', s['DATA'], 0))] = base
def is_named(base):
    n = npcs.get(base)
    if not n or not n['name']: return False
    return n['name'].decode('latin1').strip().lower() not in GENERIC_NAMES and place_count[base] <= 3

# ---- clone sources (vanilla settlers: same as name_actors.py)
fo4 = open(a.fo4, 'rb').read(); clone_src = {}
for r in iter_records(fo4):
    if r.sig == 'NPC_':
        s = subrecords(fo4, r); e = dict(s).get('EDID', b'').rstrip(bytes(1)).decode('latin1')
        if e in ('REFarmerMale', 'REFarmerFemale'): clone_src[e] = (r, s)
del fo4
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

# ---- CapitalActors.esp tree
data = open(a.plugin, 'rb').read()
masters, _ = plugin_header(data); own = len(masters)
def parse(q, end):
    items = []
    while q < end:
        sig = data[q:q + 4]; size = struct.unpack_from('<I', data, q + 4)[0]
        if sig == b'GRUP':
            items.append(['G', data[q + 8:q + 12], struct.unpack_from('<I', data, q + 12)[0], data[q + 16:q + 24], parse(q + 24, q + size)]); q += size
        else:
            items.append(['R', bytearray(data[q:q + 24 + size]), sig, struct.unpack_from('<I', data, q + 12)[0]]); q += 24 + size
    return items
def ser(it):
    if it[0] == 'R': return bytes(it[1])
    p = b''.join(ser(c) for c in it[4])
    return b'GRUP' + struct.pack('<I', 24 + len(p)) + it[1] + struct.pack('<I', it[2]) + it[3] + p
hdr_end = 24 + struct.unpack_from('<I', data, 4)[0]
top = parse(hdr_end, len(data))
npc_group = next((t for t in top if t[0] == 'G' and t[1] == b'NPC_'), None)
if npc_group is None: sys.exit('plugin has no NPC_ group: run actors/name_actors.py first')
existing = {}; max_low = 0
def scan(items):
    global max_low
    for it in items:
        if it[0] == 'R':
            if (it[3] >> 24) == own: max_low = max(max_low, it[3] & 0xFFFFFF)
            if it[2] == b'NPC_':
                p = 24; rec = it[1]
                while p < len(rec):
                    s = bytes(rec[p:p + 4]); sz = struct.unpack_from('<H', rec, p + 4)[0]
                    if s == b'EDID': existing[bytes(rec[p + 6:p + 6 + sz]).rstrip(bytes(1)).decode('latin1')] = it[3]
                    p += 6 + sz
        else: scan(it[4])
scan(top)
if 'FO3_CG01Dad' in existing: sys.exit('already named (FO3_CG01Dad exists)')

new_ids = {}; clones = []; retargeted = collections.Counter()
def visit(items):
    global max_low
    for it in items:
        if it[0] == 'G': visit(it[4]); continue
        if it[2] != b'ACHR' or not (struct.unpack_from('<I', it[1], 8)[0] & 0x800): continue
        rec = it[1]; p = 24; pos = None; name_off = None
        while p < len(rec):
            s = bytes(rec[p:p + 4]); sz = struct.unpack_from('<H', rec, p + 4)[0]
            if s == b'DATA' and sz >= 12: pos = struct.unpack_from('<3f', rec, p + 6)
            if s == b'NAME': name_off = p + 6
            p += 6 + sz
        if pos is None or name_off is None: continue
        base = disabled_at.get(tuple(round(x, 1) for x in pos))
        if base is None or not is_named(base): continue
        if base not in new_ids:
            ex_ = existing.get('FO3_' + npcs[base]['edid'])
            if ex_ is not None: new_ids[base] = ex_                          # that character already has a clone from name_actors.py (its enabled placement): reuse it
            else:
                max_low += 1; fid = (own << 24) | max_low; n = npcs[base]
                clones.append(make_clone(fid, n['edid'], n['name'], n['female'], n['essential'])); new_ids[base] = fid
        struct.pack_into('<I', rec, name_off, new_ids[base]); retargeted[npcs[base]['edid']] += 1
visit(top)
npc_group[4].extend([['R', c, b'NPC_', struct.unpack_from('<I', c, 12)[0]] for c in clones])
log('new clone NPCs: %d, placements retargeted: %d' % (len(clones), sum(retargeted.values())))
log('characters: ' + ', '.join(sorted(retargeted)))
with open(a.plugin, 'wb') as f:
    f.write(data[:hdr_end])
    for it in top: f.write(ser(it))
log('wrote ' + a.plugin)
