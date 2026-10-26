"""Make the NifSkope-converted meshes safe for Elric (the Fallout 4 mesh optimizer) before it sees them.

Elric (ElricInterop.dll) dies with an access violation on a mesh whose collision object points at a rigid body that has no shape (or at no body at all).
Fallout 3 shipped such bodies on hats, helmets, glasses, the baby carriage, the Tranquility pod, the Vault 101 / metro doors, the overseer desks, the Pitt cart,
the Broken Steel stage / Tesla coil / water barrel, the Point Lookout ferris wheel and coffins, the Zeta machine ... : 49 meshes, every one of them has such a body,
none of 150 meshes picked at random does.  A body without a shape collides with nothing in the original game either, so the node's collision link is cut and the mesh
goes through Elric like any other (it used to be skipped, and the object was then missing or had to be rebuilt by hand in the mesh repair step).

  python elric_prep.py <folder with the converted meshes | one .nif>             rewrites only the files that need it, in place
  python elric_prep.py <folder | .nif> --all-collision                          last resort for a mesh that still crashes Elric: cut every collision link
Library use: strip_shapeless_collision(nif_bytes, all_collision=False) -> (new_bytes, number_of_nodes_changed)"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import add_door_anim as A

NODE_TYPES = ('NiNode', 'BSFadeNode', 'BSLeafAnimNode', 'BSMultiBoundNode', 'BSOrderedNode', 'BSValueNode', 'BSBlastNode', 'BSDamageStage', 'BSTreeNode',
              'NiBillboardNode', 'NiSwitchNode', 'NiLODNode')          # all start with the NiNode layout that add_door_anim.node_fields reads; what follows is kept as it is
COLLISION_TYPES = ('bhkCollisionObject', 'bhkBlendCollisionObject', 'bhkSPCollisionObject', 'bhkPCollisionObject')       # target(4) flags(2) body(4)


def _usable(blocks, ref):
    return 0 <= ref < len(blocks)


def strip_shapeless_collision(b, all_collision=False):
    nif = A.Nif(b)
    changed = 0
    for i, (t, d) in enumerate(nif.blocks):
        if t not in NODE_TYPES:
            continue
        f = A.node_fields(d)
        if not _usable(nif.blocks, f['coll']):
            continue
        if not all_collision:
            ct, cd = nif.blocks[f['coll']]
            if ct not in COLLISION_TYPES or len(cd) < 10:
                continue
            body = struct.unpack_from('<i', cd, 6)[0]
            if _usable(nif.blocks, body):
                bd = nif.blocks[body][1]
                if len(bd) >= 4 and struct.unpack_from('<i', bd, 0)[0] >= 0:            # bhkWorldObject: the shape comes first
                    continue
        f['coll'] = -1
        nif.blocks[i][1] = A.node_bytes(f)
        changed += 1
    return (nif.tobytes() if changed else b), changed


def _nifs(target):
    if os.path.isfile(target):
        yield target
        return
    for root, _, names in os.walk(target):
        for n in sorted(names):
            if n.lower().endswith('.nif'):
                yield os.path.join(root, n)


def main(target, all_collision=False):
    scanned = files = nodes = unreadable = 0
    changed = []
    base = target if os.path.isdir(target) else os.path.dirname(target)
    for p in _nifs(target):
        scanned += 1
        try:
            with open(p, 'rb') as f:
                raw = f.read()
            new, k = strip_shapeless_collision(raw, all_collision)
        except Exception:                  # a file this reader does not understand goes to Elric untouched, as before
            unreadable += 1
            continue
        if k:
            with open(p, 'wb') as f:
                f.write(new)
            files += 1
            nodes += k
            changed.append(os.path.relpath(p, base).replace(os.sep, '/'))
    for c in changed:
        print('  %s: %s' % ('collision removed' if all_collision else 'collision link without a shape removed', c))
    print('elric prep: %d meshes scanned, %d changed (%d collision links cut), %d not readable (left as they are)' % (scanned, files, nodes, unreadable))
    return 0


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opts = [a for a in sys.argv[1:] if a.startswith('--')]
    if len(args) != 1 or not os.path.exists(args[0]) or any(o != '--all-collision' for o in opts):
        print(__doc__)
        sys.exit(2)
    sys.exit(main(args[0], '--all-collision' in opts))
