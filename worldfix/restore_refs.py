"""Put back placed references that xConvert dropped, into the converted Fallout3.esm.

Dropped refs fall in three groups, restored here:
  * Map markers  (source base 0x10 'MapMarker'): re-based on Fallout 4's own MapMarker (0x00000010), keeping XMRK/FNAM/FULL/TNAM so locations show on the map
  * Markers (XMarker 0x3B / XMarkerHeading 0x34, same ids in FO4): ~6,200 refs that scripts use as MoveTo / package targets
  * Bottle caps  (source base 0x0F 'Caps001'):   re-based on Fallout 4's Caps001 (0x0000000F)
  * Any ref whose base object WAS converted (statics, doors, containers ... ~220 refs in cells that failed to convert): copied with NAME/DATA/XSCL/EDID/XTEL
Everything else (XMarkers, room/collision/radiation markers, sound emitters, effects) is skipped on purpose.

  python restore_refs.py --src <FO3 Fallout3.esm> --in <converted esm> --out <esm with refs restored>
Each restored ref keeps its source FormID (low 24 bits, master index 01); flags keep Persistent (0x400) / Initially Disabled (0x800);
persistent refs go in the cell's persistent-children group (8), others in temporary (9) / visible-distant (10) as in the source."""
import argparse, collections, math, struct, sys
sys.path.insert(0, r'X:\__CAPITAL_WORKDIR__\navmesh')
from navlib import iter_records, subrecords, sub

ap = argparse.ArgumentParser()
ap.add_argument('--src', required=True); ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--out', required=True)
a = ap.parse_args()
def log(m): print(m, flush=True)

# ------------------------------------------------------------------ source: which refs exist, which are lost
ds = open(a.src, 'rb').read()
dc = open(a.inp, 'rb').read()
conv_refs = {r.fid & 0xFFFFFF for r in iter_records(dc) if r.sig == 'REFR'}
conv_base = {}
for r in iter_records(dc):
    if r.sig in ('STAT', 'MSTT', 'ACTI', 'DOOR', 'CONT', 'FURN', 'TERM', 'LIGH', 'MISC', 'ALCH', 'BOOK', 'NOTE', 'KEYM', 'TREE', 'SCOL', 'TACT', 'WEAP', 'ARMO', 'AMMO', 'IDLM'):
        conv_base[r.fid & 0xFFFFFF] = r.sig
conv_ids = {r.fid & 0xFFFFFF for r in iter_records(dc)}
SKIP_BASE_NAMES = ('xmarker', 'collisionmarker', 'roommarker', 'radiationmarker', 'cocmarker', 'portalmarker', 'planemarker', 'multiboundmarker')
src_edid = {}
for r in iter_records(ds):
    if r.sig == 'STAT':
        src_edid[r.fid] = dict(subrecords(ds, r)).get('EDID', bytes(1)).rstrip(bytes(1)).decode('latin1')

def build_ref(r):
    """-> (record bytes, group type) or (None, reason)"""
    if not r.size:
        return None, 'empty'
    if r.flags & 0x40000:
        return None, 'compressed'
    subs = dict(subrecords(ds, r))
    if 'NAME' not in subs or 'DATA' not in subs:
        return None, 'no NAME/DATA'
    base = struct.unpack('<I', subs['NAME'])[0]
    low = base & 0xFFFFFF
    out = []
    if base == 0x10 and 'XMRK' in subs:
        newbase = 0x00000010                                    # Fallout 4's MapMarker
        out += [sub('NAME', struct.pack('<I', newbase)), sub('XMRK', subs['XMRK'])]
        for k in ('FNAM', 'FULL', 'TNAM'):
            if k in subs:
                out.append(sub(k, subs[k]))
    elif base == 0x0F:
        out.append(sub('NAME', struct.pack('<I', 0x0000000F)))  # Fallout 4's Caps001
    elif base in (0x34, 0x3B):
        out.append(sub('NAME', struct.pack('<I', base)))        # XMarkerHeading / XMarker: same FormIDs in Fallout 4; scripts (MoveTo, quest packages) address them by reference
    elif (base >> 24) == 0 and low in conv_base:
        edn = src_edid.get(base, '').lower()
        if any(edn.startswith(x) for x in SKIP_BASE_NAMES):
            return None, 'marker base'
        out.append(sub('NAME', struct.pack('<I', 0x01000000 | low)))
        if 'XTEL' in subs and len(subs['XTEL']) >= 28:
            x = subs['XTEL']
            dest = struct.unpack_from('<I', x, 0)[0]
            if (dest >> 24) == 0 and (dest & 0xFFFFFF) in conv_ids:
                px, py, pz, rx, ry, rz = struct.unpack_from('<6f', x, 4)
                flags = struct.unpack_from('<I', x, 28)[0] if len(x) >= 32 else 0
                if rz < 0:
                    rz += 2 * math.pi
                out.append(sub('XTEL', struct.pack('<I6fII', 0x01000000 | (dest & 0xFFFFFF), px, py, pz, rx, ry, rz, flags, 0)))
        if 'XSCL' in subs:
            out.append(sub('XSCL', subs['XSCL']))
    else:
        return None, 'base not converted'
    if 'EDID' in subs:
        out.insert(0, sub('EDID', subs['EDID']))
    out.append(sub('DATA', subs['DATA']))
    body = b''.join(out)
    flags = r.flags & 0xC00
    gtype = 8 if (r.flags & 0x400) else 9
    for l, t in r.chain:
        if t == 10:
            gtype = 10
    rec = b'REFR' + struct.pack('<IIIIHH', len(body), flags, 0x01000000 | (r.fid & 0xFFFFFF), 0, 131, 0) + body
    return rec, gtype

lost = collections.defaultdict(list)        # cell fid (source, low24) -> [(group type, record bytes)]
stat = collections.Counter()
for r in iter_records(ds):
    if r.sig != 'REFR' or (r.fid & 0xFFFFFF) in conv_refs:
        continue
    cell = 0
    for l, t in r.chain:
        if t in (6, 8, 9, 10):
            cell = struct.unpack('<I', l)[0]
    rec, g = build_ref(r)
    if rec is None:
        stat['skipped: ' + g] += 1
        continue
    lost[cell & 0xFFFFFF].append((g, rec))
    stat['restored'] += 1
log('lost source refs: %s' % dict(stat))
del ds

# ------------------------------------------------------------------ tree of the converted plugin (CELL + WRLD top groups deep, the rest raw)
data = dc
def parse(q, end):
    items = []
    while q < end:
        sig = data[q:q + 4]; size = struct.unpack_from('<I', data, q + 4)[0]
        if sig == b'GRUP':
            gtype = struct.unpack_from('<I', data, q + 12)[0]
            label = data[q + 8:q + 12]
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
    if it[0] in ('R', 'RAW'):
        return it[1]
    p = b''.join(ser(c) for c in it[4])
    return b'GRUP' + struct.pack('<I', 24 + len(p)) + it[1] + struct.pack('<I', it[2]) + it[3] + p

hdr_end = 24 + struct.unpack_from('<I', data, 4)[0]
top = parse(hdr_end, len(data))
cell_groups = {}                 # cell low24 -> (container items list, index of CELL record)
sample_rest = {}
def index_cells(items):
    for i, it in enumerate(items):
        if it[0] == 'R' and it[2] == b'CELL':
            cell_groups[it[3] & 0xFFFFFF] = (items, i)
        elif it[0] == 'G':
            sample_rest.setdefault(it[2], it[3])
            if it[2] in (0, 1, 2, 3, 4, 5):
                index_cells(it[4])
index_cells(top)

placed = skipped = 0
for cell, refs in lost.items():
    if cell not in cell_groups:
        skipped += len(refs); continue
    items, i = cell_groups[cell]
    cell_fid = items[i][3]
    grp6 = items[i + 1] if i + 1 < len(items) and items[i + 1][0] == 'G' and items[i + 1][2] == 6 else None
    if grp6 is None:
        grp6 = ['G', struct.pack('<I', cell_fid), 6, sample_rest.get(6, bytes(8)), []]
        items.insert(i + 1, grp6)
        # indexes of later cells in this list shift by one
        for k, (its, j) in list(cell_groups.items()):
            if its is items and j > i:
                cell_groups[k] = (its, j + 1)
    for gtype, rec in refs:
        sub_g = next((g for g in grp6[4] if g[0] == 'G' and g[2] == gtype), None)
        if sub_g is None:
            sub_g = ['G', struct.pack('<I', cell_fid), gtype, sample_rest.get(gtype, bytes(8)), []]
            grp6[4].append(sub_g)
        sub_g[4].append(['R', rec, b'REFR', 0])
        placed += 1
log('placed %d refs; %d skipped (cell not found in converted plugin)' % (placed, skipped))
with open(a.out, 'wb') as f:
    f.write(data[:hdr_end])
    for it in top:
        f.write(ser(it))
log('wrote ' + a.out)
