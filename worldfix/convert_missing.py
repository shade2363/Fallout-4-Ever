"""Convert every non-vanilla mesh that audit_meshes.py reports missing (bulk conversion skipped them) with convert_single_mesh.py.
  python convert_missing.py audit.txt   (audit.txt = output of audit_meshes.py)"""
import sys, subprocess, re, os
here = os.path.dirname(os.path.abspath(__file__))
paths = []
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    m = re.match(r"^\d+ (new_vegas/\S.*?\.nif) \(", line.rstrip())
    if m and 'weapons/' not in m.group(1): paths.append(m.group(1)[len('new_vegas/'):])
print(len(paths), 'meshes to convert')
for p in paths:
    r = subprocess.run([sys.executable, os.path.join(here, 'convert_single_mesh.py'), p], capture_output=True, text=True)
    last = (r.stdout.strip().splitlines() or ['?'])[-1]
    kind = 'OK   ' if r.returncode == 0 else ('ABSENT ' if r.returncode == 2 else 'FAIL ')        # exit 2 = the mesh is not in any Fallout 3 archive either: the original game lacks it too
    print(kind, p, '|', last[:100], flush=True)
