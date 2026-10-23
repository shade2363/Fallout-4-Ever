"""Terminal models = Fallout 3 look + Fallout 4 interaction.

Fallout 4 only runs the terminal UI (camera zoom, menu text) for a model with the vanilla structure: the 'c_screen' node, the 'Screen:0' shape (material
PipScreenTerminals.BGSM), the two Havok bodies and BSX 523 of Furniture/Terminals/TerminalOnCorded.nif (verified in game 2026-10-06: that nif cut down to c_screen +
Screen:0 + ScreenType shapes still opens the UI).  Adding those pieces to the Fallout 3 nif did NOT work, so this builds the model the other way round: the vanilla nif
without its visible body, plus the Fallout 3 shapes imported under a node 'FO3Visual' that rotates the +X-facing Fallout 3 screen to the vanilla -Y and moves its front
face onto the vanilla screen.  The placed references are then turned by -90 degrees and moved by -R*t (fix_terminal_refs.py reads terminal_models.json written here).

  python add_terminal_hybrid.py     -> tool/output/loose/meshes/new_vegas/<model>.nif + worldfix/terminal_models.json"""
import sys, os, struct, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_door_anim import Nif, node_fields, node_bytes
from ba2_extract import open_ba2, zlib
OUT = r'X:\__CAPITAL_WORKDIR__\tool\output'
D4 = r'X:\__CAPITAL_FO4__\Data'
MODELS = {   # converted mesh path (inside the BA2) -> shape that is the monitor's glass (front face = the face towards +X)
    'meshes/new_vegas/terminals/terminal01.nif': 'T01Screen01:1',
    'meshes/new_vegas/terminals/terminal02.nif': 'T01Screen02:1',
    'meshes/new_vegas/terminals/terminaldesk01.nif': 'TerminalDesk01base:1',
    'meshes/new_vegas/dungeons/vaultruined/clutter/terminaldeskr01.nif': 'TerminalDeskR01:1',
    'meshes/new_vegas/dungeons/vault/accessories/voverseerterminal01.nif': 'VMonitorBank:0',
}
M = (0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0)         # +X -> -Y (v' = M v)


def mat_mul(a, b): return tuple(sum(a[3 * r + k] * b[3 * k + c] for k in range(3)) for r in range(3) for c in range(3))
def mat_vec(a, v): return tuple(sum(a[3 * r + k] * v[k] for k in range(3)) for r in range(3))


def xf_read(d):
    ne = struct.unpack_from('<I', d, 4)[0]; q = 8 + 4 * ne + 8
    return struct.unpack_from('<3f', d, q), struct.unpack_from('<9f', d, q + 12), struct.unpack_from('<f', d, q + 48)[0]


def xf_compose(p, c):                                           # p, c = (t, R, s); child inside parent
    rt = mat_vec(p[1], c[0]); t = tuple(p[0][i] + p[2] * rt[i] for i in range(3)); return t, mat_mul(p[1], c[1]), p[2] * c[2]


def shape_ref_offset(d):
    ne = struct.unpack_from('<I', d, 4)[0]; return 8 + 4 * ne + 8 + 52 + 4 + 16 + 4


def shape_positions(d):
    o = shape_ref_offset(d) + 8
    desc, = struct.unpack_from('<Q', d, o); ntri, nv, dsz = struct.unpack_from('<IHI', d, o + 8)
    vsize = (desc & 0xF) * 4; full = ((desc >> 8) & 0xF) * 4 >= 16; base = o + 8 + 10
    return [struct.unpack_from('<3f' if full else '<3e', d, base + i * vsize) for i in range(nv)]


class Tree:
    """world transforms of every node / shape of a nif"""
    def __init__(self, n):
        self.n = n; self.world = {}
        ident = ((0.0, 0.0, 0.0), (1, 0, 0, 0, 1, 0, 0, 0, 1), 1.0)

        def walk(i, pw):
            t, d = n.blocks[i]
            w = xf_compose(pw, xf_read(d)); self.world[i] = w
            if t in ('NiNode', 'BSFadeNode'):
                for k in node_fields(d)['kids']:
                    if k >= 0: walk(k, w)
        walk(0, ident)


def name_of(n, d):
    i = struct.unpack_from('<i', d, 0)[0]; return n.strs[i] if 0 <= i < len(n.strs) else ''


def import_block(src, dst, i, cache):
    """copy block i of src (node / shape / shader prop / texture set / alpha) into dst without controllers, extra data or collision; returns the dst index"""
    if i < 0: return -1
    if i in cache: return cache[i]
    t, d = src.blocks[i]; d = bytearray(d)

    def S(idx): return dst.sid(src.strs[idx]) if 0 <= idx < len(src.strs) else -1
    if t in ('NiNode', 'BSFadeNode'):
        f = node_fields(bytes(d))
        kids = [import_block(src, dst, k, cache) for k in f['kids'] if k >= 0 and src.blocks[k][0] in ('NiNode', 'BSFadeNode', 'BSTriShape')]
        f.update(name=S(f['name']), extras=[], ctrl=-1, coll=-1, kids=[k for k in kids if k >= 0], tail=b'')
        r = dst.add('NiNode', node_bytes(f))
    elif t == 'BSTriShape':
        ne = struct.unpack_from('<I', d, 4)[0]; q = 8 + 4 * ne
        ctrl, flags = struct.unpack_from('<iI', d, q); xf = bytes(d[q + 8:q + 8 + 52]); after = q + 8 + 52 + 4        # after the collision ref
        rest = bytearray(d[after:]); skin, sh, al = struct.unpack_from('<3i', rest, 16)
        struct.pack_into('<3i', rest, 16, -1, import_block(src, dst, sh, cache), import_block(src, dst, al, cache))
        r = dst.add('BSTriShape', struct.pack('<iIiI', S(struct.unpack_from('<i', d, 0)[0]), 0, -1, flags) + xf + struct.pack('<i', -1) + bytes(rest))
    elif t == 'BSLightingShaderProperty':
        ts = next((x for x in range(0, len(d) - 3) if 0 <= struct.unpack_from('<i', d, x)[0] < len(src.blocks)
                   and src.blocks[struct.unpack_from('<i', d, x)[0]][0] == 'BSShaderTextureSet'), None)
        assert struct.unpack_from('<I', d, 8)[0] == 0
        struct.pack_into('<i', d, 4, S(struct.unpack_from('<i', d, 4)[0])); struct.pack_into('<i', d, 12, -1)
        if ts is not None: struct.pack_into('<i', d, ts, import_block(src, dst, struct.unpack_from('<i', d, ts)[0], cache))
        r = dst.add(t, bytes(d))
    elif t == 'BSEffectShaderProperty':
        assert struct.unpack_from('<I', d, 4)[0] == 0
        struct.pack_into('<i', d, 0, S(struct.unpack_from('<i', d, 0)[0])); struct.pack_into('<i', d, 8, -1); r = dst.add(t, bytes(d))
    elif t == 'NiAlphaProperty':
        assert struct.unpack_from('<I', d, 4)[0] == 0
        struct.pack_into('<i', d, 0, S(struct.unpack_from('<i', d, 0)[0])); struct.pack_into('<i', d, 8, -1); r = dst.add(t, bytes(d))
    elif t == 'BSShaderTextureSet':
        r = dst.add(t, bytes(d))
    else:
        return -1
    cache[i] = r; return r


def build(fo3_bytes, van_bytes, screen_shape):
    F = Nif(fo3_bytes); V = Nif(van_bytes); tf = Tree(F)
    si = next(i for i, (t, d) in enumerate(F.blocks) if t == 'BSTriShape' and name_of(F, d) == screen_shape)
    w = tf.world[si]; pos = [mat_vec(w[1], v) for v in shape_positions(F.blocks[si][1])]
    pos = [tuple(w[0][k] + w[2] * p[k] for k in range(3)) for p in pos]                       # screen vertices in the FO3 root frame
    ys = [p[1] for p in pos]; zs = [p[2] for p in pos]
    cf = (max(p[0] for p in pos), (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)           # front-face centre (front = +X)
    vs = next(i for i, (t, d) in enumerate(V.blocks) if t == 'BSTriShape' and name_of(V, d) == 'Screen:0')
    tv = Tree(V); vw = tv.world[vs]; vp = [mat_vec(vw[1], v) for v in shape_positions(V.blocks[vs][1])]
    vp = [tuple(vw[0][k] + vw[2] * p[k] for k in range(3)) for p in vp]
    cv = ((min(p[0] for p in vp) + max(p[0] for p in vp)) / 2, min(p[1] for p in vp), (min(p[2] for p in vp) + max(p[2] for p in vp)) / 2)   # vanilla screen plane centre
    mc = mat_vec(M, cf); t = (cv[0] - mc[0], cv[1] + 0.6 - mc[1], cv[2] - mc[2])               # FO3 glass 0.6 behind the vanilla UI plane

    def setkids(i, kids):
        f = node_fields(V.blocks[i][1]); f['kids'] = kids; V.blocks[i][1] = node_bytes(f)
    by = {}
    for i, (tt, d) in enumerate(V.blocks):
        if tt in ('NiNode', 'BSTriShape'): by.setdefault(name_of(V, d), []).append(i)
    ordered = by['OrderedRenderingNode'][0]; body = by['TerminalCorded'][0]; csc = by['c_screen'][0]
    # keep c_screen, Screen:0 and the ScreenType overlays; drop the visible body (button, bodies, vent FX)
    setkids(body, [k for k in node_fields(V.blocks[body][1])['kids'] if k == csc])
    setkids(ordered, [k for k in node_fields(V.blocks[ordered][1])['kids'] if k in (body, vs)])
    cache = {}
    kids = [import_block(F, V, k, cache) for k in node_fields(F.blocks[0][1])['kids'] if k >= 0 and F.blocks[k][0] in ('NiNode', 'BSFadeNode', 'BSTriShape')]
    tr = struct.pack('<3f', *t) + struct.pack('<9f', *M) + struct.pack('<f', 1.0)
    vis = V.add('NiNode', node_bytes(dict(name=V.sid('FO3Visual'), extras=[], ctrl=-1, flags=0xe, transform=tr, coll=-1, kids=[k for k in kids if k >= 0], tail=b'')))
    root = node_fields(V.blocks[0][1]); root['kids'] = root['kids'] + [vis]; V.blocks[0][1] = node_bytes(root)
    return V.tobytes(), t, cf, cv


if __name__ == '__main__':
    f, names, recs = open_ba2(os.path.join(OUT, 'Fallout3 - Main.ba2')); idx = {x.lower().replace(chr(92), '/'): r for x, r in zip(names, recs)}

    def read(fh, ix, p):
        off, psz, usz = ix[p]; fh.seek(off); d = fh.read(psz or usz); return zlib.decompress(d) if psz else d
    g, gn, gr = open_ba2(os.path.join(D4, 'Fallout4 - Meshes.ba2')); gi = {x.lower().replace(chr(92), '/'): r for x, r in zip(gn, gr)}
    van = read(g, gi, 'meshes/furniture/terminals/terminaloncorded.nif')
    info = {}
    for p, shape in MODELS.items():
        new, t, cf, cv = build(read(f, idx, p), van, shape)
        dst = os.path.join(OUT, 'loose', *p.split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True); open(dst, 'wb').write(new)
        info[p[len('meshes/new_vegas/'):]] = dict(t=list(t))
        print('built', p, len(new), 't=', [round(x, 1) for x in t], 'fo3 front centre', [round(x, 1) for x in cf], 'vanilla screen', [round(x, 1) for x in cv])
    json.dump(info, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'terminal_models.json'), 'w'), indent=1)
