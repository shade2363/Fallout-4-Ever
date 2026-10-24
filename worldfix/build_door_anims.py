"""For every DOOR base record of the converted plugins whose model has no animation, build an animated copy (add_door_anim) as a loose file in tool/output/loose/meshes.
A model that already exists as a loose file is read from there before the archives: the mesh repair step writes the doors the bulk conversion could not do (Vault 101,
the metro tunnel door ...) as loose files, and a door that is only looked up in the archives would stay without a model and without a swing animation.
Re-writing the keyframed-collision copies (scan_animated_nifs) is separate.   python build_door_anims.py [--angle 90]"""
import sys, os, zlib, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records, subrecords
from ba2_extract import open_ba2
import add_door_anim as A

ROOT = 'X:/__CAPITAL_WORKDIR__/tool/output/'
ARCHIVES = ('Fallout3 - Main.ba2', 'Anchorage - Main.ba2', 'ThePitt - Main.ba2', 'BrokenSteel - Main.ba2', 'PointLookout - Main.ba2', 'Zeta - Main.ba2')
PLUGINS = ('Fallout3', 'Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta')


def open_archives(root=ROOT):
    """{path inside the archives (lower case, forward slashes): (open file, record)} for every .nif of the converted main archives"""
    files = {}
    for name in ARCHIVES:
        f, names, recs = open_ba2(root + name)
        for n, r in zip(names, recs):
            if n.lower().endswith('.nif'): files[n.lower().replace(chr(92), '/')] = (f, r)
    return files


def loose_path(key, root=ROOT):
    return os.path.join(root, 'loose', key.replace('/', os.sep))


def read_model(key, files, root=ROOT):
    """the model's bytes: the loose copy when there is one, else the one in the converted archives, else None"""
    p = loose_path(key, root)
    if os.path.isfile(p):
        with open(p, 'rb') as fh:
            return fh.read()
    if key in files:
        f, (off, psz, usz) = files[key]; f.seek(off); d = f.read(psz or usz)
        return zlib.decompress(d) if psz else d
    return None


def door_models(root=ROOT):
    """{'meshes/<model path>': editor id} of every DOOR base record of the converted plugins"""
    models = {}
    for esm in PLUGINS:
        d = open(root + esm + '.esm', 'rb').read()
        for r in iter_records(d):
            if r.sig == 'DOOR':
                s = dict(subrecords(d, r)); m = s.get('MODL', b'').rstrip(bytes(1)).decode('latin1')
                if m: models.setdefault('meshes/' + m.lower().replace(chr(92), '/'), s.get('EDID', b'').rstrip(bytes(1)).decode('latin1'))
    return models


def main(angle=90.0, root=ROOT):
    files = open_archives(root)
    stat = collections.Counter(); skipped = []
    for key, edid in sorted(door_models(root).items()):
        d = read_model(key, files, root)
        if d is None: stat['model missing from archives'] += 1; skipped.append(('missing', key)); continue
        try:
            new, ch = A.add_anim(d, angle)
        except Exception as e:
            stat['error ' + type(e).__name__] += 1; skipped.append((type(e).__name__ + ' ' + str(e)[:50], key)); continue
        if not ch:
            stat['already animated / not applicable']  += 1; continue
        p = loose_path(key, root); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(new); stat['animation added'] += 1
    print(dict(stat)); [print('  skipped:', s) for s in skipped[:20]]


if __name__ == '__main__':
    main(float(sys.argv[sys.argv.index('--angle') + 1]) if '--angle' in sys.argv else 90.0)
