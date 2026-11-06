r"""FO3 interior colour grade: every converted interior cell pointed at ONE vanilla FO4 image space (0x1A65F2 DefaultInterior_ClearDAWN_E, with FO4's LUT), so
Moriarty's amber, the vault teal, the metro / cave grades of Fallout 3 were all gone.

1. Each FO3 image space used by a cell (CELL XCIM) is rewritten at its converted FormID: FO4's working default-interior HDR / DOF (the converted HDR values are not usable,
   auto exposure 0), no LUT, and FO3's cinematic saturation / brightness / contrast + tint (look/fo3imgs.py, all three FO3 DNAM layouts).
2. Every interior CELL in every plugin that carries the cell (the esms AND the cell copies in CapitalActors / CapitalNavmesh / CapitalCorpses ...) gets XCIM = its FO3 image space.
   Cells without an FO3 XCIM keep FO4's default (FO3's DefaultImageSpaceInterior is neutral).
In place on tool\output (backup lab\look-backup-<stamp>), idempotent.
  python look/build_interior_grade.py [--dry]"""
import collections, os, shutil, struct, sys, time
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/navmesh')
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/look')
sys.path.insert(0, 'X:/__CAPITAL_WORKDIR__/actors')
from navlib import iter_records, subrecords, plugin_header
from esp_rewrite import rebuild
import fo3imgs

R = 'X:/__CAPITAL_WORKDIR__/'
OUT = R + 'tool/output/'
FO3D = 'X:/__CAPITAL_FO3_DATA__/'
FO4D = 'X:/__CAPITAL_FO4__/Data/'
SRC = ['Fallout3.esm', 'Anchorage.esm', 'ThePitt.esm', 'BrokenSteel.esm', 'PointLookout.esm', 'Zeta.esm']
TARGETS = SRC + ['CapitalActors.esp', 'CapitalNavmesh.esp', 'CapitalNavmeshDLC.esp', 'CapitalCorpses.esp', 'CapitalDLCActors.esp']
VAN_INTERIOR = 0x1A65F2
dry = '--dry' in sys.argv
# FO4's image-space tint reads much weaker than FO3's (live test in Moriarty's Saloon 2026-10-28: amount 0.5 stayed teal-green, 0.75 olive, 0.9 monochrome sepia; FO3 shows warm brown):
# boost the amount toward 1:  amount' = 1 - (1 - amount) * TINT_K  (0.5 -> 0.82)
TINT_K = float(os.environ.get('TINT_K', '0.36'))

fo4 = open(FO4D + 'Fallout4.esm', 'rb').read()
van = next(list(subrecords(fo4, r)) for r in iter_records(fo4) if r.sig == 'IMGS' and r.fid == VAN_INTERIOR); del fo4


def names_of(data, own):
    m = plugin_header(data)[0]; return m + [own]


# ---- FO3 truth: (plugin, id24) of a cell -> (plugin, id24) of its image space; image space grades
cell_imgs = {}; grades = {}; edids = {}
for p in SRC:
    d = open(FO3D + p, 'rb').read(); nm = names_of(d, p)
    key = lambda fid: (nm[fid >> 24].lower(), fid & 0xFFFFFF)
    for r in iter_records(d):
        if r.sig == 'IMGS':
            s = dict(subrecords(d, r)); g = fo3imgs.grade(s.get('DNAM', b''))
            if g: grades[key(r.fid)] = g; edids[key(r.fid)] = s.get('EDID', b'').rstrip(b'\0').decode()
        elif r.sig == 'CELL':
            s = dict(subrecords(d, r))
            if 'XCIM' in s: cell_imgs[key(r.fid)] = key(struct.unpack('<I', s['XCIM'])[0])
    del d
used = collections.Counter(cell_imgs.values())
print('FO3 cells with an image space:', len(cell_imgs), ' image spaces used:', len(used))

stamp = time.strftime('%Y%m%d-%H%M'); bk = R + 'lab/look-backup-' + stamp
report = collections.Counter()
for p in TARGETS:
    path = OUT + p
    if not os.path.isfile(path):                      # the demo does not build CapitalNavmeshDLC / CapitalCorpses / CapitalDLCActors
        print('skipping %s: not part of this build' % p); continue
    d = open(path, 'rb').read(); nm = [x.lower() for x in names_of(d, p)]
    idx = {n: i for i, n in enumerate(nm)}
    key = lambda fid: (nm[fid >> 24], fid & 0xFFFFFF) if (fid >> 24) < len(nm) else None
    edits = {}
    # 1. image spaces defined in this plugin that FO3 cells use
    for r in iter_records(d):
        if r.sig == 'IMGS' and (r.fid >> 24) == len(nm) - 1:
            k = key(r.fid)
            if k in used and k in grades:
                g = grades[k]; ed = edids[k]
                def fn(subs, g=g, ed=ed):
                    out = []
                    for sg, v in van:
                        if sg.startswith('TX'): continue                      # FO4 LUT = FO4's grade
                        if sg == 'EDID': v = ed.encode() + b'\0'
                        elif sg == 'CNAM': v = struct.pack('<3f', g['sat'], g['bright'], g['contrast'])
                        elif sg == 'TNAM': v = struct.pack('<4f', 1 - (1 - g['tint_amt']) * TINT_K, *g['tint'])
                        out.append((sg.encode(), v))
                    return out
                edits[r.fid] = fn; report[p + ' image spaces'] += 1
    # 2. interior cells -> their FO3 image space
    for r in iter_records(d):
        if r.sig != 'CELL': continue
        s = dict(subrecords(d, r))
        if not (s.get('DATA', b'\0')[0] & 1) or 'XCIM' not in s: continue
        want = cell_imgs.get(key(r.fid))
        if not want or want[0] not in idx: report[p + ' cells without FO3 grade'] += 1; continue
        new = (idx[want[0]] << 24) | want[1]
        if struct.unpack('<I', s['XCIM'])[0] == new: report[p + ' cells already graded'] += 1; continue
        edits[r.fid] = (lambda n: (lambda subs: [(k, struct.pack('<I', n)) if k == b'XCIM' else (k, v) for k, v in subs]))(new)
        report[p + ' cells regraded'] += 1
    if edits and not dry:
        os.makedirs(bk, exist_ok=True)
        if not os.path.exists(bk + '/' + p): shutil.copy(path, bk + '/' + p)
        open(path, 'wb').write(rebuild(d, edits, {b'CELL', b'IMGS'}))
    del d
for k in sorted(report): print('%-48s %d' % (k, report[k]))
print('backup:', bk if not dry else '(dry run)')
