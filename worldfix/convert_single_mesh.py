"""Convert ONE Fallout 3 mesh that the bulk conversion had to skip (Elric crashed): extract from the FO3 BSA, NifSkope convert, detach collision bodies with a NULL shape
(the crash cause on VDoor01), Elric, then the animated-collision fix; result goes to tool/output/loose/meshes/new_vegas/<path>.
  python convert_single_mesh.py dungeons/vault/halls/vdoor01.nif [--no-collision]"""
import sys, os, subprocess, struct, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import add_door_anim as A, fix_nif_anim_collision as fk
rel = sys.argv[1].replace(chr(92), '/').lower(); nocoll = '--no-collision' in sys.argv
R = 'X:/__CAPITAL_WORKDIR__'; tool = R + '/tool'; fo4 = 'X:/__CAPITAL_FO4__'
lab = R + '/lab/conv_single'; shutil.rmtree(lab, ignore_errors=True)
ext = lab + '/extracted/meshes/' + os.path.dirname(rel); os.makedirs(ext); os.makedirs(lab + '/temp')
D3 = 'X:/__CAPITAL_FO3_DATA__/'
for bsa in ('Fallout - Meshes.bsa', 'Anchorage - Main.bsa', 'ThePitt - Main.bsa', 'BrokenSteel - Main.bsa', 'PointLookout - Main.bsa', 'Zeta - Main.bsa'):
    r_ = subprocess.run([sys.executable, R + '/worldfix/bsa_extract.py', D3 + bsa, 'get', 'meshes/' + rel, ext + '/' + os.path.basename(rel)], capture_output=True, text=True)
    if r_.returncode == 0 and os.path.exists(ext + '/' + os.path.basename(rel)): break
else:
    print('NOT IN ANY BSA', rel); sys.exit(2)
subprocess.run([tool + '/build/nifskope_converter/release/NifSkope.exe', '--convert', lab + '/temp', lab + '/extracted', lab + '/extracted'], cwd=tool, check=True, capture_output=True)
pre = lab + '/temp/meshes/new_vegas/' + rel
n = A.Nif(open(pre, 'rb').read()); S = n.strs; detached = 0
for i, (t, d) in enumerate(n.blocks):
    if t in ('NiNode', 'BSFadeNode'):
        f = A.node_fields(d)
        if f['coll'] < 0: continue
        ct, cd = n.blocks[f['coll']]
        bad = nocoll
        if ct == 'bhkCollisionObject':
            body = struct.unpack_from('<i', cd, 6)[0]
            if body < 0 or struct.unpack_from('<i', n.blocks[body][1], 0)[0] < 0: bad = True       # body without a shape
        if bad: f['coll'] = -1; n.blocks[i][1] = A.node_bytes(f); detached += 1
os.makedirs(lab + '/var/meshes/new_vegas/' + os.path.dirname(rel), exist_ok=True); open(lab + '/var/meshes/new_vegas/' + rel, 'wb').write(n.tobytes())
print('collision bodies detached before Elric:', detached)
try:
    cmd = r'"%s/Tools/Elric/Elrich.exe" .\Settings\PCMeshes.esf "-ElricOptions.ConvertTarget=%s/var/meshes" "-ElricOptions.OutputDirectory=%s/out/meshes"' % (fo4, lab, lab)
    subprocess.run(cmd.replace('/', chr(92)) if False else cmd, cwd=tool + '/src/models-and-animations/elric', timeout=120, capture_output=True)
except subprocess.TimeoutExpired: pass
res = lab + '/out/meshes/new_vegas/' + rel
if not os.path.exists(res): print('ELRIC FAILED for', rel); sys.exit(1)
new, k = fk.patch_bytes(open(res, 'rb').read())
dst = R + '/tool/output/loose/meshes/new_vegas/' + rel; os.makedirs(os.path.dirname(dst), exist_ok=True); open(dst, 'wb').write(new)
print('OK', rel, len(new), 'bytes; keyframed bodies:', k)
