"""Make collision bodies of ANIMATED nodes keyframed in converted FO3/FNV NIFs (FO4 v130, Havok hk_2014 physics blob).

Problem: xConvert writes every collision body of a converted .nif as static (hknpPhysicsSystemData has no motion records, body motionId = 0x7fffffff).
A static body pins its NiNode in place, so the NiControllerManager animation (doors, gates, lids ...) plays but the node never moves - only parts
without a collision body (latches) visibly animate.  Vanilla FO4 doors give each moving slab a motion record (hknpMotionCinfo) and point the body at it.

This tool: for each NiNode that is the target of a NiControllerSequence controlled block AND has a bhkNPCollisionObject, add one hknpMotionCinfo
(template copied from vanilla VltDoor01) to the physics blob and set that body's motionId to it.  Blob surgery: insert the motion records in front of
the body array, fix the section header offsets, local/global/virtual fixups, the byte-array length and the NIF block size.

  python fix_nif_anim_collision.py in.nif out.nif          (prints what it changed; exit 0 even when nothing to do)
Library use: patch_bytes(nif_bytes) -> (new_bytes, n_bodies_fixed)"""
import struct, sys, os

# hknpMotionCinfo template (0x70 bytes) taken from vanilla Interiors\Vault\Doors\VltDoor01.nif (first motion record)
MOTION = bytes.fromhex(
    'ffff0100 00000000 0000803f f0ff7f5f f0ff7f5f 00000000 00000000 00000000'
    '00000000 00000000 00000000 00000000 00000000 00000000 24c2cf3f 00000000'
    '00000000 00000000 00000000 ffff7f3f 00000000 00000000 00000000 00000000'
    '00000000 00000000 00000000 00000000'.replace(' ', ''))
assert len(MOTION) == 0x70
BODY_STRIDE = 0x60

def read_nif(b):
    p = b.index(b'\n') + 1
    ver, endian, uver, nb = struct.unpack_from('<IBII', b, p); p += 13
    bsver = struct.unpack_from('<I', b, p)[0]; p += 4
    for _ in range(4 if bsver == 130 else 3): p += 1 + b[p]
    nt = struct.unpack_from('<H', b, p)[0]; p += 2
    types = []
    for _ in range(nt):
        n = struct.unpack_from('<I', b, p)[0]; p += 4; types.append(b[p:p+n].decode()); p += n
    idx = struct.unpack_from('<%dH' % nb, b, p); p += 2 * nb
    sizes_off = p
    sizes = list(struct.unpack_from('<%dI' % nb, b, p)); p += 4 * nb
    ns, ml = struct.unpack_from('<II', b, p); p += 8
    strs = []
    for _ in range(ns):
        n = struct.unpack_from('<I', b, p)[0]; p += 4; strs.append(b[p:p+n].decode('latin1')); p += n
    ng = struct.unpack_from('<I', b, p)[0]; p += 4 + 4 * ng
    blocks = []
    for i in range(nb):
        blocks.append((types[idx[i]], p, sizes[i])); p += sizes[i]
    return dict(nb=nb, sizes_off=sizes_off, strs=strs, blocks=blocks, bsver=bsver)

def fix_blob(blob, motion_for_bodies):
    """returns new blob bytes with len(motion_for_bodies) motion records; motion_for_bodies = sorted list of body indexes that become keyframed"""
    b = bytearray(blob)
    # section headers: 3 x 0x40 at 0x40; data section is the third
    sec = 0x40 + 2 * 0x40
    assert b[sec:sec + 8] == b'__data__', 'unexpected packfile layout'
    absstart, lfo, gfo, vfo, exo, imo, eno = struct.unpack_from('<7I', b, sec + 20)
    data = bytearray(b[absstart:absstart + lfo]); tail = bytes(b[absstart + lfo:])
    # arrays inside hknpPhysicsSystemData: ptr(8) size(4) cap(4); motionCinfos at 0x30, bodyCinfos at 0x40
    msz = struct.unpack_from('<I', data, 0x38)[0]
    if msz != 0: return blob, 0                      # already has motions
    bsz = struct.unpack_from('<I', data, 0x48)[0]
    # locate body array via local fixup (src 0x40)
    lfx = []
    p = 0
    while p < gfo - lfo:
        s, d = struct.unpack_from('<II', tail, p); p += 8
        if s == 0xffffffff: break
        lfx.append([s, d])
    body_off = next(d for s, d in lfx if s == 0x40)
    bodies = [i for i in motion_for_bodies if i < bsz]
    if not bodies: return blob, 0
    n = len(bodies); delta = n * len(MOTION)
    # 1. insert motion records at body_off; shift
    new_data = bytearray(data[:body_off] + MOTION * n + data[body_off:])
    struct.pack_into('<I', new_data, 0x38, n); struct.pack_into('<I', new_data, 0x3c, 0x80000000 | n)
    # 2. body motion ids (+0x0c of each 0x60 body record)
    for k, bi in enumerate(bodies):
        o = body_off + delta + bi * BODY_STRIDE
        struct.pack_into('<I', new_data, o + 0x0c, k)
    # 3. local fixups
    new_lfx = []
    for s, d in lfx:
        new_lfx.append([s + delta if s >= body_off else s, d + delta if d >= body_off else d])
    new_lfx.append([0x30, body_off]); new_lfx.sort()
    lf_bytes = b''.join(struct.pack('<II', s, d) for s, d in new_lfx)
    while len(lf_bytes) % 16: lf_bytes += struct.pack('<II', 0xffffffff, 0xffffffff)
    # 4. global fixups (src, section, dst) and virtual fixups (src, section, name offset)
    gf = bytearray(tail[gfo - lfo:vfo - lfo]); vf = bytearray(tail[vfo - lfo:exo - lfo]); rest = tail[exo - lfo:]
    def shift3(buf, shift_dst):
        for o in range(0, len(buf) - 11, 12):
            s, sec_i, d = struct.unpack_from('<III', buf, o)
            if s == 0xffffffff: continue
            if s >= body_off: s += delta
            if shift_dst and d >= body_off: d += delta
            struct.pack_into('<III', buf, o, s, sec_i, d)
    shift3(gf, True); shift3(vf, False)
    new_lfo = len(new_data); new_gfo = new_lfo + len(lf_bytes); new_vfo = new_gfo + len(gf); new_exo = new_vfo + len(vf)
    hdr = bytearray(b[:absstart])
    struct.pack_into('<7I', hdr, sec + 20, absstart, new_lfo, new_gfo, new_vfo, new_exo, new_exo + (imo - exo), new_exo + (eno - exo))
    return bytes(hdr) + bytes(new_data) + lf_bytes + bytes(gf) + bytes(vf) + bytes(rest), n

def patch_bytes(nb):
    nif = read_nif(nb); S = nif['strs']; blocks = nif['blocks']
    def name_of(i):
        t, off, sz = blocks[i]; k = struct.unpack_from('<i', nb, off)[0]; return S[k] if 0 <= k < len(S) else None
    animated = set()
    for t, off, sz in blocks:
        if t == 'NiControllerSequence':
            ncb = struct.unpack_from('<I', nb, off + 4)[0]; p = off + 12
            for _ in range(ncb):
                nn = struct.unpack_from('<i', nb, p + 9)[0]; p += 29
                if 0 <= nn < len(S): animated.add(S[nn])
    if not animated: return nb, 0
    bodies = set(); phys = None
    for i, (t, off, sz) in enumerate(blocks):
        if t == 'bhkPhysicsSystem': phys = i
    if phys is None: return nb, 0
    for i, (t, off, sz) in enumerate(blocks):
        if t == 'NiNode' and name_of(i) in animated:
            ne = struct.unpack_from('<I', nb, off + 4)[0]
            coll = struct.unpack_from('<i', nb, off + 8 + 4 * ne + 8 + 52)[0]
            if coll >= 0 and blocks[coll][0] == 'bhkNPCollisionObject':
                body_id = struct.unpack_from('<I', nb, blocks[coll][1] + 4 + 2 + 4)[0]   # target(4) flags(2) data(4) body(4)
                bodies.add(body_id)
    if not bodies: return nb, 0
    t, off, sz = blocks[phys]
    blen = struct.unpack_from('<I', nb, off)[0]
    new_blob, n = fix_blob(nb[off + 4:off + 4 + blen], sorted(bodies))
    if n == 0: return nb, 0
    rest_of_block = nb[off + 4 + blen:off + sz]
    new_block = struct.pack('<I', len(new_blob)) + new_blob + rest_of_block
    out = bytearray(nb[:off] + new_block + nb[off + sz:])
    struct.pack_into('<I', out, nif['sizes_off'] + 4 * phys, len(new_block))
    return bytes(out), n

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    new, n = patch_bytes(open(src, 'rb').read())
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    open(dst, 'wb').write(new)
    print('bodies made keyframed:', n)
