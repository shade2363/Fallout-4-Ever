"""Rebuild every converted WTHR (the converter writes empty shells: all colours 0, Skyrim-size NAM0) as a real FO4 weather from the FO3 original, in place, and give the worlds their FO3 climates.
  * template  = vanilla FO4 CommonwealthClear (layout of NAM0 19x8x4, PNAM/JNAM 32 layers x 8 times, FNAM 18 floats, DATA 20, 8 DALC, 8 IMSP)
  * FO3 NAM0 (10 types x 4 times RGBA), FNAM (6 floats), DATA (15), PNAM (4 layers x 4 times), cloud layer textures DNAM/CNAM/ANAM/BNAM, cloud speeds ONAM  ->  FO4 fields
  * the 4 FO3 times (sunrise, day, sunset, night) are spread over FO4's 8 (see EXPAND); DALC (directional ambient) is derived from the FO3 ambient colour
  * IMSP (imagespaces per time) = the graded clones of look/build_imagespaces.py when look/imagespace_ids.json exists, else vanilla CommonwealthClear's
  * WRLD CNAM = the FO3 climate of the world (the converter pointed every world except Wasteland at FO4's 0x15F)
  python look/build_weather.py [--only Fallout3]   (idempotent; plugin paths tool/output/<plug>.esm, FO3 sources in the FO3 Data folder)"""
import sys, os, struct, json, shutil, collections
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records, subrecords, sub, record, plugin_header
R = 'X:/__CAPITAL_WORKDIR__/'
FO3D = 'X:/__CAPITAL_FO3_DATA__/'
FO4D = 'X:/__CAPITAL_FO4__/Data/'
PLUGS = ['Fallout3', 'Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta']
BS = chr(92)
TEX_PREFIX = 'New_Vegas' + BS            # the converter moved every FO3 texture under textures\New_Vegas
def zs(b): return b + bytes(1)
def clamp(v): return max(0, min(255, int(round(v))))

# ---- template: vanilla CommonwealthClear
fo4 = open(FO4D + 'Fallout4.esm', 'rb').read()
TPL = None
for r in iter_records(fo4):
    if r.sig == 'WTHR' and r.fid == 0x2B52A: TPL = (dict(subrecords(fo4, r)), r)
T, TR = TPL; del fo4
IMS_ALL = json.load(open(R + 'look/imagespace_ids.json')) if os.path.exists(R + 'look/imagespace_ids.json') else {}
CUR = ['']

def mix(a, b, t): return tuple(a[i] * (1 - t) + b[i] * t for i in range(len(a)))
def expand(v4):
    """FO3 (sunrise, day, sunset, night) -> FO4's 8 time slots.  Slots 0-3 are sunrise/day/sunset/night; 4 and 7 are dark night variants, 5/6 the bright
    morning / afternoon variants (vanilla: stars lit in 4 and 7, warm sunlight in 5 and 6)."""
    S, D, Su, N = v4
    return [S, D, Su, N, N, mix(S, D, 0.5), mix(D, Su, 0.5), N]

def fo3_weather(rec_subs):
    s = collections.defaultdict(list)
    for k, v in rec_subs: s[k].append(v)
    return s

def build(conv_subs, src):
    """conv_subs = subrecords of the converted record, src = FO3 subrecord dict (lists)"""
    nam0 = src['NAM0'][0]
    f3 = [[tuple(nam0[(t * 4 + k) * 4:(t * 4 + k) * 4 + 3]) for k in range(4)] for t in range(10)]       # [type][time] = RGB
    out = []
    edid = dict(conv_subs)['EDID']
    out.append(('EDID', edid))
    # cloud layers
    layers = []
    for i, key in enumerate(('DNAM', 'CNAM', 'ANAM', 'BNAM')):
        p = src[key][0].rstrip(bytes(1)).decode('latin1') if src.get(key) else ''
        if not p or p.lower().endswith('alpha.dds'): continue
        layers.append((i, TEX_PREFIX + p))
    k = len(layers)
    for n, (i, p) in enumerate(layers): out.append((chr(0x30 + n) + '0TX', zs(p.encode('latin1'))))
    out += [('LNAM', struct.pack('<I', max(k, 1))), ('MNAM', bytes(4)), ('NNAM', bytes(4))]
    onam = src['ONAM'][0] if src.get('ONAM') else bytes(4)
    rnam = bytearray(b'\x7f' * 32); qnam = bytearray(b'\x7f' * 32)
    for n, (i, p) in enumerate(layers): qnam[n] = 0x7f + min(onam[i] >> 2, 60) if i < len(onam) else 0x7f
    out += [('RNAM', bytes(rnam)), ('QNAM', bytes(qnam))]
    pnam_src = src['PNAM'][0] if src.get('PNAM') else bytes(64)
    pn = bytearray(1024); jn = bytearray(1024)
    for n, (i, p) in enumerate(layers):
        cols = [tuple(pnam_src[(i * 4 + t) * 4:(i * 4 + t) * 4 + 3]) for t in range(4)]
        for t, c in enumerate(expand(cols)):
            o = (n * 8 + t) * 4; pn[o:o + 4] = bytes([clamp(c[0]), clamp(c[1]), clamp(c[2]), 0]); struct.pack_into('<f', jn, o, 1.0)
    for n in range(k, 32):
        for t in range(8): struct.pack_into('<f', jn, (n * 8 + t) * 4, 1.0)
    out += [('PNAM', bytes(pn)), ('JNAM', bytes(jn))]
    # sky colours
    tn = bytearray(608)
    def put(t4, vals8, scale=1.0):
        for t in range(8): tn[(t4 * 8 + t) * 4:(t4 * 8 + t) * 4 + 4] = bytes([clamp(vals8[t][0] * scale), clamp(vals8[t][1] * scale), clamp(vals8[t][2] * scale), 0])
    tpl_n = T['NAM0']
    def tpl_type(t4): return [tuple(tpl_n[(t4 * 8 + t) * 4:(t4 * 8 + t) * 4 + 3]) for t in range(8)]
    E = {t: expand(f3[t]) for t in range(10)}
    put(0, E[0]); put(1, E[1]); put(3, E[3]); put(4, E[4]); put(5, E[5]); put(6, E[6]); put(7, E[7]); put(8, E[8])
    put(9, E[3], 1.25); put(12, E[1], 1.0); put(13, E[8], 1.0); put(14, tpl_type(14)); put(15, E[5]); put(16, tpl_type(16))
    put(17, E[0], 0.6); put(18, E[7], 1.0)
    out.append(('NAM0', bytes(tn)))
    out.append(('NAM4', T['NAM4']))
    # fog
    fn = src['FNAM'][0]; fv = list(struct.unpack('<18f', T['FNAM']))
    dn, df, nn, nf, dp, np_ = struct.unpack('<6f', fn[:24])
    fv[0:6] = [dn, df, nn, nf, dp, np_]
    out.append(('FNAM', struct.pack('<18f', *fv)))
    d3 = src['DATA'][0]; data = bytearray(T['DATA']); data[0] = d3[0]; data[1] = 0; data[2] = 0
    data[3:15] = d3[3:15]
    out.append(('DATA', bytes(data)))
    en = 0xFFFFFFFF & ~((1 << k) - 1)
    out.append(('NAM1', struct.pack('<I', en)))
    snam = dict(conv_subs).get('SNAM') or T['SNAM']
    out.append(('SNAM', snam))
    IMS = IMS_ALL.get(CUR[0], {})
    if edid.rstrip(bytes(1)).decode() in IMS: out.append(('IMSP', struct.pack('<8I', *IMS[edid.rstrip(bytes(1)).decode()])))
    else: out.append(('IMSP', T['IMSP']))
    out.append(('WGDR', T['WGDR']))
    # directional ambient: FO3 ambient colour per time
    amb = E[3]; sky = E[7]
    for t in range(8):
        a = amb[t]; sk = sky[t]
        top = tuple(a[i] * 1.1 + sk[i] * 0.25 for i in range(3)); side = tuple(a[i] * 0.9 + sk[i] * 0.1 for i in range(3)); bot = tuple(a[i] * 0.5 for i in range(3))
        cols = [side, side, side, side, top, bot]
        b = b''.join(bytes([clamp(c[0]), clamp(c[1]), clamp(c[2]), 0]) for c in cols) + bytes(4) + struct.pack('<f', 1.0)
        out.append(('DALC', b))
    for kk in ('GNAM', 'UNAM', 'VNAM', 'WNAM'): out.append((kk, T[kk]))
    return out

def patch_plugin(plug):
    CUR[0] = plug
    path = R + 'tool/output/%s.esm' % plug
    data = open(path, 'rb').read()
    masters, _ = plugin_header(data); own = len(masters)
    src = open(FO3D + plug + '.esm', 'rb').read()
    src_w = {}; src_climate = {}; src_wrld = {}
    for r in iter_records(src):
        if r.sig == 'WTHR':
            s = fo3_weather(subrecords(src, r)); src_w[s['EDID'][0].rstrip(bytes(1)).decode()] = s
        elif r.sig == 'WRLD':
            c = dict(subrecords(src, r)).get('CNAM')
            if c and len(c) == 4: src_wrld[r.fid & 0xFFFFFF] = struct.unpack('<I', c)[0]
    src_masters, _ = plugin_header(src)
    climates = {r.fid & 0xFFFFFF for r in iter_records(data) if r.sig == 'CLMT' and (r.fid >> 24) == own}
    patches = {}; nw = nwr = 0
    for r in iter_records(data):
        if r.sig == 'WTHR' and (r.fid >> 24) == own:
            conv = subrecords(data, r); e = dict(conv)['EDID'].rstrip(bytes(1)).decode()
            if e not in src_w or 'NAM0' not in src_w[e]: print('  no FO3 source for', e); continue
            subs = build(conv, src_w[e])
            patches[r.off] = record('WTHR', r.fid, [sub(k, v) for k, v in subs], flags=r.flags & ~0x40000, vc=r.vc, ver=131); nw += 1
        elif r.sig == 'WRLD' and (r.fid >> 24) == own:
            want = src_wrld.get(r.fid & 0xFFFFFF)
            if want is None: continue
            if (want >> 24) == len(src_masters) - 0 or True:
                low = want & 0xFFFFFF
                if plug == 'Fallout3' or (want >> 24) >= len(src_masters):
                    if low in climates: new = (own << 24) | low
                    else: continue
                else: continue
            subs = subrecords(data, r)
            if any(k == 'CNAM' and struct.unpack('<I', v)[0] == new for k, v in subs): continue
            subs = [(k, struct.pack('<I', new) if k == 'CNAM' else v) for k, v in subs]
            patches[r.off] = record('WRLD', r.fid, [sub(k, v) for k, v in subs], flags=r.flags & ~0x40000, vc=r.vc, ver=r.ver); nwr += 1
    if not patches: print(plug, 'nothing to patch'); return
    hdr_size = 24 + struct.unpack_from('<I', data, 4)[0]
    def walk(p, end):
        out = []
        while p < end:
            sig = data[p:p + 4]; size, = struct.unpack_from('<I', data, p + 4)
            if sig == b'GRUP':
                body = walk(p + 24, p + size)
                out.append(data[p:p + 4] + struct.pack('<I', 24 + len(body)) + data[p + 8:p + 24] + body); p += size
            else:
                out.append(patches.get(p, data[p:p + 24 + size])); p += 24 + size
        return b''.join(out)
    open(path, 'wb').write(data[:hdr_size] + walk(hdr_size, len(data)))
    print('%-13s weathers rebuilt %d, world climates set %d' % (plug, nw, nwr))

if __name__ == '__main__':
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    os.makedirs(R + 'lab/look-backup', exist_ok=True)
    for plug in PLUGS:
        if only and plug != only: continue
        bk = R + 'lab/look-backup/%s.esm' % plug
        if not os.path.exists(bk): shutil.copy(R + 'tool/output/%s.esm' % plug, bk)
        patch_plugin(plug)
