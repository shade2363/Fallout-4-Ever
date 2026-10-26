"""Tests of worldfix/elric_prep.py (no game, no Elric needed): a mesh whose collision points at a body without a shape gets that link cut; healthy meshes are left alone.

  python -m unittest tests.test_elric_prep -v
"""
import os, shutil, struct, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'worldfix'))
sys.path.insert(0, os.path.join(ROOT, 'navmesh'))
import add_door_anim as A
import elric_prep

def read(path):
    with open(path, 'rb') as f:
        return f.read()


IDENT = struct.pack('<3f', 0, 0, 0) + struct.pack('<9f', 1, 0, 0, 0, 1, 0, 0, 0, 1) + struct.pack('<f', 1.0)


def make_nif(blocks, strs=('Root',)):
    """a minimal Fallout 4 (bsver 130) NIF made of (type, bytes) blocks: what add_door_anim.Nif reads and writes"""
    types = []
    for t, _ in blocks:
        if t not in types:
            types.append(t)
    out = b'Gamebryo File Format, Version 20.2.0.7\n' + struct.pack('<IBII', 0x14020007, 1, 12, len(blocks)) + struct.pack('<I', 130) + b'\x00' * 4
    out += struct.pack('<H', len(types)) + b''.join(struct.pack('<I', len(t)) + t.encode() for t in types)
    out += b''.join(struct.pack('<H', types.index(t)) for t, _ in blocks)
    out += b''.join(struct.pack('<I', len(d)) for _, d in blocks)
    out += struct.pack('<II', len(strs), max(len(s) for s in strs)) + b''.join(struct.pack('<I', len(s)) + s.encode() for s in strs)
    out += struct.pack('<I', 0)
    return out + b''.join(d for _, d in blocks)


def node(coll):
    """a NiNode named 'Root' with no children and the given collision object reference"""
    return struct.pack('<iI', 0, 0) + struct.pack('<iI', -1, 0x8e) + IDENT + struct.pack('<iI', coll, 0)


def collision(body):
    return struct.pack('<iHi', 0, 1, body)


def body(shape):
    return struct.pack('<i', shape) + bytes(40)


def collision_ref(data):
    """the collision reference of the root node of a NIF"""
    return A.node_fields(A.Nif(data).blocks[0][1])['coll']


class StripTests(unittest.TestCase):
    def test_a_body_without_a_shape_loses_its_link(self):
        nif = make_nif([('NiNode', node(1)), ('bhkCollisionObject', collision(2)), ('bhkRigidBody', body(-1))])
        new, n = elric_prep.strip_shapeless_collision(nif)
        self.assertEqual(n, 1)
        self.assertEqual(collision_ref(nif), 1)
        self.assertEqual(collision_ref(new), -1)
        self.assertEqual(len(A.Nif(new).blocks), 3)              # nothing else changes: the orphaned blocks stay

    def test_a_collision_object_without_a_body_loses_its_link(self):
        nif = make_nif([('NiNode', node(1)), ('bhkCollisionObject', collision(-1))])
        new, n = elric_prep.strip_shapeless_collision(nif)
        self.assertEqual(n, 1)
        self.assertEqual(collision_ref(new), -1)

    def test_a_healthy_body_is_left_alone_byte_for_byte(self):
        nif = make_nif([('NiNode', node(1)), ('bhkCollisionObject', collision(2)), ('bhkRigidBody', body(3)), ('bhkBoxShape', bytes(32))])
        new, n = elric_prep.strip_shapeless_collision(nif)
        self.assertEqual(n, 0)
        self.assertEqual(new, nif)

    def test_all_collision_cuts_even_a_healthy_body(self):
        nif = make_nif([('NiNode', node(1)), ('bhkCollisionObject', collision(2)), ('bhkRigidBody', body(3)), ('bhkBoxShape', bytes(32))])
        new, n = elric_prep.strip_shapeless_collision(nif, all_collision=True)
        self.assertEqual(n, 1)
        self.assertEqual(collision_ref(new), -1)

    def test_a_mesh_without_collision_is_untouched(self):
        nif = make_nif([('NiNode', node(-1))])
        self.assertEqual(elric_prep.strip_shapeless_collision(nif), (nif, 0))

    def test_the_result_is_a_valid_nif_again(self):
        nif = make_nif([('NiNode', node(1)), ('bhkCollisionObject', collision(2)), ('bhkRigidBody', body(-1))])
        new, _ = elric_prep.strip_shapeless_collision(nif)
        again, n = elric_prep.strip_shapeless_collision(new)
        self.assertEqual((again, n), (new, 0))                  # nothing left to do: a second pass is a no-op


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, data):
        p = os.path.join(self.tmp, *rel.split('/'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data)
        return p

    def test_folder_run_rewrites_only_the_bad_files_and_survives_garbage(self):
        bad = self.write('new_vegas/clutter/hat.nif', make_nif([('NiNode', node(1)), ('bhkCollisionObject', collision(2)), ('bhkRigidBody', body(-1))]))
        good_data = make_nif([('NiNode', node(-1))])
        good = self.write('new_vegas/clutter/ok.nif', good_data)
        junk = self.write('new_vegas/clutter/junk.nif', b'this is not a nif')
        notnif = self.write('new_vegas/readme.txt', b'x')
        self.assertEqual(elric_prep.main(self.tmp), 0)
        self.assertEqual(collision_ref(read(bad)), -1)
        self.assertEqual(read(good), good_data)
        self.assertEqual(read(junk), b'this is not a nif')
        self.assertEqual(read(notnif), b'x')

    def test_a_single_file_can_be_given(self):
        p = self.write('one.nif', make_nif([('NiNode', node(1)), ('bhkCollisionObject', collision(2)), ('bhkRigidBody', body(3)), ('bhkBoxShape', bytes(32))]))
        elric_prep.main(p)
        self.assertEqual(collision_ref(read(p)), 1)               # healthy: unchanged
        elric_prep.main(p, all_collision=True)
        self.assertEqual(collision_ref(read(p)), -1)

    def test_command_line_shape(self):
        import subprocess
        r = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'worldfix', 'elric_prep.py'), self.tmp, '--bogus'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn('elric_prep.py', r.stdout)


if __name__ == '__main__':
    unittest.main()
