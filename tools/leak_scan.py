"""Release gate: fail (exit 1) if the repo or a built package contains anything that must not be distributed.

  python tools/leak_scan.py [PATH ...]            (default: this repo; pass a zip/exe-folder to scan a package)
  python tools/leak_scan.py --hashes private.txt   (optional: one SHA-256 per line of the maintainer's own game files, kept OUT of the repo)

Checks: forbidden file types (Bethesda formats, compiled scripts, executables of third parties), files over 2 MB, personal / machine strings,
hard-coded drive paths, FO3 data dumps (lines that look like record counts / dialogue exports), and exact hashes of the maintainer's game files.
"""
import argparse, hashlib, json, os, re, sys, zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORBID_EXT = {'.esm', '.esp', '.esl', '.ba2', '.bsa', '.nif', '.dds', '.tga', '.ogg', '.wav', '.fuz', '.xwm', '.lip', '.bik', '.bk2', '.swf',
              '.hkx', '.kf', '.pex', '.bgsm', '.bgem', '.egm', '.egt', '.tri', '.btr', '.bto', '.btd', '.lod'}
THIRD_PARTY_EXE = {'papyruscompiler.exe', 'papyrusassembler.exe', 'pcompiler.dll', 'archive2.exe', 'elrich.exe', 'xfoedit.exe', 'xfoedit64.exe',
                   'xdump.exe', 'xdump64.exe', 'bsarch.exe', 'bsarch64.exe', 'f4se_loader.exe', 'xconvert.exe'}
def _local_private():
    """your own private strings (user name, e-mail words, folder names) live in publish/local/config.json, which is git-ignored: none are written in this file"""
    try:
        with open(os.path.join(HERE, 'publish', 'local', 'config.json'), encoding='utf-8') as f:
            return [re.escape(x) for x in json.load(f).get('private_strings', []) if x]
    except (OSError, ValueError):
        return []


PERSONAL = ['C:[\\\\/]+Users[\\\\/]+(?!Public|<|%|\\{|\\*)\\w+'] + _local_private()
DUMP = re.compile(r'^(?:[A-Z]{4}\s+\d{2,}\s*$|File:\s+\w+\.es[mp]\s+total=)', re.M)
BIG = 2 * 1024 * 1024
TEXT_EXT = {'.py', '.ps1', '.psc', '.pas', '.md', '.txt', '.json', '.ini', '.cfg', '.bat', '.cmd', '.csv', '.tsv', '.xml', '.yml', '.yaml', '.toml', '.tmpl'}
SKIP_FILES = {'leak_scan.py', 'sync_from_dev.py'}           # these name the strings they look for


def repo_files():
    """what git would commit (tracked + untracked, minus ignored): the local-only picture is ignored, so it is not a leak here"""
    import subprocess
    out = subprocess.run(['git', '-C', HERE, 'ls-files', '-co', '--exclude-standard'], capture_output=True, text=True).stdout.splitlines()
    return [os.path.join(HERE, f) for f in out if os.path.isfile(os.path.join(HERE, f))]


def iter_files(paths):
    if paths == [HERE]:
        paths = repo_files()
    for p in paths:
        if os.path.isdir(p):
            for r, ds, fs in os.walk(p):
                ds[:] = [d for d in ds if d != '.git']
                for f in fs:
                    yield os.path.join(r, f), None
        elif zipfile.is_zipfile(p):
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if not n.endswith('/'):
                        yield p + '!' + n, z.read(n)
        else:
            yield p, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--hashes')
    a = ap.parse_args()
    bad = set(l.strip().lower() for l in open(a.hashes)) if a.hashes else set()
    problems, n = [], 0
    for path, data in iter_files(a.paths or [HERE]):
        n += 1
        name = os.path.basename(path.split('!')[-1])
        ext = os.path.splitext(name)[1].lower()
        if data is None:
            try:
                data = open(path, 'rb').read()
            except OSError as e:
                problems.append((path, 'unreadable: %s' % e)); continue
        if re.search(r'assets[\\/]+local', path, re.I):
            problems.append((path, 'local-only art folder (personal pictures, e.g. Vault Boy) must never be committed or packaged'))
        if ext in FORBID_EXT:
            problems.append((path, 'forbidden file type %s' % ext))
        if name.lower() in THIRD_PARTY_EXE:
            problems.append((path, 'third-party / Bethesda program must not be bundled'))
        runtime = bool(re.search(r'_internal[\\/](?!payload)', path)) or name == 'CapitalConvert.exe'     # Python / Pillow runtime of the packaged exe
        if len(data) > BIG and not runtime:
            problems.append((path, 'larger than 2 MB (%d bytes)' % len(data)))
        if bad and hashlib.sha256(data).hexdigest() in bad:
            problems.append((path, 'IDENTICAL to a maintainer game file'))
        if name in SKIP_FILES or (ext not in TEXT_EXT and b'\0' in data[:4096]):
            continue
        txt = data.decode('utf-8', errors='replace')
        for rx in PERSONAL:
            m = re.search(rx, txt, re.I)
            if m:
                problems.append((path, 'personal/machine string %r (line %d)' % (m.group(0), txt[:m.start()].count('\n') + 1)))
        if DUMP.search(txt):
            problems.append((path, 'looks like a dump of Fallout 3 data'))
    for p, why in problems:
        print('FAIL %s: %s' % (os.path.relpath(p, HERE) if p.startswith(HERE) else p, why))
    print('%d files scanned, %d problem(s)' % (n, len(problems)))
    sys.exit(1 if problems else 0)


main()
