"""Scan the converted BA2s for animated NIFs whose animated nodes have static collision bodies; optionally write the fixed copies as loose files.
  python scan_animated_nifs.py [--out tool/output/loose]    (default: count only; fixed copies go to <out>/<path inside the BA2>)"""
import sys, os, zlib, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ba2_extract import open_ba2
from fix_nif_anim_collision import patch_bytes
out = None
if '--out' in sys.argv: out = sys.argv[sys.argv.index('--out') + 1]
root = 'X:/__CAPITAL_WORKDIR__/tool/output/'
total = fixed = bodies = failed = 0
sizes = collections.Counter()
for name in ('Fallout3 - Main.ba2', 'Anchorage - Main.ba2', 'ThePitt - Main.ba2', 'BrokenSteel - Main.ba2', 'PointLookout - Main.ba2', 'Zeta - Main.ba2'):
    f, names, recs = open_ba2(root + name)
    for n, (off, psz, usz) in zip(names, recs):
        if not n.lower().endswith('.nif'): continue
        f.seek(off); d = f.read(psz or usz)
        if psz: d = zlib.decompress(d)
        if b'NiControllerManager' not in d[:20000] or b'bhkPhysicsSystem' not in d[:20000]: continue
        total += 1
        try:
            new, k = patch_bytes(d)
        except Exception as e:
            failed += 1; sizes['fail: ' + type(e).__name__] += 1; continue
        if k:
            fixed += 1; bodies += k
            if out:
                p = os.path.join(out, n.replace('/', os.sep)); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(new)
print('animated nifs with physics: %d, fixed: %d (%d bodies), failed: %d %s' % (total, fixed, bodies, failed, dict(sizes)))
