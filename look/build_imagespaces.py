"""Per-weather FO4 imagespaces graded like the FO3 image space modifiers (the converter dropped every IMAD, so the FO3 desaturated / amber wasteland grade was lost).
For every weather of a converted plugin: the 8 vanilla imagespaces of FO4's CommonwealthClear are cloned (EDID F3_<weather>_<slot>), their LUT texture removed (it carries FO4's colour grade),
saturation (CNAM[0]) and tint (TNAM = amount, R, G, B) set from the FO3 IMAD of that time of day (sunrise, day, sunset, night; slots 4..7 follow night / day / day-sunset / night).
The clones are inserted into the plugin's IMGS group (idempotent: existing F3_ records are rewritten) and look/imagespace_ids.json maps  plugin -> weather EDID -> 8 FormIDs  for build_weather.py.
  python look/build_imagespaces.py [--only Fallout3]"""
import sys, os, struct, json, collections
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/look')
import fo3imgs
from navlib import iter_records, subrecords, sub, record, group, plugin_header
R = 'X:/__CAPITAL_WORKDIR__/'
FO3D = 'X:/__CAPITAL_FO3_DATA__/'
FO4D = 'X:/__CAPITAL_FO4__/Data/'
PLUGS = ['Fallout3', 'Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta']
VAN = [0x1955D1, 0x216A9C, 0x1955CF, 0x1955D0, 0x1C8576, 0x1955D3, 0x1955D4, 0x1955D5]     # CommonwealthClear IMSP slots
TIMES = [0, 1, 2, 3, 3, 1, 2, 3]            # FO3 time index (sunrise, day, sunset, night) feeding each of the 8 FO4 slots
TINT_K = float(os.environ.get('TINT_K', '0.4'))
def zs(b): return b + bytes(1)

fo4 = open(FO4D + 'Fallout4.esm', 'rb').read()
vanilla = {r.fid: subrecords(fo4, r) for r in iter_records(fo4) if r.sig == 'IMGS' and r.fid in VAN}; del fo4
_fo3 = open(FO3D + 'Fallout3.esm', 'rb').read()
FO3_IMGS = {r.fid: fo3imgs.grade(dict(subrecords(_fo3, r)).get('DNAM', b'')) for r in iter_records(_fo3) if r.sig == 'IMGS'}; del _fo3

def read_imad(src_idx, r):
    """-> (saturation, tint amount, (R, G, B)) of an FO3 IMAD at t=0"""
    s = dict(subrecords(src_idx['data'], r)); sat = 1.0; amt = 0.0; col = (1.0, 1.0, 1.0)
    t = s.get('TNAM')
    if t and len(t) >= 20: _, cr, cg, cb, ca = struct.unpack('<5f', t[:20]); amt, col = ca, (cr, cg, cb)
    q = s.get('QIAD')                           # IAD 17 = cinematic saturation (value at key 0)
    if q and len(q) >= 8: sat = struct.unpack('<2f', q[:8])[1]
    return sat, amt, col

def grade(vsubs, edid, sat, amt, col, bright=None, contrast=None):
    out = []
    for k, v in vsubs:
        if k == 'EDID': out.append((k, zs(edid.encode())))
        elif k.startswith('TX'): continue                           # LUT = FO4 grade
        elif k == 'CNAM':                                            # FO4 cinematic: saturation, brightness, contrast
            vb, vc = struct.unpack('<2f', v[4:12])
            out.append((k, struct.pack('<3f', sat, vb if bright is None else bright, vc if contrast is None else contrast)))
        elif k == 'TNAM': out.append((k, struct.pack('<4f', 1 - (1 - amt) * TINT_K if amt > 0 else amt, *col)))   # FO4's tint amount is far weaker than FO3's: boost toward 1
        else: out.append((k, v))
    return out

def run(plug):
    path = R + 'tool/output/%s.esm' % plug
    data = open(path, 'rb').read(); masters, _ = plugin_header(data); own = len(masters)
    src = open(FO3D + plug + '.esm', 'rb').read()
    imad = {r.fid: r for r in iter_records(src) if r.sig == 'IMAD'}
    idx = {'data': src}
    weathers = []
    for r in iter_records(src):
        if r.sig == 'WTHR':
            subs = subrecords(src, r); iads = [v for k, v in subs if k in ('\x00IAD', '\x01IAD', '\x02IAD', '\x03IAD')]
            weathers.append((dict(subs)['EDID'].rstrip(bytes(1)).decode(), iads, r.fid))
    # FO3 also grades every worldspace with a BASE image space (WRLD INAM: Wasteland = WastelandBaseImageSpace, saturation 0.55, contrast 1.01, brightness 1.08)
    # that the weather modifiers act on.  FO4 has no worldspace image space, so the converter dropped it and the weathers ran at full colour: the base is folded
    # into each weather's grade (saturation multiplies, contrast / brightness from the base, the base tint when the weather has none).
    own_src = 0 if plug == 'Fallout3' else 1
    local = {r.fid: fo3imgs.grade(dict(subrecords(src, r)).get('DNAM', b'')) for r in iter_records(src) if r.sig == 'IMGS'}
    def base_imgs(fid): return (FO3_IMGS.get(fid & 0xFFFFFF) if (fid >> 24) == 0 else local.get(fid)) if own_src else FO3_IMGS.get(fid)
    climates = {}; worlds = []; regions = []
    for r in iter_records(src):
        if r.sig == 'CLMT':
            wl = dict(subrecords(src, r)).get('WLST', b''); climates[r.fid] = [struct.unpack_from('<I', wl, i)[0] for i in range(0, len(wl) - 11, 12)]
        elif r.sig == 'WRLD':
            s2 = dict(subrecords(src, r))
            if 'INAM' in s2: worlds.append((r.fid, struct.unpack('<I', s2['CNAM'])[0] if 'CNAM' in s2 else 0, struct.unpack('<I', s2['INAM'])[0]))
        elif r.sig == 'REGN':
            s2 = list(subrecords(src, r)); d2 = dict(s2)
            if 'WNAM' in d2:
                for k, v in s2:
                    if k == 'RDWT': regions.append((struct.unpack('<I', d2['WNAM'])[0], [struct.unpack_from('<I', v, i)[0] for i in range(0, len(v) - 11, 12)]))
    world_base = {wf: inam for wf, _, inam in worlds}
    votes = collections.defaultdict(collections.Counter)
    for wf, clim, inam in worlds:
        for w in climates.get(clim, []): votes[w][inam] += 1
    for wf, wl in regions:
        if wf in world_base:
            for w in wl: votes[w][world_base[wf]] += 1
    base_of = {w: base_imgs(c.most_common(1)[0][0]) for w, c in votes.items()}
    existing = {}
    for r in iter_records(data):
        if r.sig == 'IMGS' and (r.fid >> 24) == own:
            e = dict(subrecords(data, r)).get('EDID', b'').rstrip(bytes(1)).decode()
            if e.startswith('F3_'): existing[e] = r
    nxt = max((r.fid & 0xFFFFFF) for r in iter_records(data) if (r.fid >> 24) == own) + 1
    new_recs = []; patches = {}; ids = {}
    nbase = 0
    for wname, iads, wfid in weathers:
        base = base_of.get(wfid); nbase += base is not None
        grades = []
        for ref in iads[:4]:
            fid = struct.unpack('<I', ref)[0]; rec = imad.get(fid)
            grades.append(read_imad(idx, rec) if rec else (1.0, 0.0, (1.0, 1.0, 1.0)))
        while len(grades) < 4: grades.append((1.0, 0.0, (1.0, 1.0, 1.0)))
        row = []
        for slot in range(8):
            edid = 'F3_%s_%d' % (wname, slot); sat, amt, col = grades[TIMES[slot]]
            bright = contrast = None
            if base:
                sat = sat * base['sat']; bright, contrast = base['bright'], base['contrast']
                if amt <= 0.0 and base['tint_amt'] > 0.0: amt, col = base['tint_amt'], base['tint']
            body = [sub(k, v) for k, v in grade(vanilla[VAN[slot]], edid, sat, amt, col, bright, contrast)]
            if edid in existing:
                r = existing[edid]; patches[r.off] = record('IMGS', r.fid, body, ver=131); row.append(r.fid)
            else:
                fid = (own << 24) | nxt; nxt += 1; new_recs.append(record('IMGS', fid, body, ver=131)); row.append(fid)
        ids[wname] = row
    # write: patch existing + append new records to the IMGS top group
    hdr_size = 24 + struct.unpack_from('<I', data, 4)[0]
    p = hdr_size; out = [data[:hdr_size]]; done = False
    while p < len(data):
        sig = data[p:p + 4]; size, = struct.unpack_from('<I', data, p + 4)
        if sig == b'GRUP' and data[p + 8:p + 12] == b'IMGS' and struct.unpack_from('<I', data, p + 12)[0] == 0:
            body = bytearray()
            q = p + 24
            while q < p + size:
                s2, z2 = data[q:q + 4], struct.unpack_from('<I', data, q + 4)[0]
                body += patches.get(q, data[q:q + 24 + z2]); q += 24 + z2
            body += b''.join(new_recs)
            out.append(data[p:p + 4] + struct.pack('<I', 24 + len(body)) + data[p + 8:p + 24] + bytes(body)); done = True
        else: out.append(data[p:p + size] if sig == b'GRUP' else data[p:p + 24 + size])
        p += size if sig == b'GRUP' else 24 + size
    assert done or not new_recs, 'no IMGS group in ' + plug
    res = b''.join(out)
    if new_recs:
        hl = struct.unpack_from('<I', res, 4)[0]; hdr = bytearray(res[:24 + hl]); q = 24
        while q < len(hdr):
            sg = bytes(hdr[q:q + 4]); sz = struct.unpack_from('<H', hdr, q + 4)[0]
            if sg == b'HEDR':
                cnt, nid = struct.unpack_from('<II', hdr, q + 10); struct.pack_into('<II', hdr, q + 10, cnt + len(new_recs), max(nid, nxt))
            q += 6 + sz
        res = bytes(hdr) + res[24 + hl:]
    open(path, 'wb').write(res)
    print('%-13s weathers %d (%d with a worldspace base grade)  imagespaces new %d rewritten %d' % (plug, len(weathers), nbase, len(new_recs), len(patches)))
    return ids

if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    allids = {}
    for plug in PLUGS:
        if only and plug != only: continue
        ids = run(plug); allids[plug] = ids
    jp = R + 'look/imagespace_ids.json'
    old = json.load(open(jp)) if os.path.exists(jp) else {}
    old.update(allids); json.dump(old, open(jp, 'w'))
