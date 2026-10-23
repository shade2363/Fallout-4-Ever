"""Give a converted hinged-door NIF (FO4 v130) an Open/Close swing animation.

Fallout 3 swung simple doors open in engine code, so their .nif has no animation at all; Fallout 4 only moves a door by playing 'Open'/'Close' sequences
of a NiControllerManager inside the .nif.  Without it the door toggles OPEN/CLOSE but never moves.

Built exactly like a vanilla FO4 hinged door (IndMetalDoor01.nif): the root's children and collision move under one new child node 'DoorLeaf' (pivot = the
model origin = the hinge, as in FO3); the root gets BSX 'animated', a NiControllerManager, a NiMultiTargetTransformController, two NiControllerSequence
('Open' = rotate the leaf +90 deg about Z in 1.0 s, 'Close' = back) with a linear quaternion key each, text keys start/end, and an object palette.
The collision body of the leaf is then made keyframed by fix_nif_anim_collision (otherwise a static body pins the leaf).

  python add_door_anim.py in.nif out.nif [--angle 90]
Library: add_anim(nif_bytes, angle_deg=90) -> (new_bytes, changed: bool)"""
import struct, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fix_nif_anim_collision as fk

FLT_MAX = 3.4028234663852886e+38

class Nif:
    def __init__(self, b):
        self.b = b
        p = b.index(b'\n') + 1
        ver, endian, uver, nb = struct.unpack_from('<IBII', b, p); p += 13
        self.ver, self.endian, self.uver = ver, endian, uver
        self.bsver, = struct.unpack_from('<I', b, p); p += 4
        assert self.bsver == 130, 'not an FO4 nif'
        self.pre = b[:p]                                    # up to and including bsver
        q = p
        for _ in range(4): q += 1 + b[q]                    # author, process script, export script, max filepath
        self.exportinfo = b[p:q]; p = q
        nt = struct.unpack_from('<H', b, p)[0]; p += 2
        self.types = []
        for _ in range(nt):
            n = struct.unpack_from('<I', b, p)[0]; p += 4; self.types.append(b[p:p+n].decode()); p += n
        idx = list(struct.unpack_from('<%dH' % nb, b, p)); p += 2 * nb
        sizes = struct.unpack_from('<%dI' % nb, b, p); p += 4 * nb
        ns, ml = struct.unpack_from('<II', b, p); p += 8
        self.strs = []
        for _ in range(ns):
            n = struct.unpack_from('<I', b, p)[0]; p += 4; self.strs.append(b[p:p+n].decode('latin1')); p += n
        ng = struct.unpack_from('<I', b, p)[0]; self.groups = b[p:p + 4 + 4 * ng]; p += 4 + 4 * ng
        self.blocks = []                                    # [type name, bytes]
        for i in range(nb):
            self.blocks.append([self.types[idx[i]], bytes(b[p:p+sizes[i]])]); p += sizes[i]
        self.footer = bytes(b[p:])
    def sid(self, s):
        if s not in self.strs: self.strs.append(s)
        return self.strs.index(s)
    def add(self, tname, data):
        if tname not in self.types: self.types.append(tname)
        self.blocks.append([tname, data]); return len(self.blocks) - 1
    def tobytes(self):
        out = bytearray(self.pre) + self.exportinfo
        out += struct.pack('<H', len(self.types))
        for t in self.types: out += struct.pack('<I', len(t)) + t.encode()
        for t, d in self.blocks: out += struct.pack('<H', self.types.index(t))
        for t, d in self.blocks: out += struct.pack('<I', len(d))
        out += struct.pack('<II', len(self.strs), max((len(s) for s in self.strs), default=0))
        for s in self.strs: out += struct.pack('<I', len(s)) + s.encode('latin1')
        out += self.groups
        for t, d in self.blocks: out += d
        out += self.footer
        # block count lives in the header prefix: pre = ... version(4) endian(1) userver(4) numblocks(4) bsver(4)
        nbo = len(self.pre) - 4 - 4
        struct.pack_into('<I', out, nbo, len(self.blocks))
        return bytes(out)

def node_fields(d):
    """parse a bsver-130 NiNode/BSFadeNode block -> dict"""
    name, ne = struct.unpack_from('<iI', d, 0); p = 8
    extras = list(struct.unpack_from('<%di' % ne, d, p)); p += 4 * ne
    ctrl, flags = struct.unpack_from('<iI', d, p); p += 8
    transform = d[p:p + 52]; p += 52
    coll, nc = struct.unpack_from('<iI', d, p); p += 8
    kids = list(struct.unpack_from('<%di' % nc, d, p)); p += 4 * nc
    return dict(name=name, extras=extras, ctrl=ctrl, flags=flags, transform=transform, coll=coll, kids=kids, tail=d[p:])
def node_bytes(f):
    return (struct.pack('<iI', f['name'], len(f['extras'])) + struct.pack('<%di' % len(f['extras']), *f['extras']) + struct.pack('<iI', f['ctrl'], f['flags']) +
            f['transform'] + struct.pack('<iI', f['coll'], len(f['kids'])) + struct.pack('<%di' % len(f['kids']), *f['kids']) + f['tail'])

IDENT = struct.pack('<3f', 0, 0, 0) + struct.pack('<9f', 1, 0, 0, 0, 1, 0, 0, 0, 1) + struct.pack('<f', 1.0)

def add_anim(b, angle_deg=90.0, duration=1.0):
    nif = Nif(b)
    if any(t == 'NiControllerManager' for t, d in nif.blocks): return b, False
    if not nif.blocks or nif.blocks[0][0] not in ('NiNode', 'BSFadeNode'): return b, False
    root = node_fields(nif.blocks[0][1])
    old_ctrl = root['ctrl']                                 # an existing controller (e.g. alpha) is chained after ours
    # BSX flags: set 'animated' bit
    bsx = None
    for e in root['extras']:
        if e >= 0 and nif.blocks[e][0] == 'BSXFlags': bsx = e
    if bsx is None:
        bsx = nif.add('BSXFlags', struct.pack('<iI', nif.sid('BSX'), 0)); root['extras'].append(bsx)
    nm, val = struct.unpack('<iI', nif.blocks[bsx][1]); nif.blocks[bsx][1] = struct.pack('<iI', nm, val | 1)
    S = nif.sid
    leaf_name = S('DoorLeaf')
    # --- leaf node takes over the root's children and collision
    leaf = dict(name=leaf_name, extras=[], ctrl=-1, flags=0x8e, transform=IDENT, coll=root['coll'], kids=root['kids'], tail=b'')
    leaf_i = nif.add('NiNode', node_bytes(leaf))
    if root['coll'] >= 0:
        cb = bytearray(nif.blocks[root['coll']][1]); struct.pack_into('<i', cb, 0, leaf_i); nif.blocks[root['coll']][1] = bytes(cb)
    root['coll'] = -1; root['kids'] = [leaf_i]
    # --- animation blocks (indexes assigned in order)
    base = len(nif.blocks)
    mgr_i, mttc_i, seq_open, int_open, dat_open, tk_open, seq_close, int_close, dat_close, tk_close, pal_i = range(base, base + 11)
    root['ctrl'] = mgr_i
    nif.blocks[0][1] = node_bytes(root)
    FM = struct.pack('<f', FLT_MAX); NFM = struct.pack('<f', -FLT_MAX)
    def timectl(next_ctrl, flags, target): return struct.pack('<iH', next_ctrl, flags) + struct.pack('<ff', 1.0, 0.0) + FM + NFM + struct.pack('<i', target)
    nif.add('NiControllerManager', timectl(mttc_i, 0x4c, 0) + b'\x00' + struct.pack('<I', 2) + struct.pack('<ii', seq_open, seq_close) + struct.pack('<i', pal_i))
    targets = [leaf_i] + [-1] * 4
    nif.add('NiMultiTargetTransformController', timectl(old_ctrl, 0x6c, 0) + struct.pack('<H', len(targets)) + struct.pack('<%di' % len(targets), *targets))
    s_name, s_start, s_end, s_ctl, s_open, s_close, s_empty = S('Open'), S('start'), S('end'), S('NiTransformController'), S('Open'), S('Close'), S('')
    ang = math.radians(angle_deg); q_end = (math.cos(ang / 2), 0.0, 0.0, math.sin(ang / 2)); q_0 = (1.0, 0.0, 0.0, 0.0)
    def seq(name_idx, interp, tk):
        cb = struct.pack('<iiB', interp, mttc_i, 0) + struct.pack('<5i', leaf_name, -1, s_ctl, -1, -1)
        return (struct.pack('<iII', name_idx, 1, 1) + cb + struct.pack('<fIIfffii', 1.0, tk, 2, 1.0, 0.0, duration, mgr_i, root['name']) + struct.pack('<H', 0))
    def interp(data): return struct.pack('<8f', *([-FLT_MAX] * 8)) + struct.pack('<i', data)
    def tdata(qa, qb): return (struct.pack('<II', 2, 1) + struct.pack('<f', 0.0) + struct.pack('<4f', *qa) + struct.pack('<f', duration) + struct.pack('<4f', *qb) + struct.pack('<II', 0, 0))
    def textkeys(): return struct.pack('<iI', s_empty, 2) + struct.pack('<fi', 0.0, s_start) + struct.pack('<fi', duration, s_end)
    nif.add('NiControllerSequence', seq(s_open, int_open, tk_open)); nif.add('NiTransformInterpolator', interp(dat_open)); nif.add('NiTransformData', tdata(q_0, q_end)); nif.add('NiTextKeyExtraData', textkeys())
    nif.add('NiControllerSequence', seq(s_close, int_close, tk_close)); nif.add('NiTransformInterpolator', interp(dat_close)); nif.add('NiTransformData', tdata(q_end, q_0)); nif.add('NiTextKeyExtraData', textkeys())
    # palette: every named NiNode / BSTriShape (like vanilla)
    ents = []
    for i, (t, d) in enumerate(nif.blocks):
        if t in ('NiNode', 'BSFadeNode', 'BSTriShape', 'BSSubIndexTriShape', 'BSMeshLODTriShape', 'BSDynamicTriShape'):
            k = struct.unpack_from('<i', d, 0)[0]
            if 0 <= k < len(nif.strs) and nif.strs[k]: ents.append((nif.strs[k], i))
    pal = struct.pack('<iI', 0, len(ents)) + b''.join(struct.pack('<I', len(n)) + n.encode('latin1') + struct.pack('<i', i) for n, i in ents)
    nif.add('NiDefaultAVObjectPalette', pal)
    assert len(nif.blocks) == pal_i + 1
    out = nif.tobytes()
    out, nb = fk.patch_bytes(out)           # make the leaf's collision body keyframed
    return out, True

if __name__ == '__main__':
    ang = float(sys.argv[sys.argv.index('--angle') + 1]) if '--angle' in sys.argv else 90.0
    new, ch = add_anim(open(sys.argv[1], 'rb').read(), ang)
    os.makedirs(os.path.dirname(os.path.abspath(sys.argv[2])), exist_ok=True)
    open(sys.argv[2], 'wb').write(new)
    print('animation added' if ch else 'unchanged')
