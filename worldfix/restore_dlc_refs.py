"""Put back placed references that xConvert dropped from the five DLC esms (twin of restore_refs.py, which only knows Fallout3.esm).

xConvert drops the editor markers (XMarker 0x3B / XMarkerHeading 0x34: 2,957 refs in the DLC), the map markers and the bottle caps of the DLC plugins; the quest scripts
(Player.MoveTo DLC04LookoutLandingMarkerREF ...), package locations and objective targets address those markers by reference.  This script re-adds, per DLC esm:
  * map markers (source base 0x10) re-based on Fallout 4's MapMarker (0x10), keeping XMRK / FNAM / FULL / TNAM
  * XMarker / XMarkerHeading refs (same base ids in Fallout 4)
  * Caps001 pickups (base 0x0F -> Fallout 4 Caps001)
  * refs whose base object WAS converted (own DLC statics / doors / containers ... or a Fallout3.esm base) that are missing in the converted plugin
Only refs that sit in a cell the DLC itself defines are restored (refs a DLC places into Fallout3.esm cells are skipped).  Each restored ref keeps its source FormID (local id), now with
the converted plugin's own master index (2).  Idempotent: refs that already exist are skipped, so it can be run on the final, patched tool/output/<DLC>.esm in place.

  python restore_dlc_refs.py --dlc Anchorage [--in tool/output/Anchorage.esm] [--out same]   |   --all"""
import argparse, collections, math, os, struct, sys
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records, subrecords, sub, plugin_header

FO3D = 'X:/__CAPITAL_FO3_DATA__/'
OUTD = 'X:/__CAPITAL_WORKDIR__/tool/output/'
DLCS = ['Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta']
ap = argparse.ArgumentParser()
ap.add_argument('--dlc', default=''); ap.add_argument('--all', action='store_true')
ap.add_argument('--in', dest='inp', default=''); ap.add_argument('--out', default='')
a = ap.parse_args()
BASE_SIGS = ('STAT', 'MSTT', 'ACTI', 'DOOR', 'CONT', 'FURN', 'TERM', 'LIGH', 'MISC', 'ALCH', 'BOOK', 'NOTE', 'KEYM', 'TREE', 'SCOL', 'TACT', 'WEAP', 'ARMO', 'AMMO', 'IDLM')
SKIP_BASE_NAMES = ('xmarker', 'collisionmarker', 'roommarker', 'radiationmarker', 'cocmarker', 'portalmarker', 'planemarker', 'multiboundmarker')


def log(m): print(m, flush=True)


def run(name):
    src_path = FO3D + name + '.esm'; in_path = a.inp or (OUTD + name + '.esm'); out_path = a.out or in_path
    ds = open(src_path, 'rb').read(); dc = open(in_path, 'rb').read()
    src_masters, _ = plugin_header(ds); own_src = len(src_masters)
    dst_masters, _ = plugin_header(dc); own_dst = len(dst_masters)
    f3_idx = next(i for i, m in enumerate(dst_masters) if m.lower() == 'fallout3.esm')
    assert src_masters and src_masters[0].lower() == 'fallout3.esm', src_masters

    def to_dst(raw):
        """FormID of the source plugin -> FormID of the converted plugin (own records and Fallout3.esm only), or None"""
        i = raw >> 24
        if i == own_src: return (own_dst << 24) | (raw & 0xFFFFFF)
        if i == 0: return (f3_idx << 24) | (raw & 0xFFFFFF)
        return None

    conv_refs = {r.fid & 0xFFFFFF for r in iter_records(dc) if r.sig == 'REFR' and (r.fid >> 24) == own_dst}
    conv_base = {}
    for r in iter_records(dc):
        if r.sig in BASE_SIGS and (r.fid >> 24) == own_dst: conv_base[(own_dst << 24) | (r.fid & 0xFFFFFF)] = r.sig
    c3 = open(OUTD + 'Fallout3.esm', 'rb').read()
    for r in iter_records(c3):
        if r.sig in BASE_SIGS and (r.fid >> 24) == 1: conv_base[(f3_idx << 24) | (r.fid & 0xFFFFFF)] = r.sig
    del c3
    conv_ids = {r.fid for r in iter_records(dc)}
    src_edid = {}
    for r in iter_records(ds):
        if r.sig == 'STAT': src_edid[r.fid] = dict(subrecords(ds, r)).get('EDID', bytes(1)).rstrip(bytes(1)).decode('latin1')

    def build_ref(r):
        if not r.size: return None, 'empty'
        if r.flags & 0x40000: return None, 'compressed'
        subs = dict(subrecords(ds, r))
        if 'NAME' not in subs or 'DATA' not in subs: return None, 'no NAME/DATA'
        base = struct.unpack('<I', subs['NAME'])[0]
        out = []
        if base == 0x10 and 'XMRK' in subs:
            out += [sub('NAME', struct.pack('<I', 0x10)), sub('XMRK', subs['XMRK'])]
            for k in ('FNAM', 'FULL', 'TNAM'):
                if k in subs: out.append(sub(k, subs[k]))
        elif base == 0x0F:
            out.append(sub('NAME', struct.pack('<I', 0x0F)))
        elif base in (0x34, 0x3B):
            out.append(sub('NAME', struct.pack('<I', base)))
        else:
            nb = to_dst(base)
            if nb is None or nb not in conv_base: return None, 'base not converted'
            if any(src_edid.get(base, '').lower().startswith(x) for x in SKIP_BASE_NAMES): return None, 'marker base'
            out.append(sub('NAME', struct.pack('<I', nb)))
            if 'XTEL' in subs and len(subs['XTEL']) >= 28:
                x = subs['XTEL']; dest = to_dst(struct.unpack_from('<I', x, 0)[0])
                if dest is not None and dest in conv_ids:
                    px, py, pz, rx, ry, rz = struct.unpack_from('<6f', x, 4)
                    flags = struct.unpack_from('<I', x, 28)[0] if len(x) >= 32 else 0
                    if rz < 0: rz += 2 * math.pi
                    out.append(sub('XTEL', struct.pack('<I6fII', dest, px, py, pz, rx, ry, rz, flags, 0)))
            if 'XSCL' in subs: out.append(sub('XSCL', subs['XSCL']))
        if 'EDID' in subs: out.insert(0, sub('EDID', subs['EDID']))
        out.append(sub('DATA', subs['DATA']))
        body = b''.join(out)
        gtype = 8 if (r.flags & 0x400) else 9
        for l, t in r.chain:
            if t == 10: gtype = 10
        return b'REFR' + struct.pack('<IIIIHH', len(body), r.flags & 0xC00, (own_dst << 24) | (r.fid & 0xFFFFFF), 0, 131, 0) + body, gtype

    lost = collections.defaultdict(list)
    stat = collections.Counter()
    for r in iter_records(ds):
        if r.sig != 'REFR' or (r.fid >> 24) != own_src or (r.fid & 0xFFFFFF) in conv_refs: continue
        cell = None
        for l, t in r.chain:
            if t in (6, 8, 9, 10): cell = struct.unpack('<I', l)[0]
        if cell is None or (cell >> 24) != own_src: stat['skipped: cell of another plugin'] += 1; continue
        rec, g = build_ref(r)
        if rec is None: stat['skipped: ' + g] += 1; continue
        lost[(own_dst << 24) | (cell & 0xFFFFFF)].append((g, rec)); stat['restored'] += 1
    log('%s: lost source refs: %s' % (name, dict(stat)))
    del ds
    if not stat['restored']: return

    data = dc

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
    cell_groups = {}; sample_rest = {}

    def index_cells(items):
        for i, it in enumerate(items):
            if it[0] == 'R' and it[2] == b'CELL': cell_groups[it[3]] = (items, i)
            elif it[0] == 'G':
                sample_rest.setdefault(it[2], it[3])
                if it[2] in (0, 1, 2, 3, 4, 5): index_cells(it[4])
    index_cells(top)
    placed = skipped = 0
    for cell, refs in lost.items():
        if cell not in cell_groups: skipped += len(refs); continue
        items, i = cell_groups[cell]
        cell_fid = items[i][3]
        grp6 = items[i + 1] if i + 1 < len(items) and items[i + 1][0] == 'G' and items[i + 1][2] == 6 else None
        if grp6 is None:
            grp6 = ['G', struct.pack('<I', cell_fid), 6, sample_rest.get(6, bytes(8)), []]
            items.insert(i + 1, grp6)
            for k, (its, j) in list(cell_groups.items()):
                if its is items and j > i: cell_groups[k] = (its, j + 1)
        for gtype, rec in refs:
            sub_g = next((g for g in grp6[4] if g[0] == 'G' and g[2] == gtype), None)
            if sub_g is None:
                sub_g = ['G', struct.pack('<I', cell_fid), gtype, sample_rest.get(gtype, bytes(8)), []]
                grp6[4].append(sub_g)
            sub_g[4].append(['R', rec, b'REFR', 0]); placed += 1
    log('%s: placed %d refs; %d skipped (cell not found in the converted plugin)' % (name, placed, skipped))
    tmp = out_path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data[:hdr_end])
        for it in top: f.write(ser(it))
    os.replace(tmp, out_path)
    log('wrote ' + out_path)


names = DLCS if a.all else [a.dlc]
assert names and names[0], 'give --dlc <name> or --all'
for n in names: run(n)
