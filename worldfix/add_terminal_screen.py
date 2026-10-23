"""Give a converted Fallout 3 terminal model the Fallout 4 terminal SCREEN.

Fallout 4 draws the terminal UI (menu text) on the geometry whose material is Materials/Interface\PipScreenTerminals.BGSM (vanilla shape 'Screen:0' in
Furniture/Terminals\TerminalOnCorded.nif: a BSLightingShaderProperty + BSShaderTextureSet using textures\AnimObjects\PipBoy\PipBoyScreen_d.dds).  The Fallout 3
terminal meshes have no such shape, so the terminal opens (camera + 'Tab) EXIT') but shows no text.  This copies that shader property + texture set from the
vanilla nif into the model and points the model's monitor shape at them.

  python add_terminal_screen.py                      (patches the models below from Fallout3 - Main.ba2 into tool/output/loose/meshes)
Library: patch(nif_bytes, shape_name, vanilla_nif_bytes) -> new bytes"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from add_door_anim import Nif
from ba2_extract import open_ba2, zlib

def shape_ref_offset(d):
    ne = struct.unpack_from('<I', d, 4)[0]; p = 8 + 4 * ne + 8 + 52 + 4 + 16     # name, extras, controller+flags, transform, collision, bounding sphere
    return p + 4                                                                  # skin ref, then shader ref (p+4), alpha ref (p+8)

def patch(b, shape_name, van, clone=False):
    n = Nif(b); v = Nif(van)
    wrap = True
    vi = next(i for i, (t, d) in enumerate(v.blocks) if t == 'BSTriShape' and v.strs[struct.unpack_from('<i', d, 0)[0]] == 'Screen:0')
    vshader = struct.unpack_from('<i', v.blocks[vi][1], shape_ref_offset(v.blocks[vi][1]))[0]
    assert v.blocks[vshader][0] == 'BSLightingShaderProperty'
    sd = bytearray(v.blocks[vshader][1]); vts = None
    for off in range(0, len(sd) - 3):
        x = struct.unpack_from('<i', sd, off)[0]
        if 0 <= x < len(v.blocks) and v.blocks[x][0] == 'BSShaderTextureSet': vts = (off, x); break
    assert vts, 'texture set ref not found'
    tgt = None
    for i, (t, d) in enumerate(n.blocks):
        if t == 'BSTriShape' and n.strs[struct.unpack_from('<i', d, 0)[0]] == shape_name: tgt = i
    if tgt is None: return b, False
    ts_new = n.add('BSShaderTextureSet', v.blocks[vts[1]][1])
    struct.pack_into('<i', sd, 4, n.sid(v.strs[struct.unpack_from('<i', sd, 4)[0]]))     # name = material path in this nif's string table
    struct.pack_into('<i', sd, vts[0], ts_new)
    sh_new = n.add('BSLightingShaderProperty', bytes(sd))
    d = bytearray(n.blocks[tgt][1]); o = shape_ref_offset(d)
    struct.pack_into('<i', d, o, sh_new); struct.pack_into('<i', d, o + 4, -1)             # shader = screen, no alpha property
    if not clone:
        n.blocks[tgt][1] = bytes(d)
        add_c_screen(n, shape_name); wrap_face(n)
        return n.tobytes(), True
    # clone: the target is an effect shape that an animation controller targets (swapping its shader type crashes the load), so add a copy as a new child
    struct.pack_into('<i', d, 0, n.sid('Screen:0'))
    new_i = n.add('BSTriShape', bytes(d))
    for i, (t, dd) in enumerate(n.blocks):
        if t in ('NiNode', 'BSFadeNode') and i != new_i:
            from add_door_anim import node_fields, node_bytes
            f = node_fields(dd)
            if tgt in f['kids']:
                f['kids'].append(new_i); n.blocks[i][1] = node_bytes(f); break
    else: raise SystemExit('no parent node for ' + shape_name)
    add_c_screen(n, shape_name); wrap_face(n)
    return n.tobytes(), True


def _shape_geometry(d):
    """-> (positions [(x,y,z)], mean normal) of a BSTriShape block (half or full precision positions, v130)."""
    o = shape_ref_offset(d) + 8
    desc, = struct.unpack_from('<Q', d, o); ntri, nv, dsz = struct.unpack_from('<IHI', d, o + 8)
    vsize = (desc & 0xF) * 4; uv_off = ((desc >> 8) & 0xF) * 4; nrm_off = ((desc >> 16) & 0xF) * 4
    base = o + 8 + 10; pos = []; nsum = [0.0, 0.0, 0.0]
    full = uv_off >= 16
    for i in range(nv):
        v = base + i * vsize
        x, y, z = struct.unpack_from('<3f', d, v) if full else struct.unpack_from('<3e', d, v)
        pos.append((x, y, z))
        nb = d[v + nrm_off: v + nrm_off + 3]
        for k in range(3): nsum[k] += nb[k] / 255.0 * 2.0 - 1.0
    ln = (sum(c * c for c in nsum) ** 0.5) or 1.0
    return pos, [c / ln for c in nsum]

def add_c_screen(n, shape_name):
    """Add the 'c_screen' camera node (vanilla terminals have one at the screen centre, local -Y = out of the screen) next to the screen shape."""
    from add_door_anim import node_fields, node_bytes, IDENT
    tgt = next(i for i, (t, d) in enumerate(n.blocks) if t == 'BSTriShape' and n.strs[struct.unpack_from('<i', d, 0)[0]] == shape_name)
    pos, nrm = _shape_geometry(n.blocks[tgt][1])
    c = [(min(p[k] for p in pos) + max(p[k] for p in pos)) / 2 for k in range(3)]
    d = n.blocks[tgt][1]; ne = struct.unpack_from('<I', d, 4)[0]; q = 8 + 4 * ne + 8
    st = struct.unpack_from('<3f', d, q); sr = struct.unpack_from('<9f', d, q + 12)       # shape transform (row-major rotation)
    cp = [st[r] + sr[3 * r] * c[0] + sr[3 * r + 1] * c[1] + sr[3 * r + 2] * c[2] for r in range(3)]
    nw = [sr[3 * r] * nrm[0] + sr[3 * r + 1] * nrm[1] + sr[3 * r + 2] * nrm[2] for r in range(3)]
    ylocal = [-nw[0], -nw[1], -nw[2]]
    up = (0.0, 0.0, 1.0)
    xl = [ylocal[1] * up[2] - ylocal[2] * up[1], ylocal[2] * up[0] - ylocal[0] * up[2], ylocal[0] * up[1] - ylocal[1] * up[0]]
    lx = sum(v * v for v in xl) ** 0.5
    xl = [v / lx for v in xl] if lx > 1e-4 else [1.0, 0.0, 0.0]
    zl = [xl[1] * ylocal[2] - xl[2] * ylocal[1], xl[2] * ylocal[0] - xl[0] * ylocal[2], xl[0] * ylocal[1] - xl[1] * ylocal[0]]
    rot = (xl[0], ylocal[0], zl[0], xl[1], ylocal[1], zl[1], xl[2], ylocal[2], zl[2])      # columns = local axes
    tr = struct.pack('<3f', *cp) + struct.pack('<9f', *rot) + struct.pack('<f', 1.0)
    node = dict(name=n.sid('c_screen'), extras=[], ctrl=-1, flags=0x8e, transform=tr, coll=-1, kids=[], tail=b'')
    ni = n.add('NiNode', node_bytes(node))
    for i, (t, dd) in enumerate(n.blocks):
        if t in ('NiNode', 'BSFadeNode') and i != ni:
            f = node_fields(dd)
            if tgt in f['kids']:
                f['kids'].append(ni); n.blocks[i][1] = node_bytes(f); return True
    return False

def wrap_face(n):
    """Fallout 3 terminal screens face +X, Fallout 4's furniture entry expects them to face -Y (vanilla 'c_screen' / marker offset (0,-61,0)).  Move the root's children and
    collision under a node rotated so that +X -> -Y; the references of these terminals must then be turned by the opposite angle (see fix_terminal_refs.py)."""
    from add_door_anim import node_fields, node_bytes
    root = node_fields(n.blocks[0][1])
    rot = (0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    tr = struct.pack('<3f', 0, 0, 0) + struct.pack('<9f', *rot) + struct.pack('<f', 1.0)
    leaf = dict(name=n.sid('FO3Face'), extras=[], ctrl=-1, flags=0x8e, transform=tr, coll=root['coll'], kids=root['kids'], tail=b'')
    li = n.add('NiNode', node_bytes(leaf))
    if root['coll'] >= 0:
        cb = bytearray(n.blocks[root['coll']][1]); struct.pack_into('<i', cb, 0, li); n.blocks[root['coll']][1] = bytes(cb)
    root['coll'] = -1; root['kids'] = [li]; n.blocks[0][1] = node_bytes(root)
    for e in root['extras']:                                                   # vanilla terminals carry BSX 523 (0x20B); the Fallout 3 ones 11
        if e >= 0 and n.blocks[e][0] == 'BSXFlags':
            nm, val = struct.unpack('<iI', n.blocks[e][1]); n.blocks[e][1] = struct.pack('<iI', nm, val | 0x200)

MODELS = {   # converted mesh path (inside the BA2) -> the monitor shape
    'meshes/new_vegas/terminals/terminal01.nif': ('T01Screen01:1', True),
    'meshes/new_vegas/terminals/terminal02.nif': ('T01Screen02:1', True),
    'meshes/new_vegas/terminals/terminaldesk01.nif': ('TerminalDesk01base:1', True),
    'meshes/new_vegas/dungeons/vaultruined/clutter/terminaldeskr01.nif': ('TerminalDeskR01:1', False),
    'meshes/new_vegas/dungeons/vault/accessories/voverseerterminal01.nif': ('VMonitorBank:0', True),
}
if __name__ == '__main__':
    OUT = r'X:\__CAPITAL_WORKDIR__\tool\output'
    f, names, recs = open_ba2(os.path.join(OUT, 'Fallout3 - Main.ba2')); idx = {x.lower().replace(chr(92), '/'): r for x, r in zip(names, recs)}
    def read(p):
        off, psz, usz = idx[p]; f.seek(off); d = f.read(psz or usz); return zlib.decompress(d) if psz else d
    D4 = r'X:\__CAPITAL_FO4__\Data'
    g, gn, gr = open_ba2(os.path.join(D4, 'Fallout4 - Meshes.ba2')); gi = {x.lower().replace(chr(92), '/'): r for x, r in zip(gn, gr)}
    off, psz, usz = gi['meshes/furniture/terminals/terminaloncorded.nif']; g.seek(off); van = g.read(psz or usz); van = zlib.decompress(van) if psz else van
    for p, (shape, clone) in MODELS.items():
        new, ok = patch(read(p), shape, van, clone)
        if not ok: print('shape not found', p, shape); continue
        dst = os.path.join(OUT, 'loose', *p.split('/')); os.makedirs(os.path.dirname(dst), exist_ok=True); open(dst, 'wb').write(new); print('patched', p, len(new))
