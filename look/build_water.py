"""Rebuild the converted WATR records (zero DNAM, FO3 texture paths) as FO4 waters coloured like the FO3 originals, in place; point the Wasteland world's water at the converted Potomac.
  FO4 WATR DNAM colour words (RGB + 0 alpha): +4 shallow, +8 deep, +36 reflection, +96 / +192 / +196 secondary tints (layout found by diffing vanilla waters).
  FO3 DNAM colours: floats[11] then shallow, deep, reflection (RGBA bytes) at offset 44.
  base = vanilla ExtLakeQuannapowittWater (exterior) / IntPondDarkWater (names that look like interiors); the base's textures, effects and camera values are kept.
  python look/build_water.py"""
import sys, os, struct, shutil
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records, subrecords, sub, record, plugin_header
R = 'X:/__CAPITAL_WORKDIR__/'
FO3D = 'X:/__CAPITAL_FO3_DATA__/'
FO4D = 'X:/__CAPITAL_FO4__/Data/'
PLUGS = ['Fallout3', 'Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta']
INTERIOR = ('interior', 'vault', 'cave', 'metro', 'underground', 'factory', 'utility', 'bathtub', 'fountain', 'dark', 'purity', 'lamplight', 'tunnel', 'cistern')
RAD_NORMAL, RAD_HIGH = 0x24FBF, 0x1FE6A4          # Fallout4.esm SPEL WaterRadiationDrinking / WaterRadiationHighDrinking (master index 0)
REFL_K = float(os.environ.get('REFL_K', '0.7')); DESAT = float(os.environ.get('DESAT', '0.5')); SH_K = float(os.environ.get('SH_K', '0.5')); REFL_SCALE = float(os.environ.get('REFL_SCALE', '1.0'))
def zs(b): return b + bytes(1)
def clamp(v): return max(0, min(255, int(v)))
fo4 = open(FO4D + 'Fallout4.esm', 'rb').read()
base = {}
for r in iter_records(fo4):
    if r.sig == 'WATR':
        d = subrecords(fo4, r); e = dict(d)['EDID'].rstrip(bytes(1)).decode()
        if e in ('ExtLakeQuannapowittWater', 'IntPondDarkWater'): base[e] = d
del fo4

_f3 = open(FO3D + 'Fallout3.esm', 'rb').read()
SPELS = {r.fid & 0xFFFFFF: dict(subrecords(_f3, r)).get('EDID', b'').rstrip(bytes(1)).decode() for r in iter_records(_f3) if r.sig == 'SPEL'}
del _f3
def drink_xnam(sx):
    if not sx or sx in ('WaterHeal1Purified', 'WaterHeal2Good'): return None
    return struct.pack('<I', RAD_HIGH if sx in ('WaterHeal5Terrible', 'WaterHeal1Rads500') else RAD_NORMAL)

def patch_plugin(plug):
    path = R + 'tool/output/%s.esm' % plug
    data = open(path, 'rb').read(); masters, _ = plugin_header(data); own = len(masters)
    src = open(FO3D + plug + '.esm', 'rb').read()
    f3 = {}; f3x = {}
    sp = SPELS
    for r in iter_records(src):
        if r.sig == 'WATR':
            d = dict(subrecords(src, r))
            if 'XNAM' in d and len(d['XNAM']) == 4: d['XNAM_EDID'] = sp.get(struct.unpack('<I', d['XNAM'])[0] & 0xFFFFFF, '')
            if 'DNAM' in d and len(d['DNAM']) >= 56: f3[d['EDID'].rstrip(bytes(1)).decode()] = d
            else: f3x[d['EDID'].rstrip(bytes(1)).decode()] = d
    patches = {}; potomac = None; n = 0
    for r in iter_records(data):
        if r.sig == 'WATR' and (r.fid >> 24) == own:
            conv = subrecords(data, r); cd = dict(conv); e = cd['EDID'].rstrip(bytes(1)).decode()
            if e == 'Potomac': potomac = r.fid
            if e not in f3:
                if e in f3x:                                                      # no usable FO3 DNAM (the drinkable d1..d5 / puddle waters): keep the record, fix only the drinking spell
                    xn = drink_xnam(f3x[e].get('XNAM_EDID', ''))
                    subs = [(k, v) for k, v in conv if k != 'XNAM'] + ([('XNAM', xn)] if xn else [])
                    patches[r.off] = record('WATR', r.fid, [sub(k, v) for k, v in subs], flags=r.flags & ~0x40000, vc=r.vc, ver=r.ver); n += 1
                continue
            d3 = f3[e]['DNAM']; sh, dp, rf = [tuple(d3[o:o + 3]) for o in (44, 48, 52)]
            b = base['IntPondDarkWater' if any(k in e.lower() for k in INTERIOR) else 'ExtLakeQuannapowittWater']
            bd = dict(b); dn = bytearray(bd['DNAM'])
            def put(off, c, k=1.0): dn[off:off + 4] = bytes([clamp(c[0] * k), clamp(c[1] * k), clamp(c[2] * k), 0])
            # FO3 renders its reflection colour far weaker than FO4 does (MegatonBombWater: reflection pure cyan, looked murky olive in FO3): pull it toward the shallow colour and desaturate
            sh = tuple(sh[i] * (1 - SH_K) + dp[i] * SH_K for i in range(3)); lu0 = 0.3 * sh[0] + 0.59 * sh[1] + 0.11 * sh[2]; sh = tuple(sh[i] * (1 - DESAT) + lu0 * DESAT for i in range(3))         # FO3 shallow green renders murky olive: darken toward deep, desaturate
            rf = tuple(rf[i] * (1 - REFL_K) + sh[i] * REFL_K for i in range(3)); lu = 0.3 * rf[0] + 0.59 * rf[1] + 0.11 * rf[2]; rf = tuple(rf[i] * (1 - DESAT) + lu * DESAT for i in range(3))
            put(4, sh); put(8, dp); put(36, rf, REFL_SCALE); put(96, rf, 0.8 * REFL_SCALE); put(192, sh, 1.2); put(196, dp)
            subs = []
            for k, v in b:
                if k == 'EDID': subs.append((k, cd['EDID']))
                elif k == 'DNAM': subs.append((k, bytes(dn)))
                elif k == 'ANAM': subs.append((k, cd.get('ANAM', v)))
                elif k == 'SNAM' and 'SNAM' in cd: subs.append((k, cd['SNAM']))
                elif k == 'SNAM': continue
                elif k == 'XNAM':                                                         # drinking spell: the FO3 SPEL is not converted (dangling id), map its tier to the vanilla FO4 radiation-drinking spells
                    sx = f3[e].get('XNAM_EDID', '')
                    if sx in ('WaterHeal1Purified', 'WaterHeal2Good') or not sx: continue            # clean water: no rads
                    subs.append((k, struct.pack('<I', RAD_HIGH if sx in ('WaterHeal5Terrible', 'WaterHeal1Rads500') else RAD_NORMAL)))
                else: subs.append((k, v))
                if k == 'EDID' and 'FULL' in cd: subs.append(('FULL', cd['FULL']))
            sx = f3[e].get('XNAM_EDID', '')
            if sx and sx not in ('WaterHeal1Purified', 'WaterHeal2Good') and not any(k == 'XNAM' for k, _ in subs):          # the interior base has no drinking spell
                subs.append(('XNAM', struct.pack('<I', RAD_HIGH if sx in ('WaterHeal5Terrible', 'WaterHeal1Rads500') else RAD_NORMAL)))
            patches[r.off] = record('WATR', r.fid, [sub(k, v) for k, v in subs], flags=r.flags & ~0x40000, vc=r.vc, ver=131); n += 1
    nw = 0
    if potomac:
        for r in iter_records(data):
            if r.sig == 'WRLD' and (r.fid >> 24) == own and dict(subrecords(data, r)).get('EDID', b'').rstrip(bytes(1)) == b'Wasteland':
                subs = [(k, struct.pack('<I', potomac) if k in ('NAM2', 'NAM3') else v) for k, v in subrecords(data, r)]
                patches[r.off] = record('WRLD', r.fid, [sub(k, v) for k, v in subs], flags=r.flags & ~0x40000, vc=r.vc, ver=r.ver); nw += 1
    if not patches: print(plug, 'nothing'); return
    hdr_size = 24 + struct.unpack_from('<I', data, 4)[0]
    def walk(p, end):
        out = []
        while p < end:
            sig = data[p:p + 4]; size, = struct.unpack_from('<I', data, p + 4)
            if sig == b'GRUP':
                body = walk(p + 24, p + size)
                out.append(data[p:p + 4] + struct.pack('<I', 24 + len(body)) + data[p + 8:p + 24] + body); p += size
            else: out.append(patches.get(p, data[p:p + 24 + size])); p += 24 + size
        return b''.join(out)
    open(path, 'wb').write(data[:hdr_size] + walk(hdr_size, len(data)))
    print('%-13s waters rebuilt %d, wasteland water set %d' % (plug, n, nw))

for plug in PLUGS:
    bk = R + 'lab/look-backup/%s.esm' % plug
    if not os.path.exists(bk): shutil.copy(R + 'tool/output/%s.esm' % plug, bk)
    patch_plugin(plug)
