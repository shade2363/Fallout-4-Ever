"""For every DOOR base record of the converted plugins whose model has no animation, build an animated copy (add_door_anim) as a loose file in tool/output/meshes.
Also re-writes the keyframed-collision copies (scan_animated_nifs) is separate.   python build_door_anims.py [--angle 90]"""
import sys, os, zlib, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
from navlib import iter_records, subrecords
from ba2_extract import open_ba2
import add_door_anim as A
root = 'X:/__CAPITAL_WORKDIR__/tool/output/'
files = {}
for name in ('Fallout3 - Main.ba2', 'Anchorage - Main.ba2', 'ThePitt - Main.ba2', 'BrokenSteel - Main.ba2', 'PointLookout - Main.ba2', 'Zeta - Main.ba2'):
    f, names, recs = open_ba2(root + name)
    for n, r in zip(names, recs):
        if n.lower().endswith('.nif'): files[n.lower().replace(chr(92), '/')] = (f, r)
ang = float(sys.argv[sys.argv.index('--angle') + 1]) if '--angle' in sys.argv else 90.0
models = {}
for esm in ('Fallout3', 'Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta'):
    d = open(root + esm + '.esm', 'rb').read()
    for r in iter_records(d):
        if r.sig == 'DOOR':
            s = dict(subrecords(d, r)); m = s.get('MODL', b'').rstrip(bytes(1)).decode('latin1')
            if m: models.setdefault('meshes/' + m.lower().replace(chr(92), '/'), s.get('EDID', b'').rstrip(bytes(1)).decode('latin1'))
stat = collections.Counter(); skipped = []
for key, edid in sorted(models.items()):
    if key not in files: stat['model missing from archives'] += 1; skipped.append(('missing', key)); continue
    f, (off, psz, usz) = files[key]; f.seek(off); d = f.read(psz or usz); d = zlib.decompress(d) if psz else d
    try:
        new, ch = A.add_anim(d, ang)
    except Exception as e:
        stat['error ' + type(e).__name__] += 1; skipped.append((type(e).__name__ + ' ' + str(e)[:50], key)); continue
    if not ch:
        stat['already animated / not applicable']  += 1; continue
    p = os.path.join(root, 'loose', key.replace('/', os.sep)); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(new); stat['animation added'] += 1
print(dict(stat)); [print('  skipped:', s) for s in skipped[:20]]
