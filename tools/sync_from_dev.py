"""Copy the demo's code from the dev tree into this clean release repo, by allowlist only.

  python tools/sync_from_dev.py [--dev DIR] [--dry-run]

Scope (demo = world + actors + navmesh): the entry scripts below plus everything they reference (python imports and file names mentioned in
text), found by following references inside the dev tree. Nothing else is copied.  Third-party programs (tool/, xEdit, Papyrus compiler,
Archive2 ...) and anything derived from Bethesda data are NEVER copied: they are fetched or built on the user's PC.
Writes SYNC-MANIFEST.json (path + sha256).  Run tools/leak_scan.py afterwards.
"""
import argparse, fnmatch, hashlib, json, os, re, shutil

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BS = chr(92)
ENTRY = [   # demo stages: 01-prepare 02-assets 03-plugins 04-worldfix 05-lod 06-actors 10-navmesh 12-fixes 15-meshes 18-install
    'tests/crashers.txt',
    'builder/capital_builder.py', 'builder/gui.py', 'builder/detect.py', 'builder/steps.py', 'builder/stages.py', 'builder/xedit_auto.py',
    'builder/make_exe.py',
    'tools/make_blank_bik.py', 'tools/patch_bink_track.py',
    'convert-fo3-assets.ps1', 'rename-master.ps1', 'build-actor-map.ps1', 'install-output.ps1', 'capital-profile.ps1',
    'worldfix/apply-fixes.ps1', 'worldfix/restore_dlc_refs.py', 'worldfix/place_disabled_actors.py', 'worldfix/fix_crashers.py', 'worldfix/lock_terminals.py',
    'worldfix/scan_animated_nifs.py', 'worldfix/build_door_anims.py', 'worldfix/audit_meshes.py', 'worldfix/convert_missing.py',
    'worldfix/convert_single_mesh.py', 'worldfix/add_terminal_hybrid.py', 'worldfix/fix_terminal_refs.py', 'worldfix/make_empty_plugin.py',
    'actors/name_actors.py', 'actors/name_disabled.py', 'actors/name_more_actors.py',
    'navmesh/convert_navmesh.py', 'packaging/pack_ba2.ps1', 'packaging/common.ps1', 'packaging/ba2_tool.py', 'packaging/stage_dds.py',
    'tool/xedit/Edit Scripts/FO3 - Export actors.pas', 'tool/xedit/Edit Scripts/FO4 - List actors.pas',
    'tool/xedit/Edit Scripts/FO4 - List NPC templates.pas', 'tool/xedit/Edit Scripts/FO4 - Place actors.pas',
    'tool/xedit/Edit Scripts/FO3 and FNV - Translator.pas',
]
# never copied, whatever references them (matched against every path component)
DENY = ['*.pyc', '__pycache__', '*.before-*', '*.pre-*', '*.orig', '*.bak', '*.log', '*.err', 'dlc_*', '*speakers*', 'children.json',
        'voice_manifest*', 'counts-*', 'inspect-*', 'unresolved-*', 'outfit_models*', 'weapon_*', 'blender_*', 'build_outfits*', '*suit*',
        '*.esm', '*.esp', '*.esl', '*.ba2', '*.bsa', '*.nif', '*.dds', '*.tga', '*.ogg', '*.wav', '*.fuz', '*.bk2', '*.bik', '*.swf', '*.hkx',
        '*.pex', '*.exe', '*.dll']
DENY_DIRS = ['dialogue/', 'ai/', 'audio/', 'voice/', 'quests/', 'items/', 'perks/', 'skills/', 'objscripts/', 'npcfaces/', 'look/', 'ui/', 'tests/', 'kitbridge/', 'anim/', 'characters/', 'childhood/', 'dist/', 'build/', 'lab/', 'scripts/compiler/', 'backup/', 'Logs/', 'screenshots/', 'deliverables/', 'ui/fo3', 'ui/fo4']
REF = re.compile(r'[A-Za-z0-9_./\\ -]*[A-Za-z0-9_-]\.(?:py|ps1|pas|json|psc)\b')
IMP = re.compile(r'^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)', re.M)
TEXT = ('.py', '.ps1', '.psc', '.pas')
OWNED = ('builder/', 'install-output.ps1')       # seeded once from the dev tree, then owned by this repo
# machine-specific literals of the dev PC -> neutral placeholders (the builder's staging step maps the placeholders to the user's detected folders)
def _local():
    """your dev-machine paths live in publish/local/config.json (git-ignored); nothing personal is written in this tracked file"""
    try:
        with open(os.path.join(HERE, 'publish', 'local', 'config.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        raise SystemExit('publish/local/config.json is missing: run  python publish/publish.py setup  and fill in dev_tree and dev_literals')


LITERALS = [tuple(x) for x in _local().get('dev_literals', [])]



def scrub(text):
    for a, b in sorted(LITERALS, key=lambda p: -len(p[0])):
        for x, y in ((a, b), (a.replace(BS, BS * 2), b.replace(BS, BS * 2)), (a.replace(BS, '/'), b.replace(BS, '/'))):
            text = text.replace(x, y)
    return text
# copied but never followed: they mention every stage of the full port, the demo lists its own files in ENTRY
NOFOLLOW = ['builder/stages.py', 'builder/steps.py', 'builder/capital_builder.py', 'builder/gui.py', 'builder/make_exe.py', 'builder/detect.py',
            'install-output.ps1', 'capital-profile.ps1', 'packaging/pack_ba2.ps1']


ALLOW = ['tests/crashers.txt']          # data the demo needs although its folder is denied (see TRANSFORM)


def denied(rel):
    r = rel.replace(BS, '/')
    if r in ALLOW:
        return False
    if any(r.startswith(d) for d in DENY_DIRS):
        return True
    if r.startswith('tool/') and not r.startswith('tool/xedit/Edit Scripts/'):
        return True       # third-party tree: never ours to copy
    return any(fnmatch.fnmatch(p, pat) for pat in DENY for p in r.split('/'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dev', default=os.environ.get('CAPITAL_DEV_TREE') or _local().get('dev_tree'))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    dev = a.dev
    wanted, skipped = set(), set()
    queue = list(ENTRY)

    def find(name, base):
        name = name.replace(BS, '/').strip().lstrip('/')
        while name.startswith('./'):
            name = name[2:]
        for c in (os.path.join(os.path.dirname(base), name), os.path.join(dev, name)):
            if os.path.isfile(c):
                return os.path.relpath(c, dev).replace(BS, '/')
        return None

    while queue:
        rel = queue.pop()
        if rel in wanted or rel in skipped:
            continue
        if not os.path.isfile(os.path.join(dev, rel)) or denied(rel):
            skipped.add(rel)
            continue
        wanted.add(rel)
        if not rel.lower().endswith(TEXT) or rel in NOFOLLOW:
            continue
        txt = open(os.path.join(dev, rel), encoding='utf-8', errors='replace').read()
        if rel.endswith('.py'):
            for m in IMP.findall(txt):
                for d in (os.path.dirname(rel) + '/', 'worldfix/', 'actors/', 'navmesh/', 'packaging/', 'builder/', ''):
                    c = '%s%s.py' % (d, m)
                    if os.path.isfile(os.path.join(dev, c)):
                        queue.append(c)
                        break
        for m in REF.findall(txt):
            r = find(m, os.path.join(dev, rel))
            if r:
                queue.append(r)
    mp = os.path.join(HERE, 'SYNC-MANIFEST.json')
    if os.path.exists(mp) and not a.dry_run:
        for f in json.load(open(mp))['files']:
            if f['path'] not in wanted and os.path.exists(os.path.join(HERE, f['path'])):
                os.remove(os.path.join(HERE, f['path']))
    man = []
    for rel in sorted(wanted):
        src, dst = os.path.join(dev, rel), os.path.join(HERE, rel)
        raw = open(src, 'rb').read()
        if rel == 'tests/crashers.txt':       # keep plugin / record type / FormID only: the Editor ID column is Bethesda text
            tab = chr(9)
            rows = [l.split(tab) for l in raw.decode('utf-8').splitlines() if l.strip()]
            raw = ''.join(tab.join(c[:5] + ['']) + chr(10) for c in rows).encode('utf-8')
        elif rel.lower().endswith(TEXT + ('.json',)):
            raw = scrub(raw.decode('utf-8', errors='surrogateescape')).encode('utf-8', errors='surrogateescape')
        man.append({'path': rel, 'sha256': hashlib.sha256(raw).hexdigest()})
        if rel.startswith(OWNED) and os.path.exists(dst):
            continue            # the installer is a release product now: edited here, never overwritten from the dev tree
        if not a.dry_run:
            os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
            open(dst, 'wb').write(raw)
    if not a.dry_run:
        for r, ds, fs in os.walk(HERE, topdown=False):
            if not fs and not ds and '.git' not in r and r != HERE:
                os.rmdir(r)
        json.dump({'files': man}, open(mp, 'w'), indent=1)
    print('%d files %s; %d references skipped' % (len(wanted), 'would be copied' if a.dry_run else 'copied', len(skipped)))
    for s in sorted(skipped):
        if not s.endswith('.pyc'):
            print('  skipped:', s)


main()
