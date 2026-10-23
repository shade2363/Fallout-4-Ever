"""Make a signed release folder (never uploads anything).

  python tools/release.py [--version X.Y.Z] [--notes "text" | --notes-file F] [--save-compat save-safe|needs-new-save|needs-new-game]
                          [--min-app X.Y.Z] [--key PRIVATE_KEY_FILE] [--out DIR] [--no-build]

1. builds the exe + payload (builder/make_exe.py) unless --no-build
2. runs the leak scan on dist\\CapitalConvert (blocks the release on any finding)
3. dist\\release\\vX.Y.Z\\ gets: CapitalConvert-X.Y.Z.zip (full install), CapitalPayload-X.Y.Z.zip (update package), manifest.json, manifest.sig, SHA256SUMS.txt
4. prints the gh command to publish them as a GitHub Release (you run it yourself, after reading the checklist in docs/RELEASE-CHECKLIST.md)
"""
import argparse, hashlib, json, os, subprocess, sys, time, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'builder'))


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def zip_dir(src, dst, prefix=''):
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in sorted(files):
                if f.endswith('.pyc'):
                    continue
                p = os.path.join(root, f)
                z.write(p, (prefix + os.path.relpath(p, src)).replace(os.sep, '/'))


def find_signtool():
    import glob, shutil
    hit = shutil.which('signtool')
    if hit:
        return hit
    kits = r'C:\Program Files (x86)\Windows Kits\10'
    c = sorted(glob.glob(kits + r'\bin\*\x64\signtool.exe')) or glob.glob(kits + r'\App Certification Kit\signtool.exe')
    return c[-1] if c else None


def authenticode_sign(exe, thumbprint=None, pfx=None, pfx_password_env='CAPITAL_PFX_PASSWORD', timestamp_url='http://timestamp.digicert.com', require_trusted=False):
    """Authenticode-sign the exe with signtool (SHA-256 + RFC 3161 timestamp) and verify it; raises SystemExit on any failure"""
    st = find_signtool()
    if not st:
        raise SystemExit('signtool.exe not found (install the Windows SDK "Signing Tools")')
    cmd = [st, 'sign', '/fd', 'SHA256'] + (['/tr', timestamp_url, '/td', 'SHA256'] if timestamp_url else []) + ['/d', 'Fallout 4-Ever', '/du', 'https://github.com/shade2363/Fallout-4-Ever']
    if pfx:
        cmd += ['/f', pfx]
        if os.environ.get(pfx_password_env):
            cmd += ['/p', os.environ[pfx_password_env]]
    elif thumbprint:
        cmd += ['/sha1', thumbprint]
    else:
        cmd += ['/a']
    cmd.append(exe)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('signing FAILED: ' + r.stdout[-800:] + ' ' + r.stderr[-800:])
    v = subprocess.run(['powershell', '-NoProfile', '-Command', "(Get-AuthenticodeSignature '%s').Status" % exe], capture_output=True, text=True).stdout.strip()
    print('signed %s: signature status %s' % (os.path.basename(exe), v))
    if require_trusted and v != 'Valid':
        raise SystemExit('the signature is %s, not Valid (not issued by a trusted authority)' % v)
    return v


def make_release(version, notes, save_compat, min_app, key_path, out_dir, app_dir, run_scan=True, sign=None):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    payload = os.path.join(app_dir, '_internal', 'payload')
    if not os.path.isdir(payload):
        raise SystemExit('no payload folder at %s (run builder/make_exe.py first)' % payload)
    if run_scan:
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'leak_scan.py'), app_dir], capture_output=True, text=True)
        sys.stdout.write(r.stdout[-1500:])
        if r.returncode:
            raise SystemExit('LEAK SCAN FAILED: the release is blocked')
    if sign:
        authenticode_sign(os.path.join(app_dir, 'CapitalConvert.exe'), **sign)
    rel = os.path.join(out_dir, 'v' + version)
    os.makedirs(rel, exist_ok=True)
    pz = os.path.join(rel, 'CapitalPayload-%s.zip' % version)
    zip_dir(payload, pz)
    full = os.path.join(rel, 'CapitalConvert-%s.zip' % version)
    zip_dir(app_dir, full, 'CapitalConvert/')
    manifest = {'version': version, 'released': time.strftime('%Y-%m-%d'), 'notes': notes, 'save_compat': save_compat, 'min_app_version': min_app,
                'payload': {'name': os.path.basename(pz), 'size': os.path.getsize(pz), 'sha256': sha256_file(pz)}}
    mb = (json.dumps(manifest, indent=1, sort_keys=True) + '\n').encode('utf-8')
    open(os.path.join(rel, 'manifest.json'), 'wb').write(mb)
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(open(key_path, 'rb').read().decode().strip()))
    with open(os.path.join(rel, 'manifest.sig'), 'w', newline=chr(10)) as f:
        f.write(key.sign(mb).hex())
    with open(os.path.join(rel, 'SHA256SUMS.txt'), 'w', newline=chr(10)) as f:
        for n in sorted(os.listdir(rel)):
            if n != 'SHA256SUMS.txt':
                f.write('%s  %s\n' % (sha256_file(os.path.join(rel, n)), n))
    return rel


if __name__ == '__main__':
    import version as V
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default=V.VERSION)
    ap.add_argument('--notes', default='')
    ap.add_argument('--notes-file')
    ap.add_argument('--save-compat', default='save-safe', choices=['save-safe', 'needs-new-save', 'needs-new-game'])
    ap.add_argument('--min-app', default=V.VERSION)
    ap.add_argument('--key', default=os.path.join(os.path.expanduser('~'), 'CapitalConvert-signing', 'release-private.key'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist', 'release'))
    ap.add_argument('--no-build', action='store_true')
    ap.add_argument('--sign-thumbprint', help='sign CapitalConvert.exe with the code-signing certificate with this SHA-1 thumbprint (certificate store)')
    ap.add_argument('--sign-pfx', help='sign with this .pfx file (password in the environment variable CAPITAL_PFX_PASSWORD)')
    ap.add_argument('--timestamp-url', default='http://timestamp.digicert.com')
    ap.add_argument('--require-trusted', action='store_true', help='fail unless Windows reports the signature as Valid (a real, trusted certificate)')
    a = ap.parse_args()
    notes = open(a.notes_file, encoding='utf-8').read() if a.notes_file else a.notes
    if not a.no_build:
        subprocess.check_call([sys.executable, os.path.join(ROOT, 'builder', 'make_exe.py')], cwd=ROOT)
    sign = {'thumbprint': a.sign_thumbprint, 'pfx': a.sign_pfx, 'timestamp_url': a.timestamp_url, 'require_trusted': a.require_trusted} if (a.sign_thumbprint or a.sign_pfx) else None
    rel = make_release(a.version, notes, a.save_compat, a.min_app, a.key, a.out, os.path.join(ROOT, 'dist', 'CapitalConvert'), sign=sign)
    print('\nrelease folder:', rel)
    for n in sorted(os.listdir(rel)):
        print('  %-34s %8.1f MB' % (n, os.path.getsize(os.path.join(rel, n)) / 1048576))
    print('\nPublish (after the checklist) with:\n  gh release create v%s "%s\\*" --repo shade2363/Fallout-4-Ever --title "Fallout 4-Ever %s" --notes-file <notes>' % (a.version, rel, a.version))
