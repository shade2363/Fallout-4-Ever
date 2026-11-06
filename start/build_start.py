"""Fallout 4-Ever: build the New Game start (CapitalStart.esp + two compiled scripts).

New Game -> the player is moved to the spot right outside Vault 101, has a Pip-Boy, and the quest "Escape!" is already completed in the Pip-Boy; then the character
editor and the SPECIAL screen open.  The only inputs from your games: the converted Fallout3.esm (to check that the spawn point exists) and your Fallout 4 Papyrus compiler.

  python start/build_start.py --conv <converted Fallout3.esm> --fo4 <Fallout 4 folder> --out <CapitalStart.esp> --src <script source folder> --scripts-out <pex folder>

Plugin: CapitalStart.esp, masters Fallout4.esm + Fallout3.esm: quest CapitalStartDemo (Start Game Enabled, script CapStartDemo) and quest CapitalEscape ("Escape!").
Scripts: CapStartDemo.pex and Fragments\\Quests\\QF_MQ101_0001ED86.pex (replaces the vanilla intro fragment; removed again by the uninstall).
"""
import argparse, os, re, struct, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'navmesh'))
from navlib import iter_records, sub, record, group

EXIT_LOCAL = 0x0ACD96          # Fallout3.esm placed reference "CG04SunBlindDummy" in the cell Vault101Exterior: the spot where the player steps out of the vault
EXIT_CELL = 0x10010C1          # (Fallout3.esm is master 1 of the converted plugin)
PIPBOY = 0x00021B3B            # Fallout4.esm Pip-Boy
START_ID, ESC_ID = 0x800, 0x801
MASTERS = ['Fallout4.esm', 'Fallout3.esm']
OWN = len(MASTERS)


def zs(b):
    return b.rstrip(bytes(1)) + bytes(1)


def vmad(script):
    return struct.pack('<HHH', 6, 2, 1) + struct.pack('<H', len(script)) + script.encode() + bytes([0]) + struct.pack('<H', 0)


def check_spawn_point(conv):
    want = (1 << 24) | EXIT_LOCAL
    with open(conv, 'rb') as f:
        d = f.read()
    for r in iter_records(d):
        if r.sig == 'REFR' and r.fid == want:
            return True
    return False


def build_plugin(out):
    flt = sub('FLTR', b'CapitalConvert' + bytes([92]) + bytes(1))
    start = record('QUST', (OWN << 24) | START_ID, [sub('EDID', zs(b'CapitalStartDemo')), sub('VMAD', vmad('CapStartDemo')),
                   sub('DNAM', struct.pack('<HBBIi', 0x0011, 50, 0, 0, 0)), flt, sub('NEXT', b''), sub('ANAM', struct.pack('<I', 0))], ver=131)
    esc = record('QUST', (OWN << 24) | ESC_ID, [sub('EDID', zs(b'CapitalEscape')), sub('FULL', zs(b'Escape!')),
                 sub('DNAM', struct.pack('<HBBIi', 0x0010, 50, 0, 0, 0)), flt, sub('NEXT', b''),
                 sub('INDX', struct.pack('<HBB', 10, 0, 0)), sub('QSDT', bytes([0])), sub('NAM2', zs(b'You made it out of Vault 101.')),
                 sub('QOBJ', struct.pack('<H', 10)), sub('FNAM', struct.pack('<I', 0)), sub('NNAM', zs(b'Escape from Vault 101')),
                 sub('ANAM', struct.pack('<I', 0))], ver=131)
    hs = [sub('HEDR', struct.pack('<fII', 1.0, 2, 0x802)), sub('CNAM', b'CapitalConvert' + bytes(1))]
    for m in MASTERS:
        hs += [sub('MAST', m.encode() + bytes(1)), sub('DATA', bytes(8))]
    with open(out, 'wb') as f:
        f.write(record('TES4', 0, hs, ver=131) + group(b'QUST', 0, start + esc))


def write_sources(src):
    subs = {'@EXIT@': str(EXIT_LOCAL), '@QSTART@': str(START_ID), '@QESC@': str(ESC_ID), '@PIPBOY@': str(PIPBOY)}
    out = {}
    for name, rel in (('CapStartDemo.psc.tmpl', 'CapStartDemo.psc'), ('QF_MQ101_0001ED86.psc.tmpl', os.path.join('Fragments', 'Quests', 'QF_MQ101_0001ED86.psc'))):
        with open(os.path.join(HERE, name), encoding='utf-8') as f:
            t = f.read()
        for k, v in subs.items():
            t = t.replace(k, v)
        left = re.findall(r'@[A-Z0-9]+@', t)
        if left:
            raise SystemExit('unfilled placeholders in %s: %s' % (name, left))
        p = os.path.join(src, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(t)
        out[name] = p
    return out


def find_base(fo4, scratch):
    """(folder with the game's own script sources, path of the compiler flags file). The Creation Kit unpacks the sources into Data/Scripts/Source/Base; when only
    Base.zip is there (not unpacked yet) it is unpacked into our own scratch folder, never into the game folder"""
    srcdir = os.path.join(fo4, 'Data', 'Scripts', 'Source')
    base = os.path.join(srcdir, 'Base')
    flags = os.path.join(base, 'Institute_Papyrus_Flags.flg')
    if os.path.isfile(os.path.join(base, 'Game.psc')) and os.path.isfile(flags):
        return base, flags
    for z in (os.path.join(base, 'Base.zip'), os.path.join(srcdir, 'Base.zip')):
        if os.path.isfile(z):
            dest = os.path.join(scratch, '_base')
            os.makedirs(dest, exist_ok=True)
            root = os.path.realpath(dest)
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    t = os.path.realpath(os.path.join(dest, n))
                    if not (t == root or t.startswith(root + os.sep)):
                        raise SystemExit('unsafe path in %s' % z)
                zf.extractall(dest)
            if os.path.isfile(os.path.join(dest, 'Game.psc')) and os.path.isfile(os.path.join(dest, 'Institute_Papyrus_Flags.flg')):
                return dest, os.path.join(dest, 'Institute_Papyrus_Flags.flg')
    raise SystemExit('the Fallout 4 script sources were not found (%s). Install the free "Fallout 4 Creation Kit" from Steam, start it once, and run this again.' % base)


def compile_all(fo4, src, pex_out, files):
    compiler = os.path.join(fo4, 'Papyrus Compiler', 'PapyrusCompiler.exe')
    if not os.path.exists(compiler):
        raise SystemExit('Fallout 4 Creation Kit file missing: %s (install the free "Fallout 4 Creation Kit" from Steam)' % compiler)
    base, flags = find_base(fo4, os.path.join(os.path.dirname(os.path.abspath(src)), '_work'))
    os.makedirs(pex_out, exist_ok=True)
    for name in ('CapStartDemo.psc.tmpl', 'QF_MQ101_0001ED86.psc.tmpl'):          # the quest script first: the fragment refers to its type
        r = subprocess.run([compiler, os.path.relpath(files[name], src), '-f=' + flags, '-i=%s;%s' % (src, base), '-o=' + pex_out], capture_output=True, text=True, encoding='utf-8',
                           errors='replace', cwd=os.path.dirname(compiler), creationflags=0x08000000 if os.name == 'nt' else 0)
        text = r.stdout + r.stderr
        if 'Compilation succeeded' not in text and r.returncode:
            raise SystemExit('compile failed for %s:\n%s' % (name, text[-1500:]))
        if 'error' in text.lower() and 'Compilation succeeded' not in text:
            raise SystemExit('compile failed for %s:\n%s' % (name, text[-1500:]))
        print('compiled', os.path.basename(files[name]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--conv', required=True)
    ap.add_argument('--fo4', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--src', required=True)
    ap.add_argument('--scripts-out', required=True)
    a = ap.parse_args()
    if not check_spawn_point(a.conv):
        raise SystemExit('the spawn point (Fallout3.esm reference %08X) is not in %s: the world conversion did not finish, or this is not the Fallout 3 GOTY data' % ((1 << 24) | EXIT_LOCAL, a.conv))
    print('spawn point found: Fallout3.esm %06X (outside Vault 101)' % EXIT_LOCAL)
    files = write_sources(a.src)
    compile_all(a.fo4, a.src, a.scripts_out, files)
    for rel in ('CapStartDemo.pex', os.path.join('Fragments', 'Quests', 'QF_MQ101_0001ED86.pex')):
        if not os.path.isfile(os.path.join(a.scripts_out, rel)):
            raise SystemExit('missing compiled script %s' % rel)
    with open(os.path.join(a.scripts_out, 'Fragments', 'Quests', 'QF_MQ101_0001ED86.pex'), 'rb') as f:
        frag = f.read()
    if b'F4EVER' not in frag or b'Fade the game in' in frag:
        raise SystemExit('the compiled intro fragment is not ours (the compiler picked up the original game script): refusing to install it')
    build_plugin(a.out)
    print('wrote', a.out)


main()
