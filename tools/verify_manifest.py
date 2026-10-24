"""SYNC-MANIFEST.json: the fingerprint of the program payload (the scripts the packaged program carries and runs), and the check that it is true.

  python tools/verify_manifest.py                        compare this repository with the manifest (exit 1 and a list when they differ)
  python tools/verify_manifest.py --root <folder>        compare a folder with the manifest, e.g. the payload of a built program:
                                                         dist\\CapitalConvert\\_internal\\payload  (or a release unzipped anywhere)
  python tools/verify_manifest.py --update               write the manifest from the files in this repository (run it after editing any payload file)

The payload is the folders and files listed in builder/stages.py (PAYLOAD_DIRS, PAYLOAD_FILES) without what builder/make_exe.py leaves out.  Every entry is the SHA-256 of the file
with Windows line endings turned into Unix ones, so a checkout with CRLF and one with LF give the same answer.  `origin` says who maintains the file: "dev" = copied from the
maintainer's development tree by tools/sync_from_dev.py (`dev_sha256` is the version that was copied; it differs from `sha256` when the file was edited here afterwards),
"repo" = lives only in this repository.  The manifest used to hold the hash of the development tree's copy, which is why it never matched the files it listed."""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, 'builder'))
import stages                                                     # noqa: E402

MANIFEST = os.path.join(HERE, 'SYNC-MANIFEST.json')


def digest(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read().replace(b'\r\n', b'\n')).hexdigest()


def payload_files(root):
    """relative paths (forward slashes) of everything the packaged program carries, found below `root` (same rules as builder/make_exe.py copy_payload)"""
    out = set()
    for rel in stages.PAYLOAD_DIRS:
        base = os.path.join(root, rel)
        if not os.path.isdir(base):
            continue
        for r, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')
                       and os.path.relpath(os.path.join(r, d), root).replace(os.sep, '/') not in stages.PAYLOAD_SKIP_DIRS]
            for f in files:
                if os.path.splitext(f)[1].lower() in stages.PAYLOAD_SKIP_EXT:
                    continue
                out.add(os.path.relpath(os.path.join(r, f), root).replace(os.sep, '/'))
    for rel in stages.PAYLOAD_FILES:
        if os.path.isfile(os.path.join(root, rel)):
            out.add(rel.replace(os.sep, '/'))
    return sorted(out)


def load(path=MANIFEST):
    with open(path, encoding='utf-8') as f:
        return json.load(f).get('files', [])


def check(root=HERE, manifest=MANIFEST):
    """-> list of problems, empty when the folder matches the manifest"""
    problems = []
    listed = {e['path']: e for e in load(manifest)}
    for p, e in sorted(listed.items()):
        full = os.path.join(root, p)
        if not os.path.isfile(full):
            problems.append('missing: %s' % p)
        elif digest(full) != e['sha256']:
            problems.append('changed: %s' % p)
    for p in payload_files(root):
        if p not in listed:
            problems.append('not in the manifest: %s' % p)
    return problems


def build(root=HERE, old=None, dev=None):
    """the manifest entries for the payload below `root`.  old = the entries of the previous manifest (their `origin` and `dev_sha256` are kept; an old entry without
    `dev_sha256` was written when the hash was the development tree's, so that hash becomes dev_sha256); dev = {path: hash of the file a sync just copied from the dev tree}"""
    old = {e['path']: e for e in (old or [])}
    dev = dev or {}
    files = []
    for p in payload_files(root):
        h = digest(os.path.join(root, p))
        e = old.get(p)
        entry = {'path': p, 'sha256': h, 'origin': e.get('origin', 'dev') if e else 'repo'}
        if p in dev:
            entry['origin'] = 'dev'
            d = dev[p]
        else:
            d = (e.get('dev_sha256') or e.get('sha256')) if (e and entry['origin'] == 'dev') else None
        if d and d != h:
            entry['dev_sha256'] = d
        files.append(entry)
    return files


def write(root=HERE, manifest=MANIFEST, dev=None):
    old = load(manifest) if os.path.isfile(manifest) else []
    files = build(root, old, dev)
    with open(manifest, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'files': files}, f, indent=1)
        f.write('\n')
    return files


def main(argv):
    root = HERE
    if '--root' in argv:
        root = os.path.abspath(argv[argv.index('--root') + 1])
    if '--update' in argv:
        files = write(HERE)
        print('SYNC-MANIFEST.json: %d payload files' % len(files))
        return 0
    problems = check(root)
    for p in problems:
        print(p)
    print('%s: %s' % (root, 'matches SYNC-MANIFEST.json' if not problems else '%d difference(s) from SYNC-MANIFEST.json (after editing a payload file run: python tools/verify_manifest.py --update)' % len(problems)))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
