"""Update check / install / rollback for the pipeline scripts (the "payload").

Release layout on GitHub (tag vX.Y.Z), all uploaded as release assets:
    manifest.json        version, notes, save_compat, min_app_version, payload {name, size, sha256}
    manifest.sig         Ed25519 signature (raw bytes, hex text) over the exact bytes of manifest.json, made with the maintainer's private key
    CapitalPayload-X.Y.Z.zip   our scripts only (no game files, no third-party programs)
What is trusted: only a manifest whose signature verifies against builder/update_key.py.  The payload zip must then match the signed size + SHA-256.
Nothing is ever executed from the download: files are unpacked into %LOCALAPPDATA%\\CapitalConvert\\updates\\<version>\\payload and used by the next build.
Network use happens ONLY when the user asks (Check for updates).  HTTPS to api.github.com / github.com only (override: CAPITAL_UPDATE_URL, for tests).
"""
import hashlib, json, os, shutil, time, urllib.error, urllib.request, zipfile

from version import VERSION, UPDATE_REPO
import update_key

APPDATA = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'CapitalConvert')
UPDATES = os.path.join(APPDATA, 'updates')
ACTIVE = os.path.join(UPDATES, 'active.json')
KEEP = 3                                         # installed payload versions kept for rollback
SAVE_COMPAT = {'save-safe': 'Safe for existing saves.',
               'needs-new-save': 'Existing saves may break: start a new save after updating.',
               'needs-new-game': 'Existing saves will NOT work: start a new game after updating.'}
MAX_MANIFEST = 256 * 1024
MAX_PAYLOAD = 400 * 1024 * 1024


class UpdateError(Exception):
    pass


def parse_version(s):
    try:
        return tuple(int(x) for x in str(s).strip().lstrip('v').split('.'))
    except ValueError:
        raise UpdateError('bad version string: %r' % (s,))


def _allowed(url, override):
    if url.startswith('https://api.github.com/') or url.startswith('https://github.com/') or url.startswith('https://objects.githubusercontent.com/'):
        return True
    return bool(override) and url.startswith(override.rstrip('/'))


def _get(url, limit, override=None):
    if not _allowed(url, override):
        raise UpdateError('refusing to download from %s' % url)
    req = urllib.request.Request(url, headers={'User-Agent': 'CapitalConvert-updater', 'Accept': 'application/octet-stream, application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read(limit + 1)
    except (urllib.error.URLError, OSError, ValueError) as e:       # offline, DNS, firewall, 404 ...: a plain message, not a traceback
        raise UpdateError('could not reach the update server (%s). Check your internet connection and try again.' % (getattr(e, 'reason', None) or e))
    if len(data) > limit:
        raise UpdateError('download larger than the allowed %d bytes: %s' % (limit, url))
    return data


def verify_signature(manifest_bytes, sig_text, public_key_hex=None):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex or update_key.PUBLIC_KEY_HEX))
        pub.verify(bytes.fromhex(sig_text.strip().decode() if isinstance(sig_text, bytes) else sig_text.strip()), manifest_bytes)
    except (InvalidSignature, ValueError):
        raise UpdateError('the update manifest signature is NOT valid: refusing it')


def _read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _write_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1)


def active_info():
    try:
        return _read_json(ACTIVE)
    except (OSError, ValueError):
        return None


def current_payload_version():
    a = active_info()
    return a['version'] if a else VERSION


def active_payload():
    """folder of the installed update's payload, or None to use the payload bundled in the exe"""
    a = active_info()
    if a and os.path.isdir(a.get('dir', '')):
        try:
            if parse_version(a['version']) > parse_version(VERSION) and parse_version(a.get('min_app_version', '0')) <= parse_version(VERSION):
                return a['dir']
        except UpdateError:
            pass
    return None


def installed_versions():
    out = []
    if os.path.isdir(UPDATES):
        for n in os.listdir(UPDATES):
            if os.path.isfile(os.path.join(UPDATES, n, 'payload.json')):
                out.append(n)
    return sorted(out, key=parse_version)


def check(source=None, repo=None):
    """ask the release page for the newest signed manifest; returns a dict (never installs anything)"""
    source = source if source is not None else os.environ.get('CAPITAL_UPDATE_URL')
    if source:
        base = source.rstrip('/')
        urls = {'manifest.json': base + '/manifest.json', 'manifest.sig': base + '/manifest.sig'}
        payload_base = base
    else:
        rel = json.loads(_get('https://api.github.com/repos/%s/releases/latest' % (repo or UPDATE_REPO), MAX_MANIFEST * 8))
        urls = {a['name']: a['browser_download_url'] for a in rel.get('assets', [])}
        if 'manifest.json' not in urls or 'manifest.sig' not in urls:
            raise UpdateError('the latest release has no signed manifest')
        payload_base = None
    mbytes = _get(urls['manifest.json'], MAX_MANIFEST, source)
    verify_signature(mbytes, _get(urls['manifest.sig'], 4096, source))
    m = json.loads(mbytes.decode('utf-8'))
    cur = parse_version(current_payload_version())
    newer = parse_version(m['version']) > cur
    app_too_old = parse_version(m.get('min_app_version', '0')) > parse_version(VERSION)
    pname = m['payload']['name']
    purl = urls.get(pname) or ((payload_base + '/' + pname) if payload_base else None)
    return {'current': current_payload_version(), 'app': VERSION, 'latest': m['version'], 'newer': newer, 'app_too_old': app_too_old, 'manifest': m,
            'payload_url': purl, 'source': source, 'notes': m.get('notes', ''), 'save_compat': m.get('save_compat', 'save-safe'),
            'save_text': SAVE_COMPAT.get(m.get('save_compat', 'save-safe'), '')}


def _unzip_safe(zpath, dest):
    base = os.path.realpath(dest)
    with zipfile.ZipFile(zpath) as z:
        for i in z.infolist():
            t = os.path.realpath(os.path.join(dest, i.filename))
            if not (t == base or t.startswith(base + os.sep)):
                raise UpdateError('unsafe path in the update package: %s' % i.filename)
            if os.path.splitext(i.filename)[1].lower() in ('.exe', '.dll', '.esm', '.esp', '.ba2', '.bsa', '.nif', '.dds'):
                raise UpdateError('the update package contains a file type that is never allowed: %s' % i.filename)
        z.extractall(dest)


def apply(info, log=print):
    """download + verify + unpack the payload of a check() result, then make it the active payload; the previous one stays for rollback"""
    if not info['newer']:
        raise UpdateError('nothing newer to install')
    if info['app_too_old']:
        raise UpdateError('this update needs a newer installer (version %s or later): download the new release instead' % info['manifest'].get('min_app_version'))
    m = info['manifest']['payload']
    if not info.get('payload_url'):
        raise UpdateError('no download address for the update package')
    log('downloading %s (%d KB)' % (m['name'], m['size'] // 1024))
    data = _get(info['payload_url'], min(m['size'] + 1024, MAX_PAYLOAD), info.get('source'))
    if len(data) != m['size']:
        raise UpdateError('update package size %d differs from the signed %d: refusing it' % (len(data), m['size']))
    if hashlib.sha256(data).hexdigest() != m['sha256']:
        raise UpdateError('update package SHA-256 differs from the signed value: refusing it')
    ver = info['latest']
    os.makedirs(UPDATES, exist_ok=True)
    tmp = os.path.join(UPDATES, '.incoming-%d' % os.getpid())
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    zp = os.path.join(tmp, 'p.zip')
    with open(zp, 'wb') as f:
        f.write(data)
    try:
        _unzip_safe(zp, os.path.join(tmp, 'payload'))
        os.remove(zp)
        meta = {'version': ver, 'installed': time.strftime('%Y-%m-%d %H:%M:%S'), 'notes': info['notes'], 'save_compat': info['save_compat'],
                'min_app_version': info['manifest'].get('min_app_version', '0'), 'sha256': m['sha256']}
        _write_json(os.path.join(tmp, 'payload.json'), meta)
        final = os.path.join(UPDATES, ver)
        shutil.rmtree(final, ignore_errors=True)
        os.replace(tmp, final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    prev = active_info()
    _write_json(ACTIVE, {'version': ver, 'dir': os.path.join(final, 'payload'), 'min_app_version': meta['min_app_version'], 'previous': prev['version'] if prev else None})
    for old in installed_versions()[:-KEEP]:
        shutil.rmtree(os.path.join(UPDATES, old), ignore_errors=True)
    log('update %s installed (%s). Run the build again: only the stages whose scripts changed will re-run.' % (ver, info['save_text']))
    return ver


def rollback(log=print):
    """go back to the previous installed payload version (or the payload bundled in the exe)"""
    a = active_info()
    if not a:
        raise UpdateError('no update is installed: nothing to roll back')
    vers = [v for v in installed_versions() if v != a['version']]
    older = [v for v in vers if parse_version(v) < parse_version(a['version'])]
    if older and parse_version(older[-1]) > parse_version(VERSION):
        v = older[-1]
        meta = _read_json(os.path.join(UPDATES, v, 'payload.json'))
        _write_json(ACTIVE, {'version': v, 'dir': os.path.join(UPDATES, v, 'payload'), 'min_app_version': meta.get('min_app_version', '0'), 'previous': None})
        log('rolled back to payload %s' % v)
        return v
    os.remove(ACTIVE)
    log('rolled back to the payload bundled with the exe (%s)' % VERSION)
    return VERSION
