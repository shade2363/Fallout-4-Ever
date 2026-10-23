"""Give converted interior cells a usable Fallout 4 ambient light.

An FO3 CELL has a 40-byte XCLL; xConvert pads it to FO4's 136 bytes with zeros. FO4 lights actors (and dynamic objects) in interiors from the
six 'directional ambient' cube colours (XCLL +40..+63) plus the fog-far colour etc., all zero here => every NPC, creature and the player is a
black silhouette inside a converted interior. This fills those fields the way vanilla FO4 interiors have them: cube colours derived from the cell's
ambient colour (+ sides half, - sides full, like vanilla), fog-far colour = fog-near colour, fog max 0.7, and the vanilla tail defaults (template-inherit flags cleared: these cells have no lighting template).

  python fix_interior_lighting.py --in <esm> --out <esm>
Only interior cells whose XCLL is 136 bytes and whose cube colours are all zero are touched; record sizes do not change."""
import argparse, struct, sys
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records

ap = argparse.ArgumentParser()
ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--boost', type=float, default=1.0, help='scale applied to the derived cube colours')
a = ap.parse_args()

data = bytearray(open(a.inp, 'rb').read())
# vanilla (CroupManor01) tail, words 16..33 of the 136-byte XCLL; colour words are overwritten per cell
TAIL = bytes.fromhex('00000000 0000803f 1f1f1f00 3333333f 00000000 00000000 e0040000 00000000 00401c46 15151500 1f1f1f00 0000803f 0000803f 0000803f 0000803f 0000803f 00000000 00401c46'.replace(' ', ''))
def scale(c, f):
    return bytes(min(255, int(round(b * f))) for b in c[:3]) + bytes(1)
patched = skipped = 0
for r in iter_records(bytes(data)):
    if r.sig != 'CELL' or (r.flags & 0x40000):
        continue
    p = r.off + 24; end = p + r.size
    interior = False; xcll = None
    while p < end:
        s = bytes(data[p:p + 4]); sz = struct.unpack_from('<H', data, p + 4)[0]
        if s == b'DATA' and sz >= 1: interior = bool(data[p + 6] & 1)
        if s == b'XCLL' and sz == 136: xcll = p + 6
        p += 6 + sz
    if not interior or xcll is None:
        continue
    if any(data[xcll + 40:xcll + 64]):
        skipped += 1; continue
    amb = bytes(data[xcll:xcll + 4]); fog = bytes(data[xcll + 8:xcll + 12])
    if not any(amb[:3]):
        amb = bytes([40, 40, 40, 0])                        # cells with black ambient still need some actor fill light
    half = scale(amb, 0.5 * a.boost); full = scale(amb, a.boost)
    cube = half + full + half + full + half + full           # X+ X- Y+ Y- Z+ Z-
    tail = bytearray(TAIL)
    tail[8:12] = fog if any(fog[:3]) else bytes([31, 31, 31, 0])            # fog far colour
    tail[36:40] = fog if any(fog[:3]) else bytes([21, 21, 21, 0])           # word 25
    data[xcll + 40:xcll + 64] = cube
    data[xcll + 64:xcll + 136] = bytes(tail)
    patched += 1
open(a.out, 'wb').write(bytes(data))
print('interior lighting: %d cells patched, %d already had ambient cube colours -> %s' % (patched, skipped, a.out))
