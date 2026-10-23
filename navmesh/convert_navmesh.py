"""Convert Fallout 3 / New Vegas navmeshes (NAVM + NAVI) to Fallout 4 format.

    python convert_navmesh.py --src <FO3 or FNV .esm> --conv <converted FO4-format .esm> --out <new .esp>
                              [--vanilla-navi <Fallout4.esm>] [--limit N]

The conversion rules were derived by comparing an original New Vegas navmesh set with its converted counterpart (reference project,
read-only) and are reproduced here from scratch:
  triangles : vertices and edges copied, 9 extra bytes (FLT_MAX float + [0,0,(flags>>8)&6,0,0])
  edge links: type/triangle copied, neighbour mesh -> new FormID, edge = edge of the neighbour triangle nearest to this mesh
  doors     : triangle copied, CRC E48B73F3, door ref -> converted-plugin FormID (dropped when the ref no longer exists)
  grid      : header copied, per-cell triangle counts widened from u16 to u32
Only standard library; never writes to an input file.
"""
import argparse
import collections
import math
import struct
import sys
import time

sys.path.insert(0, __file__.rsplit('\\', 1)[0] if '\\' in __file__ else '.')
from navlib import iter_records, record_bytes, subrecords, plugin_header, sub, record, group  # noqa: E402

MAGIC = 0xA5E9A03C        # CRC hash written in every FO4 pathing cell
DOOR_CRC = 0xE48B73F3     # 'PathingDoor'
FLT_MAX = b'\xff\xff\x7f\x7f'
NEW_INDEX = 2             # our records live at master index 2 (masters: Fallout4.esm, <converted plugin>)
SRC_TO_CONV = 1           # a base-plugin FormID 00xxxxxx becomes 01xxxxxx in the converted plugin (= CONV_INDEX)
# DLC runs (--own-src / --conv-own / --conv-index / --new-index / --id-base): the source plugin's own FormIDs have prefix OWN_SRC (its master count), the converted plugin's own records
# prefix CONV_OWN, and the converted plugin sits at CONV_INDEX of the output plugin's master list; the base game keeps 0 / 1 / 1 and changes nothing
OWN_SRC = 0
CONV_OWN = 1
CONV_INDEX = 1
ID_BASE = 0x800
FID_TAGS = {'LTMP', 'XCIM', 'XEZN', 'XCWT', 'XCCM', 'XLCN', 'XOWN', 'XCAS', 'XCMO', 'XILL', 'CNAM', 'NAM2', 'NAM3', 'NAM4', 'ZNAM', 'WNAM', 'TNAM', 'XLRL'}


def log(*a):
    print('[%7.1fs]' % (time.time() - T0), *a, flush=True)


T0 = time.time()


def mapfid(f):
    """Source FormID (base plugin, index 00) -> FormID inside the converted plugin."""
    if f >> 24 != OWN_SRC:
        return None
    return (CONV_INDEX << 24) | (f & 0xFFFFFF)


# ------------------------------------------------------------------ source side
class SrcMesh:
    __slots__ = ('fid', 'cell', 'nv', 'nt', 'verts', 'tris', 'nex', 'ext', 'doors', 'grid', 'world', 'gx', 'gy', 'newid')


def read_source(path):
    data = open(path, 'rb').read()
    cells = {}      # fid -> (world fid or 0, gx, gy)
    navms = {}
    navi = None
    for r in iter_records(data):
        if r.sig == 'CELL':
            world = 0
            for label, gtype in r.chain:
                if gtype == 1:
                    world = struct.unpack('<I', label)[0]
            gx = gy = 0
            for s, b in subrecords(data, r):
                if s == 'XCLC' and len(b) >= 8:
                    gx, gy = struct.unpack_from('<ii', b, 0)
            cells[r.fid] = (world, gx, gy)
        elif r.sig == 'NAVM':
            subs = dict(subrecords(data, r))
            if 'DATA' not in subs: continue         # deleted record (flag 0x20): DLC plugins delete / stub some navmeshes
            m = SrcMesh()
            m.fid = r.fid
            m.cell, m.nv, m.nt, m.nex, ncov, ndoor = struct.unpack('<6I', subs['DATA'])
            m.verts = subs.get('NVVX', b'')
            m.tris = subs.get('NVTR', b'')
            m.ext = subs.get('NVEX', b'')
            m.doors = subs.get('NVDP', b'')
            m.grid = subs.get('NVGD', b'')
            navms[r.fid] = m
        elif r.sig == 'NAVI':
            navi = subrecords(data, r)
    return cells, navms, navi


# ------------------------------------------------------------------ converted side
def cvn(f):
    """FormID of the converted file -> FormID in the output plugin's master list"""
    return (CONV_INDEX << 24) | (f & 0xFFFFFF) if (f >> 24) == CONV_OWN else f


def conv_record(data, r):
    """record bytes of the converted file as they must appear in the output plugin (own FormIDs renumbered when the converted plugin has another master index there)"""
    if CONV_OWN == CONV_INDEX:
        return record_bytes(data, r)
    subs = []
    for k, v in subrecords(data, r):
        if k in FID_TAGS and len(v) == 4 and v[3] == CONV_OWN: v = v[:3] + bytes([CONV_INDEX])
        subs.append(sub(k, v))
    return record(r.sig, cvn(r.fid), subs, flags=r.flags & ~0x40000, ver=r.ver)


def read_converted(path):
    data = open(path, 'rb').read()
    worlds = {}     # fid -> record bytes
    ext_cells = {}  # fid -> (world fid, block label, subblock label, record bytes)
    int_cells = {}  # fid -> (block label, subblock label, record bytes)
    refs = set()
    for r in iter_records(data):
        if r.sig == 'WRLD':
            worlds[cvn(r.fid)] = conv_record(data, r)
        elif r.sig == 'CELL':
            ch = r.chain
            if len(ch) >= 4 and ch[0][1] == 0 and ch[0][0] == b'WRLD' and ch[2][1] == 4 and ch[3][1] == 5:
                ext_cells[cvn(r.fid)] = (cvn(struct.unpack('<I', ch[1][0])[0]), ch[2][0], ch[3][0], conv_record(data, r))
            elif len(ch) >= 3 and ch[0][0] == b'CELL' and ch[1][1] == 2 and ch[2][1] == 3:
                int_cells[cvn(r.fid)] = (ch[1][0], ch[2][0], conv_record(data, r))
        elif r.sig in ('REFR', 'ACHR'):
            refs.add(cvn(r.fid))
    return worlds, ext_cells, int_cells, refs


# ------------------------------------------------------------------ geometry helpers
def build_grid_index(segs, size=256.0):
    idx = collections.defaultdict(list)
    for k, (ax, ay, bx, by) in enumerate(segs):
        x0, x1 = sorted((ax, bx)); y0, y1 = sorted((ay, by))
        for gx in range(int(x0 // size), int(x1 // size) + 1):
            for gy in range(int(y0 // size), int(y1 // size) + 1):
                idx[(gx, gy)].append(k)
    return idx


def dseg(px, py, s):
    ax, ay, bx, by = s
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    u = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + u * dx), py - (ay + u * dy))


class MeshGeo:
    """Vertices/triangles/segments of a source mesh, with a spatial index for nearest-boundary queries."""

    def __init__(self, m):
        self.v = [struct.unpack_from('<3f', m.verts, 12 * k) for k in range(m.nv)]
        self.t = [struct.unpack_from('<3H3H', m.tris, 16 * k) for k in range(m.nt)]
        self.segs = []
        for tt in self.t:
            for k in range(3):
                a = self.v[tt[k]]; b = self.v[tt[(k + 1) % 3]]
                self.segs.append((a[0], a[1], b[0], b[1]))
        self._idx = None

    @property
    def idx(self):
        if self._idx is None:
            self._idx = build_grid_index(self.segs)
        return self._idx

    def nearest(self, px, py):
        size = 256.0
        gx, gy = int(px // size), int(py // size)
        best = 1e30
        for ring in range(0, 3):
            cand = set()
            for ix in range(gx - ring, gx + ring + 1):
                for iy in range(gy - ring, gy + ring + 1):
                    cand.update(self.idx.get((ix, iy), ()))
            for k in cand:
                d = dseg(px, py, self.segs[k])
                if d < best:
                    best = d
            if best <= size * ring or best < 4.0:
                return best
        # fall back to a full scan
        for s in self.segs:
            d = dseg(px, py, s)
            if d < best:
                best = d
        return best


def link_edge(geo_this, geo_nb, tri_idx):
    """Edge of the neighbour's triangle (tri_idx) nearest to this mesh's boundary."""
    if tri_idx >= len(geo_nb.t):
        return 0
    tt = geo_nb.t[tri_idx]
    if geo_this is geo_nb:
        # link to the same mesh: every edge touches it, the reference picks the edge whose adjacent triangle is farthest away
        def cen(t):
            vs = [geo_nb.v[t[i]] for i in range(3)]
            return (sum(v[0] for v in vs) / 3, sum(v[1] for v in vs) / 3)
        c0 = cen(tt)
        far = []
        for e in range(3):
            adj = tt[3 + e]
            if adj == 0xFFFF or adj >= len(geo_nb.t):
                far.append(-1.0)
            else:
                c1 = cen(geo_nb.t[adj]); far.append(math.hypot(c0[0] - c1[0], c0[1] - c1[1]))
        return far.index(max(far))
    best, pick = None, 0
    for k in range(3):
        p = geo_nb.v[tt[k]]; q = geo_nb.v[tt[(k + 1) % 3]]
        d = geo_this.nearest((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        if best is None or d < best:
            best, pick = d, k
    return pick


# ------------------------------------------------------------------ conversion
FLAG_MASK = 0x57


def convert_tris(raw, nt):
    out = bytearray()
    for t in range(nt):
        s = raw[16 * t:16 * t + 16]
        flags, = struct.unpack_from('<I', s, 12)
        # verified on all 392 distinct flag values: byte1 = flags & 0x57, byte2 = (flags >> 8) & 0x06
        out += s[:12] + FLT_MAX + b'\x00' + bytes([flags & FLAG_MASK, (flags >> 8) & 0x06]) + b'\x00\x00'
    return bytes(out)


def convert_grid(g):
    div, = struct.unpack_from('<I', g, 0)
    out = bytearray(g[:36])
    o = 36
    for _ in range(div * div):
        n, = struct.unpack_from('<H', g, o); o += 2
        out += struct.pack('<I', n) + g[o:o + 2 * n]
        o += 2 * n
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--conv', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--vanilla-navi', default=r'X:\__CAPITAL_FO4__\Data\Fallout4.esm')
    ap.add_argument('--masters', default='Fallout4.esm,Fallout3.esm', help='masters of the output plugin; the 2nd must be the converted plugin')
    ap.add_argument('--limit', type=int, default=0, help='convert only the first N navmeshes (testing)')
    ap.add_argument('--skip', type=int, default=0, help='bisect aid: skip the first N convertible navmeshes (in NAVI order) before --limit')
    ap.add_argument('--report', default='')
    ap.add_argument('--cells-only', action='store_true', help='bisect aid: emit the cell overrides without any NAVM children')
    ap.add_argument('--navi', choices=('full', 'none', 'nonvpp'), default='full',
                    help='NAVI record: full (NVER+NVMI+vanilla NVPP), none (omit), nonvpp (no NVPP) - for bisecting crashes')
    ap.add_argument('--no-doors', action='store_true', help='bisect aid: drop all door triangles')
    ap.add_argument('--flag-mask', type=lambda x: int(x, 0), default=0x57, help='mask applied to the low byte of source triangle flags (bisect aid)')
    ap.add_argument('--own-src', type=int, default=0, help='DLC: prefix of the own FormIDs of the source plugin (its master count)')
    ap.add_argument('--conv-own', type=int, default=1, help='DLC: prefix of the own records inside the converted plugin')
    ap.add_argument('--conv-index', type=int, default=1, help='DLC: index of the converted plugin in the master list of the output plugin')
    ap.add_argument('--new-index', type=int, default=2, help='index of the output plugin itself (= its master count)')
    ap.add_argument('--id-base', type=lambda x: int(x, 0), default=0x800, help='first local FormID of the converted navmeshes')
    args = ap.parse_args()
    global FLAG_MASK, OWN_SRC, CONV_OWN, CONV_INDEX, NEW_INDEX, ID_BASE
    FLAG_MASK = args.flag_mask
    OWN_SRC, CONV_OWN, CONV_INDEX, NEW_INDEX, ID_BASE = args.own_src, args.conv_own, args.conv_index, args.new_index, args.id_base

    log('reading source', args.src)
    cells, navms, navi = read_source(args.src)
    log('source: %d cells, %d navmeshes, NAVI entries %d' % (len(cells), len(navms), sum(1 for k, v in navi if k == 'NVMI')))
    log('reading converted', args.conv)
    worlds, ext_cells, int_cells, refs = read_converted(args.conv)
    log('converted: %d worlds, %d exterior cells, %d interior cells, %d refs' % (len(worlds), len(ext_cells), len(int_cells), len(refs)))

    nvmi = {}
    nvci = {}
    order = []
    for k, v in navi:
        if k == 'NVMI':
            nav, = struct.unpack_from('<I', v, 4)
            nvmi[nav] = v
            order.append(nav)
    for k, v in navi:
        if k == 'NVCI':
            nav, = struct.unpack_from('<I', v, 0)
            o = 4; arrs = []
            for _ in range(3):
                n, = struct.unpack_from('<I', v, o); o += 4
                arrs.append(list(struct.unpack_from('<%dI' % n, v, o))); o += 4 * n
            nvci[nav] = arrs

    # ---- which navmeshes can be converted
    kept = []
    skipped = collections.Counter()
    for nav in order:
        m = navms.get(nav)
        if m is None:
            skipped['no NAVM record for NAVI entry'] += 1; continue
        cf = mapfid(m.cell)
        world, gx, gy = cells.get(m.cell, (0, 0, 0))
        if cf is None:
            skipped['cell from another plugin'] += 1; continue
        if world:
            wf = mapfid(world)
            if wf not in worlds or cf not in ext_cells:
                skipped['exterior cell/world missing in converted plugin'] += 1; continue
            m.world, m.gx, m.gy = wf, gx, gy
        else:
            if cf not in int_cells:
                skipped['interior cell missing in converted plugin'] += 1; continue
            m.world, m.gx, m.gy = 0, 0, 0
        kept.append(m)
        if args.limit and len(kept) >= args.limit + args.skip:
            break
    kept = kept[args.skip:]
    kept.sort(key=lambda mm: mm.fid)        # the reference numbers navmeshes in ascending source-FormID order
    for i, m in enumerate(kept):
        m.newid = (NEW_INDEX << 24) | (ID_BASE + i)
    newid_of = {m.fid: m.newid for m in kept}
    log('convertible navmeshes: %d (skipped: %s)' % (len(kept), dict(skipped)))

    # ---- NVNM per mesh
    geos = {}
    def geo(fid):
        if fid not in geos:
            geos[fid] = MeshGeo(navms[fid])
        return geos[fid]

    stats = collections.Counter()
    navm_by_cell = collections.defaultdict(list)
    nvmi_out = []
    kept_set = set(newid_of)
    merged_map = {}
    for m in kept:
        cf = mapfid(m.cell)
        if m.world:
            parent = struct.pack('<hh', m.gy, m.gx)
        else:
            parent = struct.pack('<I', cf)
        head = struct.pack('<IIII', 15, MAGIC, m.world, 0)[:12] + parent
        # edge links
        links = bytearray(); nl = 0
        g_this = None
        for k in range(m.nex):
            ty, nb, tri = struct.unpack_from('<IIH', m.ext, 10 * k)
            if nb not in kept_set:
                stats['edge link dropped (neighbour not converted)'] += 1; continue
            if g_this is None:
                g_this = geo(m.fid)
            edge = link_edge(g_this, geo(nb), tri)
            links += struct.pack('<IIHB', ty, newid_of[nb], tri, edge)
            nl += 1
        doors = bytearray(); nd = 0
        for k in range(len(m.doors) // 8):
            dref, tri, unk = struct.unpack_from('<IHH', m.doors, 8 * k)
            cref = mapfid(dref)
            if args.no_doors or cref is None or cref not in refs:
                stats['door triangle dropped (door ref not in converted plugin)'] += 1; continue
            doors += struct.pack('<HII', tri, DOOR_CRC, cref)
            nd += 1
        nvnm = (head + struct.pack('<I', m.nv) + m.verts + struct.pack('<I', m.nt) + convert_tris(m.tris, m.nt)
                + struct.pack('<I', nl) + bytes(links) + struct.pack('<I', nd) + bytes(doors)
                + struct.pack('<III', 0, 0, 0) + convert_grid(m.grid))
        navm_by_cell[cf].append(record('NAVM', m.newid, [sub('NVNM', nvnm)]))
        stats['navmeshes converted'] += 1

    # ---- NAVI entries
    inv_merge = collections.defaultdict(set)
    for m in kept:
        for x in nvci.get(m.fid, [[], [], []])[0]:
            if x in kept_set:
                inv_merge[x].add(m.fid)
    for m in kept:
        cf = mapfid(m.cell)
        a = nvci.get(m.fid, [[], [], []])
        merged = sorted(set(newid_of[x] for x in a[0] if x in kept_set) | set(newid_of[x] for x in inv_merge[m.fid]))
        pref = [newid_of[x] for x in a[1] if x in kept_set]
        ldoors = sorted((DOOR_CRC, mapfid(x)) for x in a[2] if mapfid(x) in refs)
        # approximate location = mean of the mesh's vertices (verified against all 4,771 reference entries)
        nvx = navms[m.fid].verts
        pts = [struct.unpack_from('<3f', nvx, 12 * k) for k in range(m.nv)]
        loc = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts), sum(p[2] for p in pts) / len(pts))
        if m.world:
            parent = struct.pack('<hh', m.gy, m.gx)
        else:
            parent = struct.pack('<I', cf)
        e = (struct.pack('<I', m.newid) + struct.pack('<I3fI', 0, *loc, 0)
             + struct.pack('<I', len(merged)) + b''.join(struct.pack('<I', x) for x in merged)
             + struct.pack('<I', len(pref)) + b''.join(struct.pack('<I', x) for x in pref)
             + struct.pack('<I', len(ldoors)) + b''.join(struct.pack('<II', c, r) for c, r in ldoors)
             + b'\x00' + struct.pack('<III', MAGIC, m.world, 0)[:8] + parent)
        nvmi_out.append(sub('NVMI', e))

    # ---- vanilla NVPP (preferred pathing) copied so the base game's long-range pathing hints survive
    vd = open(args.vanilla_navi, 'rb').read()
    vnavi = [r for r in iter_records(vd) if r.sig == 'NAVI'][0]
    vsubs = subrecords(vd, vnavi)
    nvpp = [b for k, b in vsubs if k == 'NVPP'][0]
    navi_subs = [sub('NVER', struct.pack('<I', 15))] + nvmi_out + ([] if args.navi == 'nonvpp' else [sub('NVPP', nvpp)])
    navi_rec = record('NAVI', vnavi.fid, navi_subs)

    # ---- assemble groups
    log('assembling groups')
    def cell_entry(cf, cell_bytes):
        if args.cells_only:
            return cell_bytes
        navs = b''.join(navm_by_cell[cf])
        cfb = struct.pack('<I', cf)
        return cell_bytes + group(cfb, 6, group(cfb, 9, navs))

    # exterior
    wtree = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    itree = collections.defaultdict(lambda: collections.defaultdict(list))
    for cf in navm_by_cell:
        if cf in ext_cells:
            w, blk, sb, cb = ext_cells[cf]
            wtree[w][blk][sb].append((cf, cb))
        else:
            blk, sb, cb = int_cells[cf]
            itree[blk][sb].append((cf, cb))
    world_payloads = []
    for w in sorted(wtree):
        blocks = b''
        for blk in sorted(wtree[w]):
            subs_ = b''
            for sb in sorted(wtree[w][blk]):
                subs_ += group(sb, 5, b''.join(cell_entry(cf, cb) for cf, cb in sorted(wtree[w][blk][sb])))
            blocks += group(blk, 4, subs_)
        world_payloads.append(worlds[w] + group(struct.pack('<I', w), 1, blocks))
    cell_blocks = b''
    for blk in sorted(itree):
        subs_ = b''
        for sb in sorted(itree[blk]):
            subs_ += group(sb, 3, b''.join(cell_entry(cf, cb) for cf, cb in sorted(itree[blk][sb])))
        cell_blocks += group(blk, 2, subs_)
    body = b''
    if cell_blocks:
        body += group(b'CELL', 0, cell_blocks)
    if world_payloads:
        body += group(b'WRLD', 0, b''.join(world_payloads))
    if args.navi != 'none':
        body += group(b'NAVI', 0, navi_rec)

    # ---- TES4 header
    n_records = len(kept) + len([1 for cf in navm_by_cell]) + len(world_payloads) + (0 if args.navi == 'none' else 1)
    masters = args.masters.split(',')
    hsubs = [sub('HEDR', struct.pack('<fII', 1.0, n_records, (NEW_INDEX << 24) | (ID_BASE + len(kept)))),
             sub('CNAM', b'CapitalConvert\0')]
    for mname in masters:
        hsubs.append(sub('MAST', mname.encode('latin1') + b'\0'))
        hsubs.append(sub('DATA', b'\0' * 8))
    tes4 = record('TES4', 0, hsubs, ver=131)
    open(args.out, 'wb').write(tes4 + body)
    log('wrote %s (%.1f MB)' % (args.out, (len(tes4) + len(body)) / 1048576))
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print('   %7d  %s' % (v, k))
    if args.report:
        with open(args.report, 'w') as f:
            f.write('\n'.join('%d %s' % (v, k) for k, v in stats.items()))
        # id map for debugging / regression tests
        with open(args.report + '.ids', 'w') as f:
            for m in kept:
                f.write('%08X %08X\n' % (m.fid, m.newid))


if __name__ == '__main__':
    main()
