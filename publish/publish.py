"""The ONLY supported way to put this project on GitHub.  It cannot push anything that has not passed the gate.

  python publish/publish.py setup            create publish/local/config.json (your private settings; git-ignored) and install the push guard
  python publish/publish.py check            gate: scan the committed tree (what would be public) for personal data, secrets, game files, forbidden files
  python publish/publish.py snapshot -m MSG  gate, then make/extend the local branch `public`: a clean commit of the current tree under your no-reply identity
  python publish/publish.py push [--yes]     gate again on the whole public history, then push `public` to the GitHub repo's main branch (asks you to confirm)
  python publish/publish.py release X.Y.Z    verify dist/release/vX.Y.Z (hashes, signature, contents), then create the GitHub release (asks you to confirm)
  python publish/publish.py status           what is local, what is public, what the guard allows

Why a separate `public` branch: your working branch (`main`) keeps the full local history, which may hold your real e-mail, folder names or experiments.  Only the
`public` branch is ever pushed, and every commit on it is created by this tool, from a tree that passed the gate, with your no-reply identity.  The git pre-push
hook installed by `setup` refuses any other push (other branches, other remotes, force pushes, deletions).

Nothing personal is stored in this tracked file: your names, paths and e-mail words live in publish/local/config.json (never committed).
"""
import argparse, hashlib, io, json, os, re, subprocess, sys, tarfile, tempfile, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(ROOT, 'publish', 'local')
CFG_PATH = os.path.join(LOCAL, 'config.json')
NOREPLY = '@users.noreply.github.com'
ZERO = '0' * 40

# paths that must never be public, whatever their content
FORBID_PATH = [r'(^|/)assets/local(/|$)', r'(^|/)publish/local(/|$)', r'(^|/)dist(/|$)', r'(^|/)build(/|$)', r'(^|/)lab(/|$)', r'(^|/)backup(/|$)',
               r'\.(pfx|p12|pem|key|jks|keystore)$', r'(^|/)[^/]*private[^/]*$', r'(^|/)\.env[^/]*$', r'(^|/)id_(rsa|ed25519|ecdsa)',
               r'\.(esm|esp|esl|ba2|bsa|nif|dds|tga|ogg|wav|fuz|xwm|lip|bik|bk2|swf|hkx|kf|pex|bgsm|bgem|egm|egt|tri)$',
               r'\.(exe|dll|pyd|msi)$', r'\.(log|bak|orig)$', r'\.before-', r'\.pre-']
# things that look like credentials
SECRET_RX = [rb'-----BEGIN [A-Z ]*PRIVATE KEY-----', rb'ghp_[A-Za-z0-9]{30,}', rb'gho_[A-Za-z0-9]{30,}', rb'ghu_[A-Za-z0-9]{30,}', rb'ghs_[A-Za-z0-9]{30,}',
             rb'github_pat_[A-Za-z0-9_]{30,}', rb'xox[abprs]-[A-Za-z0-9-]{20,}', rb'AKIA[0-9A-Z]{16}', rb'AIza[0-9A-Za-z_-]{35}',
             rb'sk-[A-Za-z0-9]{32,}', rb'(?i)(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*[\'"][^\'"\s]{8,}[\'"]']
GENERIC_PERSONAL = [rb'[A-Za-z]:[\\/]+Users[\\/]+(?!Public|<|%|\{|\*|Default|All)[A-Za-z0-9._-]+']
MAX_FILE = 2 * 1024 * 1024
TEXT_SKIP_EXT = {'.png', '.ico', '.jpg', '.jpeg', '.gif', '.zip', '.7z', '.pyc'}


class Gate(Exception):
    pass


def git(root, *args, env=None, check=True, inp=None):
    e = dict(os.environ)
    e.update(env or {})
    r = subprocess.run(['git', '-C', root] + list(args), capture_output=True, input=inp, env=e)
    if check and r.returncode:
        raise Gate('git %s failed: %s' % (' '.join(args[:3]), r.stderr.decode('utf-8', 'replace').strip()[:300]))
    return r.stdout.decode('utf-8', 'replace') if inp is None or isinstance(inp, str) else r.stdout


def load_cfg(path=CFG_PATH):
    if not os.path.isfile(path):
        raise Gate('no private settings yet: run  python publish/publish.py setup')
    with open(path, encoding='utf-8') as f:
        c = json.load(f)
    if not re.fullmatch(r'[A-Za-z0-9._-]+/[A-Za-z0-9._-]+', c.get('repo', '')):
        raise Gate('config.json: "repo" must look like owner/name')
    if not c.get('author_email', '').endswith(NOREPLY):
        raise Gate('config.json: "author_email" must be your GitHub no-reply address (ends with %s), never a real e-mail' % NOREPLY)
    if not c.get('author_name'):
        raise Gate('config.json: "author_name" is missing')
    c.setdefault('private_strings', [])
    c.setdefault('signing_key_paths', [])
    return c


# ----------------------------------------------------------------------------------------------------------------------------------- scanning
def export_tree(root, rev, dest):
    """unpack exactly the committed files of `rev` (what would be public) into dest"""
    r = subprocess.run(['git', '-C', root, 'archive', '--format=tar', rev], capture_output=True)
    if r.returncode:
        raise Gate('cannot export %s: %s' % (rev, r.stderr.decode('utf-8', 'replace')[:200]))
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as t:
        t.extractall(dest, filter='data') if sys.version_info >= (3, 12) else t.extractall(dest)


def key_fingerprints(cfg):
    """hex of every private key file configured: searched for inside the tree and NEVER printed"""
    out = []
    for p in cfg.get('signing_key_paths', []):
        try:
            with open(p, 'rb') as f:
                v = f.read().strip()
            if len(v) >= 32:
                out.append(v)
        except OSError:
            pass
    return out


def scan_dir(d, cfg, label='tree'):
    """returns a list of problem strings for every file below d"""
    problems = []
    privs = [(s, re.compile(re.escape(s.encode('utf-8')), re.I)) for s in cfg.get('private_strings', []) if s]
    keys = key_fingerprints(cfg)
    n = 0
    for root, _, files in os.walk(d):
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, d).replace(os.sep, '/')
            n += 1
            for rx in FORBID_PATH:
                if re.search(rx, rel, re.I):
                    problems.append('%s: forbidden file %s' % (label, rel))
                    break
            size = os.path.getsize(p)
            if size > MAX_FILE:
                problems.append('%s: %s is %d MB (limit 2 MB)' % (label, rel, size >> 20))
            if os.path.splitext(f)[1].lower() in TEXT_SKIP_EXT and size > 600 * 1024:
                continue
            with open(p, 'rb') as fh:
                data = fh.read()
            for s, rx in privs:
                m = rx.search(data)
                if m:
                    problems.append('%s: %s contains a private string (%d chars, line %d)' % (label, rel, len(s), data[:m.start()].count(b'\n') + 1))
            for rx in SECRET_RX:
                m = re.search(rx, data)
                if m:
                    problems.append('%s: %s looks like a credential (line %d)' % (label, rel, data[:m.start()].count(b'\n') + 1))
            for rx in GENERIC_PERSONAL:
                m = re.search(rx, data)
                if m:
                    problems.append('%s: %s contains a personal Windows path (line %d)' % (label, rel, data[:m.start()].count(b'\n') + 1))
            for k in keys:
                if k in data:
                    problems.append('%s: %s CONTAINS YOUR PRIVATE SIGNING KEY' % (label, rel))
    return problems, n


def run_leak_scan(d):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'leak_scan.py'), d], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return [] if r.returncode == 0 else ['leak_scan: ' + l for l in r.stdout.splitlines() if l.startswith('FAIL')][:20] or ['leak_scan failed']


def check_tree(root, rev, cfg, label=None):
    with tempfile.TemporaryDirectory() as d:
        export_tree(root, rev, d)
        problems, n = scan_dir(d, cfg, label or rev[:12])
        problems += run_leak_scan(d)
    return problems, n


def check_identity(root, rev, cfg):
    """every commit reachable from rev must carry only the no-reply identity and a message free of private strings"""
    problems = []
    fmt = '%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%B%x1e'
    out = git(root, 'log', rev, '--format=' + fmt)
    privs = [s.lower() for s in cfg.get('private_strings', []) if s]
    for rec in out.split('\x1e'):
        rec = rec.strip('\n')
        if not rec:
            continue
        h, an, ae, cn, ce, msg = rec.split('\x1f')
        for who, email in (('author', ae), ('committer', ce)):
            if email != cfg['author_email']:
                problems.append('commit %s: %s e-mail is not your no-reply address' % (h[:8], who))
        for who, name in (('author', an), ('committer', cn)):
            if name != cfg['author_name']:
                problems.append('commit %s: %s name differs from config' % (h[:8], who))
        low = msg.lower()
        if any(s in low for s in privs):
            problems.append('commit %s: message contains a private string' % h[:8])
    return problems


def check_public_history(root, cfg):
    """the whole `public` branch: identity of every commit and the tree of every commit"""
    if git(root, 'rev-parse', '--verify', '-q', 'refs/heads/public', check=False).strip() == '':
        return ['there is no `public` branch yet (run snapshot)'], 0
    problems = check_identity(root, 'refs/heads/public', cfg)
    commits = git(root, 'rev-list', 'refs/heads/public').split()
    total = 0
    for c in commits:
        pr, n = check_tree(root, c, cfg, 'public@' + c[:8])
        problems += pr
        total = max(total, n)
    return problems, total


def check_state(root, skip_tests=False):
    problems = []
    if git(root, 'status', '--porcelain').strip():
        problems.append('uncommitted changes in the working tree: commit or discard them first (the gate checks the committed tree, so they would not be published)')
    if not skip_tests:
        r = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'], cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode:
            problems.append('the tests fail: ' + (r.stderr.strip().splitlines() or ['?'])[-1][:120])
    return problems


def report(title, problems):
    print('%-4s %s' % ('PASS' if not problems else 'FAIL', title))
    for p in problems[:25]:
        print('       - ' + p)
    if len(problems) > 25:
        print('       ... and %d more' % (len(problems) - 25))
    return not problems


# ----------------------------------------------------------------------------------------------------------------------------------- commands
def cmd_check(root, cfg, skip_tests=False):
    ok = True
    ok &= report('working tree is clean and tests pass', check_state(root, skip_tests))
    pr, n = check_tree(root, 'HEAD', cfg, 'HEAD')
    ok &= report('committed tree (%d files): no personal data, secrets, game files or forbidden files' % n, pr)
    ok &= report('git identity configured as no-reply', [] if cfg['author_email'].endswith(NOREPLY) else ['not a no-reply address'])
    return ok


def cmd_snapshot(root, cfg, message, skip_tests=False):
    if not cmd_check(root, cfg, skip_tests):
        raise Gate('the gate failed: nothing was created')
    head_tree = git(root, 'rev-parse', 'HEAD^{tree}').strip()
    pub = git(root, 'rev-parse', '--verify', '-q', 'refs/heads/public', check=False).strip()
    if pub and git(root, 'rev-parse', pub + '^{tree}').strip() == head_tree:
        print('the public branch already has this exact tree: nothing new')
        return pub
    env = {'GIT_AUTHOR_NAME': cfg['author_name'], 'GIT_AUTHOR_EMAIL': cfg['author_email'], 'GIT_COMMITTER_NAME': cfg['author_name'],
           'GIT_COMMITTER_EMAIL': cfg['author_email']}
    msg = message
    if any(s and s.lower() in msg.lower() for s in cfg['private_strings']):
        raise Gate('the commit message contains a private string')
    args = ['-c', 'commit.gpgsign=false', 'commit-tree', head_tree] + (['-p', pub] if pub else []) + ['-m', msg]
    new = git(root, *args, env=env).strip()
    git(root, 'update-ref', 'refs/heads/public', new)
    pr, _ = check_public_history(root, cfg)
    if pr:
        git(root, 'update-ref', '-d', 'refs/heads/public') if not pub else git(root, 'update-ref', 'refs/heads/public', pub)
        report('public history', pr)
        raise Gate('the public history failed the gate: the new commit was removed')
    print('public branch now at %s (%d commit(s)): nothing has been pushed' % (new[:10], len(git(root, 'rev-list', 'refs/heads/public').split())))
    return new


def remote_url(cfg):
    return 'https://github.com/%s.git' % cfg['repo']


def cmd_push(root, cfg, yes=False, skip_tests=False):
    pr, n = check_public_history(root, cfg)
    if not report('public branch: every commit passes the gate (%d files in the newest)' % n, pr):
        raise Gate('refusing to push')
    head_tree = git(root, 'rev-parse', 'HEAD^{tree}').strip()
    if git(root, 'rev-parse', 'refs/heads/public^{tree}').strip() != head_tree:
        raise Gate('the public branch is older than your current commit: run  publish.py snapshot -m "..."  first')
    existing = git(root, 'remote', 'get-url', 'origin', check=False).strip()
    if existing and existing != remote_url(cfg):
        raise Gate('remote "origin" is %s, expected %s: refusing' % (existing, remote_url(cfg)))
    commits = git(root, 'rev-list', '--count', 'refs/heads/public').strip()
    print('\nAbout to publish to https://github.com/%s (branch main): %s commit(s), %d files. This is public and cannot be fully undone.' % (cfg['repo'], commits, n))
    if not yes:
        if input('Type the repository name (%s) to confirm: ' % cfg['repo']).strip() != cfg['repo']:
            raise Gate('not confirmed: nothing pushed')
    if not existing:
        git(root, 'remote', 'add', 'origin', remote_url(cfg))
    r = subprocess.run(['git', '-C', root, 'push', 'origin', 'refs/heads/public:refs/heads/main'], text=True)
    if r.returncode:
        raise Gate('git push failed (is the GitHub repo empty and does your login work?)')
    print('pushed.')


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def check_release_dir(root, cfg, version):
    d = os.path.join(root, 'dist', 'release', 'v' + version)
    problems = []
    if not os.path.isdir(d):
        return d, ['%s does not exist (build it with tools/release.py)' % d]
    want = {'manifest.json', 'manifest.sig', 'SHA256SUMS.txt', 'CapitalConvert-%s.zip' % version, 'CapitalPayload-%s.zip' % version}
    have = set(os.listdir(d))
    if have != want:
        problems.append('release folder must hold exactly %s (has %s)' % (sorted(want), sorted(have)))
        return d, problems
    for line in open(os.path.join(d, 'SHA256SUMS.txt'), encoding='utf-8').read().splitlines():
        h, _, n = line.partition('  ')
        if not n or sha256_file(os.path.join(d, n.strip())) != h:
            problems.append('SHA256SUMS does not match %s' % n)
    sys.path.insert(0, os.path.join(root, 'builder'))
    import updater
    mb = open(os.path.join(d, 'manifest.json'), 'rb').read()
    try:
        updater.verify_signature(mb, open(os.path.join(d, 'manifest.sig')).read())
    except updater.UpdateError as e:
        problems.append(str(e))
    m = json.loads(mb)
    if m.get('version') != version:
        problems.append('manifest says version %s, not %s' % (m.get('version'), version))
    pz = os.path.join(d, m['payload']['name'])
    if sha256_file(pz) != m['payload']['sha256'] or os.path.getsize(pz) != m['payload']['size']:
        problems.append('payload zip does not match the signed manifest')
    src = git(root, 'show', 'refs/heads/public:builder/version.py', check=False)
    if "VERSION = '%s'" % version not in src:
        problems.append('builder/version.py on the public branch is not version %s (publish the matching source first)' % version)
    for z in (os.path.join(d, 'CapitalConvert-%s.zip' % version), pz):
        with tempfile.TemporaryDirectory() as t:
            zipfile.ZipFile(z).extractall(t)
            pr, _ = scan_dir(t, cfg, os.path.basename(z))
            # the packaged Python runtime is binary: only the personal strings / credentials / key checks matter there
            problems += [p for p in pr if 'forbidden file' not in p and 'MB (limit' not in p]
    return d, problems


def cmd_release(root, cfg, version, yes=False):
    d, pr = check_release_dir(root, cfg, version)
    if not report('release v%s: hashes, signature, version and contents' % version, pr):
        raise Gate('refusing to publish the release')
    tag = 'v' + version
    notes = os.path.join(d, 'RELEASE-NOTES.txt')
    m = json.load(open(os.path.join(d, 'manifest.json'), encoding='utf-8'))
    body = '%s\n\nSave compatibility: %s\n\nVerify the download: compare its SHA-256 with SHA256SUMS.txt.\n' % (m.get('notes', ''), m.get('save_compat', ''))
    if any(s and s.lower() in body.lower() for s in cfg['private_strings']):
        raise Gate('the release notes contain a private string')
    print('\nAbout to create the PUBLIC release %s on https://github.com/%s with the 5 files above.' % (tag, cfg['repo']))
    if not yes and input('Type the tag (%s) to confirm: ' % tag).strip() != tag:
        raise Gate('not confirmed: nothing published')
    with open(notes, 'w', encoding='utf-8') as f:
        f.write(body)
    try:
        files = [os.path.join(d, n) for n in sorted(os.listdir(d)) if n != 'RELEASE-NOTES.txt']
        r = subprocess.run(['gh', 'release', 'create', tag, '--repo', cfg['repo'], '--target', 'main', '--title', 'Fallout 4-Ever %s' % version, '--notes-file', notes] + files, text=True)
        if r.returncode:
            raise Gate('gh release create failed (is the source pushed first, and are you logged in with gh auth login?)')
    finally:
        os.remove(notes)
    print('release %s created.' % tag)


def cmd_hook(root, cfg, remote_name, url):
    """git pre-push hook: read the refs git is about to push from stdin and allow only public -> main and v* tags to the configured repo"""
    if url.rstrip('/') not in (remote_url(cfg), remote_url(cfg)[:-4]):
        print('publish guard: push to %s blocked (only https://github.com/%s is allowed)' % (url, cfg['repo']))
        return 1
    pub_commits = set(git(root, 'rev-list', 'refs/heads/public', check=False).split())
    for line in sys.stdin.read().splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        lref, lsha, rref, rsha = parts
        if lsha == ZERO:
            print('publish guard: deleting remote refs is blocked')
            return 1
        ok_branch = lref == 'refs/heads/public' and rref == 'refs/heads/main'
        ok_tag = lref.startswith('refs/tags/v') and rref == lref
        if not (ok_branch or ok_tag):
            print('publish guard: pushing %s -> %s is blocked (only the `public` branch to main, and v* tags, may go out; use publish/publish.py)' % (lref, rref))
            return 1
        if rsha != ZERO and subprocess.run(['git', '-C', root, 'cat-file', '-e', rsha + '^{commit}'], capture_output=True).returncode == 0:
            if subprocess.run(['git', '-C', root, 'merge-base', '--is-ancestor', rsha, lsha], capture_output=True).returncode != 0:
                print('publish guard: force-pushes (rewriting what is already public) are blocked')
                return 1
        sha = git(root, 'rev-parse', lsha + '^{commit}', check=False).strip()
        if sha not in pub_commits:
            print('publish guard: %s is not on the public branch: blocked' % lref)
            return 1
    pr, _ = check_public_history(root, cfg)
    if pr:
        report('public history', pr)
        return 1
    return 0


def cmd_setup(root):
    os.makedirs(LOCAL, exist_ok=True)
    if not os.path.isfile(CFG_PATH):
        example = os.path.join(root, 'publish', 'config.example.json')
        with open(example, encoding='utf-8') as f:
            data = f.read()
        with open(CFG_PATH, 'w', encoding='utf-8') as f:
            f.write(data)
        print('created %s: open it and fill in your details (this file is git-ignored and never published)' % CFG_PATH)
    hook = os.path.join(root, '.git', 'hooks', 'pre-push')
    with open(hook, 'w', encoding='utf-8', newline='\n') as f:
        f.write('#!/bin/sh\n# installed by publish/publish.py setup: only the gate may push\nexec python "%s" hook "$1" "$2"\n' % os.path.join(root, 'publish', 'publish.py').replace('\\', '/'))
    try:
        os.chmod(hook, 0o755)
    except OSError:
        pass
    print('pre-push guard installed: a plain `git push` now only works through the gate')
    try:
        c = load_cfg()
        git(root, 'config', 'user.email', c['author_email'])
        git(root, 'config', 'user.name', c['author_name'])
        print('this repository now commits as %s <%s> by default' % (c['author_name'], c['author_email']))
    except Gate as e:
        print('(identity not set yet: %s)' % e)


def cmd_status(root, cfg):
    pub = git(root, 'rev-parse', '--verify', '-q', 'refs/heads/public', check=False).strip()
    print('repo            : github.com/%s' % cfg['repo'])
    print('local commits   : %s on main (never pushed)' % git(root, 'rev-list', '--count', 'HEAD').strip())
    print('public branch   : %s' % ((pub[:10] + ', %s commit(s)' % git(root, 'rev-list', '--count', pub).strip()) if pub else 'none yet'))
    print('origin remote   : %s' % (git(root, 'remote', 'get-url', 'origin', check=False).strip() or 'not set'))
    print('push guard hook : %s' % ('installed' if os.path.isfile(os.path.join(root, '.git', 'hooks', 'pre-push')) else 'NOT installed (run setup)'))
    print('identity        : %s <%s>' % (cfg['author_name'], cfg['author_email']))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('setup')
    c = sub.add_parser('check')
    c.add_argument('--skip-tests', action='store_true')
    s = sub.add_parser('snapshot')
    s.add_argument('-m', '--message', required=True)
    s.add_argument('--skip-tests', action='store_true')
    p = sub.add_parser('push')
    p.add_argument('--yes', action='store_true')
    r = sub.add_parser('release')
    r.add_argument('version')
    r.add_argument('--yes', action='store_true')
    sub.add_parser('status')
    h = sub.add_parser('hook')
    h.add_argument('remote_name', nargs='?', default='')
    h.add_argument('url', nargs='?', default='')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'setup':
            cmd_setup(ROOT)
            return 0
        cfg = load_cfg()
        if a.cmd == 'check':
            return 0 if cmd_check(ROOT, cfg, a.skip_tests) else 1
        if a.cmd == 'snapshot':
            cmd_snapshot(ROOT, cfg, a.message, a.skip_tests)
        elif a.cmd == 'push':
            cmd_push(ROOT, cfg, a.yes)
        elif a.cmd == 'release':
            cmd_release(ROOT, cfg, a.version.lstrip('v'), a.yes)
        elif a.cmd == 'status':
            cmd_status(ROOT, cfg)
        elif a.cmd == 'hook':
            return cmd_hook(ROOT, cfg, a.remote_name, a.url)
        return 0
    except Gate as e:
        print('BLOCKED: %s' % e)
        return 1


if __name__ == '__main__':
    sys.exit(main())
