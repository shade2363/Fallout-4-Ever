"""Fetch the third-party tools the build needs, from their official release pages, and verify them against pinned SHA-256 hashes.

  python fetch_tools.py [--workdir DIR] [--from-dir DIR] [--pin] [--only ID]

* builder/tools.lock.json lists every tool: official URL, expected size, expected SHA-256, licence.  A download whose size or hash differs is
  deleted and the build stops (never extracted, never run).
* --from-dir DIR : use files you downloaded yourself (same names) instead of the network; they are verified the same way.
* --pin          : maintainer only: write the hashes of the downloaded files into the lock file (do this once per release, on a trusted machine).
Nothing here touches the Fallout folders; everything goes to the work folder.  No Bethesda files are involved.
"""
import hashlib, json, os, shutil, sys, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK_NAME = 'tools.lock.json'


def lock_path():
    """the pinned tool list: next to this file when run from source; in the exe it is bundled in the payload (builder/), or in an installed signed update"""
    cands = []
    try:
        import updater
        a = updater.active_payload()
        if a:
            cands.append(os.path.join(a, 'builder', LOCK_NAME))
    except Exception:
        pass
    base = getattr(sys, '_MEIPASS', None)
    if base:
        cands += [os.path.join(base, 'payload', 'builder', LOCK_NAME), os.path.join(base, LOCK_NAME)]
    cands.append(os.path.join(HERE, LOCK_NAME))
    for c in cands:
        if os.path.isfile(c):
            return c
    raise RuntimeError('tools.lock.json not found (looked in: %s)' % '; '.join(cands))
CACHE = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'CapitalConvert', 'downloads')


def load_lock():
    with open(lock_path(), encoding='utf-8') as f:
        return json.load(f)['tools']


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _download(url, dst, log, expect_size):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    part = dst + '.part'
    req = urllib.request.Request(url, headers={'User-Agent': 'CapitalConvert-fetch'})
    with urllib.request.urlopen(req, timeout=60) as r, open(part, 'wb') as f:
        total, got, last = int(r.headers.get('Content-Length') or expect_size or 0), 0, -1
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            got += len(b)
            pct = int(100 * got / total) if total else 0
            if pct // 10 != last:
                last = pct // 10
                log('    %d%%  (%d MB)' % (pct, got >> 20))
    os.replace(part, dst)


def _safe_extract_zip(path, dest):
    base = os.path.realpath(dest)
    with zipfile.ZipFile(path) as z:
        for m in z.infolist():
            target = os.path.realpath(os.path.join(dest, m.filename))
            if not (target == base or target.startswith(base + os.sep)):
                raise RuntimeError('unsafe path in archive: %s' % m.filename)
        z.extractall(dest)


def _safe_extract_7z(path, dest):
    import subprocess
    sys32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'tar.exe')
    tar = sys32 if os.path.exists(sys32) else shutil.which('tar')     # not Git's GNU tar (no 7z support); Windows 10+ bsdtar reads 7z incl. the BCJ2 filter xEdit's archive uses (py7zr cannot)
    if tar:
        lst = subprocess.run([tar, '-tf', path], capture_output=True, text=True, creationflags=0x08000000)
        if lst.returncode == 0:
            base = os.path.realpath(dest)
            for n in lst.stdout.splitlines():
                t = os.path.realpath(os.path.join(dest, n))
                if not (t == base or t.startswith(base + os.sep)):
                    raise RuntimeError('unsafe path in archive: %s' % n)
            r = subprocess.run([tar, '-xf', path, '-C', dest], capture_output=True, text=True, creationflags=0x08000000)
            if r.returncode == 0:
                return
    try:
        import py7zr
    except ImportError:
        raise RuntimeError('the 7z extractor (py7zr) is missing; install it with "pip install py7zr" or unpack %s into %s by hand' % (path, dest))
    base = os.path.realpath(dest)
    with py7zr.SevenZipFile(path) as z:
        for n in z.getnames():
            t = os.path.realpath(os.path.join(dest, n))
            if not (t == base or t.startswith(base + os.sep)):
                raise RuntimeError('unsafe path in archive: %s' % n)
        z.extractall(dest)


def _flatten_single_folder(dest):
    kids = os.listdir(dest)
    if len(kids) == 1 and os.path.isdir(os.path.join(dest, kids[0])):
        top = os.path.join(dest, kids[0])
        for n in os.listdir(top):
            shutil.move(os.path.join(top, n), os.path.join(dest, n))
        os.rmdir(top)


def ensure(workdir, log=print, from_dir=None, pin=False, only=None):
    """make sure every tool in the lock file is installed in the work folder; returns the list of tool ids installed now"""
    tools = load_lock()
    marker_path = os.path.join(workdir, 'tool', '.fetched.json')
    marker = json.load(open(marker_path)) if os.path.exists(marker_path) else {}
    done, changed = [], False
    for t in tools:
        if only and t['id'] != only:
            continue
        want = t.get('sha256') or ''
        if marker.get(t['id']) == want and want and all(os.path.exists(os.path.join(workdir, s)) for s in t.get('sentinels', [])):
            log('  %s: already installed (%s)' % (t['id'], t['version']))
            continue
        name = os.path.basename(t['url'])
        src = os.path.join(from_dir, name) if from_dir else os.path.join(CACHE, name)
        if not (os.path.exists(src) and (not want or sha256_file(src) == want)):
            if from_dir:
                raise RuntimeError('%s not found (or hash differs) in %s' % (name, from_dir))
            log('  downloading %s %s (%d MB) from %s' % (t['id'], t['version'], t['size'] >> 20, t['url']))
            _download(t['url'], src, log, t['size'])
        got = sha256_file(src)
        if os.path.getsize(src) != t['size'] and not pin:
            os.remove(src) if not from_dir else None
            raise RuntimeError('%s: size %d differs from the pinned %d: refusing to use it' % (name, os.path.getsize(src), t['size']))
        if pin:
            t['sha256'] = got
            changed = True
            log('  pinned %s = %s' % (t['id'], got))
        elif not want:
            raise RuntimeError('%s has no pinned SHA-256 in tools.lock.json (maintainer: run fetch_tools.py --pin once)' % t['id'])
        elif got != want:
            os.remove(src) if not from_dir else None
            raise RuntimeError('%s: SHA-256 %s does not match the pinned %s: refusing to use it' % (name, got, want))
        dest = os.path.join(workdir, t['dest'])
        os.makedirs(dest, exist_ok=True)
        log('  verified, extracting %s into %s' % (name, dest))
        stage = dest + '.fetch-tmp'
        shutil.rmtree(stage, ignore_errors=True)
        os.makedirs(stage)
        (_safe_extract_zip if name.lower().endswith('.zip') else _safe_extract_7z)(src, stage)
        if t.get('flatten'):
            _flatten_single_folder(stage)
        for root, dirs, files in os.walk(stage):                 # overlay (keeps files the payload put there, e.g. our xEdit scripts)
            rel = os.path.relpath(root, stage)
            os.makedirs(os.path.join(dest, rel), exist_ok=True)
            for f in files:
                shutil.move(os.path.join(root, f), os.path.join(dest, rel, f))
        shutil.rmtree(stage, ignore_errors=True)
        marker[t['id']] = t.get('sha256') or got
        done.append(t['id'])
    if changed:
        with open(lock_path(), encoding='utf-8') as f:
            data = json.load(f)
        for t in data['tools']:
            for u in tools:
                if u['id'] == t['id']:
                    t['sha256'] = u.get('sha256', '')
        with open(lock_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=1)
    os.makedirs(os.path.dirname(marker_path), exist_ok=True)
    json.dump(marker, open(marker_path, 'w'), indent=1)
    return done


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--workdir', default=os.path.join(os.environ.get('LOCALAPPDATA') or '.', 'CapitalBuild'))
    ap.add_argument('--from-dir')
    ap.add_argument('--pin', action='store_true')
    ap.add_argument('--only')
    a = ap.parse_args()
    ensure(a.workdir, from_dir=a.from_dir, pin=a.pin, only=a.only)
