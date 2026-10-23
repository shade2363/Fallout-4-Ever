"""Repair the converted Fallout3.esm: move exterior cells that xConvert wrote as stub *interior* cells back into their worldspace.

Why: FO3 has ~35,000 exterior cells whose XCLC subrecord is the old 8-byte form (x,y, no flags). The converter could not read it,
so it created an empty interior CELL stub (DATA=interior, LTMP) and hung the cell's LAND under it. The terrain existed in the file
but belonged to no worldspace => void outside the cells that did convert.

This script (read-only on its inputs, writes --out):
  * finds stub interior cells whose source record is an exterior cell (grid from the source XCLC)
  * rebuilds each as a normal FO4 exterior CELL (DATA u16, XCLC 12 bytes, XCLW "no water", same FormID)
  * files it, with its existing child groups (LAND), in the right WRLD > block > sub-block
  * drops the stubs from the interior block/sub-block groups
Usage: python fix_stub_cells.py --conv <converted Fallout3.esm> --src <source Fallout3.esm> --out <fixed.esm>
"""
import argparse, struct, sys, collections
sys.path.insert(0, r'X:\__CAPITAL_WORKDIR__\navmesh')
from navlib import iter_records, subrecords, sub

ap = argparse.ArgumentParser()
ap.add_argument('--conv', required=True)
ap.add_argument('--src', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--master-index', type=lambda x: int(x, 0), default=0x01000000, help='FormID high byte of the converted plugin (self index)')
args = ap.parse_args()

def log(m): print(m, flush=True)

# ------------------------------------------------------------------ source: exterior cells that need rebuilding
log('reading source cells ...')
ds = open(args.src, 'rb').read()
src_ext = {}   # low 24 bits of cell fid -> (world fid low24, x, y, data byte)
for r in iter_records(ds):
    if r.sig != 'CELL' or not any(t == 4 for l, t in r.chain):
        continue
    world = [struct.unpack('<I', l)[0] for l, t in r.chain if t == 1][0]
    subs = dict(subrecords(ds, r))
    x, y = struct.unpack_from('<ii', subs['XCLC'])
    src_ext[r.fid & 0xFFFFFF] = (world & 0xFFFFFF, x, y, subs.get('DATA', b'\0')[0], subs.get('EDID'))
del ds
log('  exterior source cells: %d' % len(src_ext))

# ------------------------------------------------------------------ tree parse of the converted plugin
data = open(args.conv, 'rb').read()
log('parsing converted plugin (%.1f MB) ...' % (len(data) / 1048576))
DEEP = (0, 1, 2, 3, 4, 5)  # group types we descend into; cell-children groups (6,8,9,10) stay opaque

def parse(a, b, deep_top=False):
    items = []
    q = a
    while q < b:
        sig = data[q:q + 4]
        size = struct.unpack_from('<I', data, q + 4)[0]
        if sig == b'GRUP':
            label = data[q + 8:q + 12]
            gtype = struct.unpack_from('<I', data, q + 12)[0]
            rest = data[q + 16:q + 24]
            if gtype in DEEP and (gtype != 0 or label in (b'CELL', b'WRLD')):
                items.append(['G', label, gtype, rest, parse(q + 24, q + size)])
            else:
                items.append(['RAW', data[q:q + size]])
            q += size
        else:
            items.append(['R', data[q:q + 24 + size], sig, struct.unpack_from('<I', data, q + 12)[0]])
            q += 24 + size
    return items

top = parse(0, len(data))

def ser(it):
    k = it[0]
    if k in ('R', 'RAW'):
        return it[1]
    payload = b''.join(ser(c) for c in it[4])
    return b'GRUP' + struct.pack('<I', 24 + len(payload)) + it[1] + struct.pack('<I', it[2]) + it[3] + payload

# ------------------------------------------------------------------ pull stubs out of the interior CELL group
cell_top = next(g for g in top if g[0] == 'G' and g[1] == b'CELL')
stubs = {}   # low24 -> (cell record bytes (stub), children RAW item or None)
removed = 0
for blk in list(cell_top[4]):
    if blk[0] != 'G':
        continue
    for sb in list(blk[4]):
        if sb[0] != 'G':
            continue
        kids = sb[4]
        out = []
        i = 0
        while i < len(kids):
            it = kids[i]
            if it[0] == 'R' and it[2] == b'CELL' and (it[3] & 0xFFFFFF) in src_ext:
                children = None
                if i + 1 < len(kids) and kids[i + 1][0] == 'RAW' and kids[i + 1][1][:4] == b'GRUP':
                    children = kids[i + 1]; i += 1
                stubs[it[3] & 0xFFFFFF] = (it, children)
                removed += 1
            else:
                out.append(it)
            i += 1
        sb[4] = out
    blk[4] = [sb for sb in blk[4] if not (sb[0] == 'G' and not sb[4])]
cell_top[4] = [blk for blk in cell_top[4] if not (blk[0] == 'G' and not blk[4])]
log('stub interior cells found: %d (of %d exterior source cells)' % (removed, len(src_ext)))

# ------------------------------------------------------------------ rebuild as exterior cells in the worldspaces
wrld_top = next(g for g in top if g[0] == 'G' and g[1] == b'WRLD')
world_children = {}   # world fid -> the type-1 group
for it in wrld_top[4]:
    if it[0] == 'G' and it[2] == 1:
        world_children[struct.unpack('<I', it[1])[0]] = it
sample_rest = None
for wc in world_children.values():
    for b in wc[4]:
        if b[0] == 'G' and b[2] == 4:
            sample_rest = b[3]; break
    if sample_rest: break

def cell_record(low24, x, y, dbyte, edid):
    subs = []
    if edid:
        subs.append(sub('EDID', edid))
    subs.append(sub('DATA', struct.pack('<H', dbyte & 0xFF)))
    subs.append(sub('XCLC', struct.pack('<iiI', x, y, 0)))
    subs.append(sub('XCLW', b'\xff\xff\x7f\x7f'))
    body = b''.join(subs)
    fid = args.master_index | low24
    raw = b'CELL' + struct.pack('<IIIIHH', len(body), 0, fid, 0, 0, 0) + body
    return ['R', raw, b'CELL', fid]

def find_or_add(parent_items, label, gtype):
    for it in parent_items:
        if it[0] == 'G' and it[2] == gtype and it[1] == label:
            return it
    g = ['G', label, gtype, sample_rest, []]
    parent_items.append(g)
    return g

placed = collections.Counter(); skipped = []
for low24, (stub, children) in sorted(stubs.items()):
    world, x, y, dbyte, edid = src_ext[low24]
    wc = world_children.get(args.master_index | world)
    if wc is None:
        skipped.append(low24); continue
    blk = find_or_add(wc[4], struct.pack('<hh', y // 32, x // 32), 4)
    sbk = find_or_add(blk[4], struct.pack('<hh', y // 8, x // 8), 5)
    sbk[4].append(cell_record(low24, x, y, dbyte, edid))
    if children is not None:
        sbk[4].append(children)
    placed[world] += 1
log('placed: %s  skipped(no world group): %d' % ({('%06X' % k): v for k, v in placed.items()}, len(skipped)))

# ------------------------------------------------------------------ write
log('serialising ...')
with open(args.out, 'wb') as f:
    for it in top:
        f.write(ser(it))
log('wrote %s' % args.out)
