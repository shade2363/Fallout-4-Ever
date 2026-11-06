"""Stage steps that are more than "run one script".  Each takes (cfg, log, *args); cfg has workdir / fo4 / fo3_data.
Everything here mirrors the manual procedure in README.md; nothing writes into the Fallout 3 install and the Fallout 4 install is only touched by
the prepare stage (CreationKit.ini, with a .bak) and the install stage."""
import glob, os, re, shutil, subprocess, sys
from stages import FO3_PLUGINS

PY = None


WARNINGS = []                      # problems that do not stop the build but must not be hidden: shown as a summary when the build ends


def _warn(cfg, text):
    WARNINGS.append(text)


def _py(cfg):
    return [sys.executable, '--script'] if getattr(sys, 'frozen', False) else [sys.executable]


def _run(cmd, cwd, log, env=None, tolerate=False, collect=None):
    """runs a helper program; its output goes through LogFilter (millions of converter lines become a few progress lines, the full text goes to raw-output.log);
    collect = a list that receives every raw line (to look for results)"""
    from logfilter import LogFilter
    log('    $ ' + ' '.join(cmd))
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=0x08000000 if os.name == 'nt' else 0)
    flt = LogFilter(os.environ.get('CAPITAL_RAW_LOG'))
    for line in p.stdout:
        if collect is not None:
            collect.append(line.rstrip())
        for shown in flt.feed(line):
            log('      ' + shown.strip() if shown.startswith('      ') else '      ' + shown)
    for shown in flt.finish():
        log(shown)
    rc = p.wait()
    if rc != 0 and not tolerate:
        raise RuntimeError('exit %d: %s' % (rc, ' '.join(cmd)))
    return rc


def _link_or_copy(src, dst):
    if os.path.exists(dst):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.link(src, dst)                                         # hard link: no extra disk space (same volume only)
    except OSError:
        shutil.copy2(src, dst)


# --------------------------------------------------------------------------------------------------------------------------------
def prepare(cfg, log):
    wd, fo4 = cfg['workdir'], cfg['fo4']
    for d in ('tool/output', 'lab/Data', 'lab/fnv/Data', 'backup', 'scripts/out', 'lab/worldfix', 'lab/actors'):
        os.makedirs(os.path.join(wd, d), exist_ok=True)
    import fetch_tools                       # third-party tools: official release pages, pinned SHA-256 (builder/tools.lock.json)
    for t in fetch_tools.load_lock():
        if all(os.path.exists(os.path.join(wd, s)) for s in t.get('sentinels', [])):
            log('  %s %s already in the work folder (not re-verified)' % (t['id'], t['version']))
        else:
            fetch_tools.ensure(wd, log, from_dir=cfg.get('tools_dir') or os.environ.get('CAPITAL_TOOLS_DIR'), only=t['id'])
    if not os.path.exists(os.path.join(wd, 'tool/build/xedit_converter/xConvert.exe')):
        raise RuntimeError('the bundled converter (tool/build/xedit_converter/xConvert.exe) is missing from the work folder')
    # Creation Kit: allow multiple masters (same edit setup.ps1 makes; backup first)
    ck = os.path.join(fo4, 'CreationKit.ini')
    if os.path.exists(ck):
        if not os.path.exists(ck + '.capital.bak'):
            shutil.copy2(ck, ck + '.capital.bak')
        t = open(ck, encoding='utf-8', errors='replace').read()
        for k in ('bAllowMultipleMasterFiles', 'bAllowMultipleMasterLoads'):
            if re.search(r'(?m)^%s\s*=' % k, t):
                t = re.sub(r'(?m)^%s\s*=.*' % k, '%s=1' % k, t)
            else:
                t = re.sub(r'(?m)^\[General\]\s*$', '[General]\r\n%s=1' % k, t, count=1)
        old = open(ck, encoding='utf-8', errors='replace').read()
        if t != old:        # never touch the user's file when the settings are already there
            open(ck, 'w', encoding='utf-8').write(t)
            log('  CreationKit.ini: multiple masters allowed (backup: CreationKit.ini.capital.bak)')
        else:
            log('  CreationKit.ini already allows multiple masters (not modified)')
    else:
        log('  CreationKit.ini not found (run the Creation Kit once, then rebuild this stage); continuing')
    # the converter looks for <Game>.exe + Data walking up from its cwd: lab = fake Fallout 4 root, lab/fnv = fake New Vegas root
    lab = os.path.join(wd, 'lab')
    _link_or_copy(os.path.join(fo4, 'Fallout4.exe'), os.path.join(lab, 'Fallout4.exe'))
    nv = os.path.join(lab, 'fnv', 'FalloutNV.exe')
    if not os.path.exists(nv):
        cand = [os.path.join(l, 'steamapps', 'common', 'Fallout New Vegas', 'FalloutNV.exe') for l in _libs()]
        real = next((c for c in cand if os.path.exists(c)), None)
        if real:
            shutil.copy2(real, nv)
        else:
            shutil.copy2(os.path.join(os.path.dirname(cfg['fo3_data']), 'Fallout3.exe'), nv)   # placeholder: only the file name is needed to mark the root
            log('  Fallout New Vegas not installed: using a renamed Fallout3.exe as a placeholder (only its presence is checked)')
    for f in glob.glob(os.path.join(fo4, 'Data', '*.es[mlp]')):
        n = os.path.basename(f)
        if n.lower() in ('fallout4.esm',) or n.lower().startswith(('dlc', 'ccbgs', 'ccfsvfo4', 'ccsbjfo4', 'ccotmfo4', 'ccrzrfo4', 'ccfrsfo4', 'cceejfo4', 'ccbgsfo4')):
            _link_or_copy(f, os.path.join(lab, 'Data', n))
    ini = os.path.join(lab, 'Fallout.ini')
    if not os.path.exists(ini):
        open(ini, 'w').write('[General]\r\nSStartingCell=\r\nSCharGenQuest=00102037\r\n')
    log('  work folder prepared: %s' % wd)


def _libs():
    import detect
    return [os.path.join(l) for l in detect.steam_libraries()]


# --------------------------------------------------------------------------------------------------------------------------------
def convert_plugins(cfg, log):
    wd, fo3 = cfg['workdir'], cfg['fo3_data']
    fnv_data = os.path.join(wd, 'lab', 'fnv', 'Data')
    conv = os.path.join(wd, 'tool', 'build', 'xedit_converter', 'xConvert.exe')
    ps = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File']
    for name in FO3_PLUGINS:
        src = os.path.join(fo3, name + '.esm')
        if not os.path.exists(src):
            log('  %s.esm not installed: skipped' % name)
            continue
        # Fallout3.esm is fed to xConvert under the name FalloutNV.esm; DLC masters are patched to point at it
        dst = os.path.join(fnv_data, 'FalloutNV.esm' if name == 'Fallout3' else name + '.esm')
        shutil.copy2(src, dst)
        if name != 'Fallout3':
            _run(ps + [os.path.join(wd, 'rename-master.ps1'), '-Plugin', dst, '-From', 'Fallout3.esm', '-To', 'FalloutNV.esm'], wd, log)
    for name in FO3_PLUGINS:
        if not os.path.exists(os.path.join(fo3, name + '.esm')):
            continue
        arg = 'FalloutNV.esm' if name == 'Fallout3' else name + '.esm'
        out = os.path.join(wd, 'lab', 'Data', arg)
        inp = os.path.join(fnv_data, arg)
        final = os.path.join(wd, 'lab', 'Data', name + '.esm')
        if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(inp):
            log('  %s already converted (%d MB): not converting again' % (name, os.path.getsize(out) // 1048576))
        else:
            log('  converting %s (the base world takes about 50 min and ~20 GB RAM)' % name)
            _run([conv, arg], os.path.join(wd, 'lab', 'fnv'), log)
            if not os.path.exists(out):
                raise RuntimeError('xConvert produced no %s' % out)
        if name == 'Fallout3':
            shutil.copy2(out, final)            # the base plugin was fed in as FalloutNV.esm; its output has no FalloutNV master to rename
            log('  Fallout3.esm written (%d MB)' % (os.path.getsize(final) // 1048576))
        else:
            _run(ps + [os.path.join(wd, 'rename-master.ps1'), '-Plugin', out, '-From', 'FalloutNV.esm', '-To', 'Fallout3.esm', '-Out', final], wd, log)
    log('  converted plugins are in lab/Data (the world-fix stage reads them from there)')


def seed_worldfix(cfg, log):
    """apply-fixes.ps1 reads the RAW converter output from lab/worldfix/raw (it only seeds that folder from a developer backup that a clean
    machine does not have): put the freshly converted plugins there"""
    wd = cfg['workdir']
    raw = os.path.join(wd, 'lab', 'worldfix', 'raw')
    os.makedirs(raw, exist_ok=True)
    n = 0
    for name in FO3_PLUGINS:
        src = os.path.join(wd, 'lab', 'Data', name + '.esm')
        dst = os.path.join(raw, name + '.esm')
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            n += 1
    log('  seeded %d raw converted plugins into lab/worldfix/raw' % n)


def lod_settings(cfg, log):
    wd = cfg['workdir']
    src = os.path.join(wd, 'tool', 'src', 'data', 'LODSettings', 'WastelandNV.LOD')
    if not os.path.exists(src):
        raise RuntimeError('converter LOD template missing: %s' % src)
    out = os.path.join(wd, 'tool', 'output', 'LODSettings')
    os.makedirs(out, exist_ok=True)
    worlds = ['wasteland', 'dcworld01', 'dcworld02', 'dcworld03', 'dcworld04', 'dcworld05', 'dcworld06', 'dcworld07', 'dcworld08', 'dcworld09']
    for w in worlds:
        shutil.copy2(src, os.path.join(out, w + '.lod'))
    log('  %d LOD setting files written (worlds with terrain LOD; extra copies for absent worlds are harmless)' % len(worlds))


FO4_PLUGINS = ['Fallout4.esm', 'DLCRobot.esm', 'DLCworkshop01.esm', 'DLCCoast.esm', 'DLCworkshop02.esm', 'DLCworkshop03.esm', 'DLCNukaWorld.esm']


def actors(cfg, log):
    """CapitalActors.esp: three xEdit runs driven through UI Automation (builder/xedit_auto.py) around build-actor-map.ps1, then name_actors.py"""
    import xedit_auto
    wd = cfg['workdir']
    py = _py(cfg)
    ps = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File']
    act = os.path.join(wd, 'lab', 'actors')
    os.makedirs(act, exist_ok=True)
    fnv_data = os.path.join(wd, 'lab', 'fnv', 'Data')
    lab_data = os.path.join(wd, 'lab', 'Data')
    # 1. FO3 placed actors + base records (FNV mode on the lab copies)
    if not (os.path.exists(os.path.join(act, 'actors.csv')) and os.path.exists(os.path.join(act, 'placed.csv'))):
        plug = ['FalloutNV.esm'] + [n + '.esm' for n in FO3_PLUGINS[1:] if os.path.exists(os.path.join(fnv_data, n + '.esm'))]
        xedit_auto.run_xedit(wd, 'FNV', fnv_data, plug, 'FO3 - Export actors.pas',
                             done_files=[os.path.join(act, 'actors.csv'), os.path.join(act, 'placed.csv')], log=log)
    # 2. Fallout 4 actor / template lists (read-only: lab/Data holds links to the Fallout 4 masters)
    fo4plug = [n for n in FO4_PLUGINS if os.path.exists(os.path.join(lab_data, n))]
    for scr, out in (('FO4 - List actors.pas', 'fo4_actors.csv'), ('FO4 - List NPC templates.pas', 'fo4_npc_templates.csv')):
        if not os.path.exists(os.path.join(act, out)):
            xedit_auto.run_xedit(wd, 'FO4', lab_data, fo4plug, scr, done_files=[os.path.join(act, out)], log=log)
    # 3. map FO3 actors to FO4 actors
    _run(ps + [os.path.join(wd, 'build-actor-map.ps1')], wd, log)
    # 4. place them (FO4 mode, Fallout4.esm + the world-fixed converted Fallout3.esm); xEdit saves CapitalActors.esp next to the masters
    shutil.copy2(os.path.join(wd, 'tool', 'output', 'Fallout3.esm'), os.path.join(lab_data, 'Fallout3.esm'))
    esp = os.path.join(lab_data, 'CapitalActors.esp')
    if os.path.exists(esp):
        os.remove(esp)
    xedit_auto.run_xedit(wd, 'FO4', lab_data, ['Fallout4.esm', 'Fallout3.esm'], 'FO4 - Place actors.pas',
                         done_files=[os.path.join(act, 'place-log.txt')], save=True, log=log)
    if not os.path.exists(esp):
        raise RuntimeError('xEdit did not save CapitalActors.esp into %s' % lab_data)
    shutil.copy2(esp, os.path.join(act, 'CapitalActors.esp.orig'))
    # 5. names for the named characters (writes tool/output/CapitalActors.esp)
    _run(py + [os.path.join(wd, 'actors', 'name_actors.py')], wd, log)
    # 6. the initially-disabled characters (childhood Dads, Beatrice ...) and the named characters name_actors skipped; they work in place on
    #    tool/output/CapitalActors.esp, which name_actors.py has just recreated from lab/actors/CapitalActors.esp.orig (so a re-run is safe)
    for rel in ('worldfix/place_disabled_actors.py', 'actors/name_disabled.py', 'actors/name_more_actors.py'):
        _run(py + [os.path.join(wd, rel)], wd, log)


def extras(cfg, log):
    wd = cfg['workdir']
    py = _py(cfg)
    for rel in ('skills/build_skills.py', 'perks/build_perks.py', 'ai/build_ai.py', 'objscripts/build_objscripts.py', 'objscripts/compile_obj.py'):
        if os.path.exists(os.path.join(wd, rel)):
            try:
                _run(py + [os.path.join(wd, rel)], wd, log)
            except RuntimeError as e:
                log('  (optional) %s failed: %s' % (rel, e))
        else:
            log('  (optional) %s not in the payload: skipped' % rel)


def ui(cfg, log):
    """main menu + character editor: needs the FO3 UI textures, extracted from the user's own BSA with bsab"""
    wd, fo3 = cfg['workdir'], cfg['fo3_data']
    py = _py(cfg)
    bsab = os.path.join(wd, 'tool', 'bin', 'bsab', 'bsab.exe')
    fo4 = cfg['fo4']
    jobs = [(os.path.join(fo4, 'Data', 'Fallout4 - Interface.ba2'), 'interface\\*', os.path.join(wd, 'ui', 'fo4')),
            (os.path.join(fo3, 'Fallout - Textures.bsa'), 'textures\\interface\\*', os.path.join(wd, 'ui', 'fo3')),
            (os.path.join(fo3, 'Fallout - Textures.bsa'), 'textures\\terminals\\pc\\english\\racesexinterface01.dds', os.path.join(wd, 'ui', 'fo3'))]
    for arc, flt, dest in jobs:
        os.makedirs(dest, exist_ok=True)
        _run([bsab, '-e', '-f', flt, arc, dest], wd, log, tolerate=True)
    _run(py + [os.path.join(wd, 'ui', 'build_menu.py')], wd, log)
    _run(py + [os.path.join(wd, 'ui', 'build_looks.py')], wd, log)
    _run(py + [os.path.join(wd, 'ui', 'bink', 'make_menu_video.py'), os.path.join(wd, 'ui', 'out', 'Video', 'MainMenuLoop.bk2')], wd, log)
    _run(py + [os.path.join(wd, 'ui', 'pack_menu.py')], wd, log)


FURN_KEYWORDS = {"FurnitureClassRelaxation": "0018F692", "AnimFurnAllowEating": "00144A65", "FurnitureScaleActorToOne": "0012F848", "AnimFurnCouch": "0010013D",
                 "AnimFurnBedAnims": "000BC262", "AnimFurnFloorBedAnims": "0003ADA2", "AnimFurnBarStool": "00074EC7", "IsSleepFurniture": "00021B18",
                 "AnimFurnChairSitAnims": "00030BB2"}      # vanilla Fallout4.esm KYWD FormIDs (game 1.10/1.11 are the same)


def furn_keywords(cfg, log):
    import json
    p = os.path.join(cfg['workdir'], 'lab', 'furn_keywords.json')
    json.dump(FURN_KEYWORDS, open(p, 'w'))
    log('  lab/furn_keywords.json written (%d keyword ids)' % len(FURN_KEYWORDS))


def sounds_placeholder(cfg, log):
    """objscripts/attach.py lists CapitalSounds.esp in its load order; the audio pipeline (not a builder stage yet) makes the real one.  Until then an empty plugin keeps attach.py working."""
    wd = cfg['workdir']
    p = os.path.join(wd, 'tool', 'output', 'CapitalSounds.esp')
    if os.path.exists(p):
        log('  CapitalSounds.esp already present: kept')
        return
    _run(_py(cfg) + [os.path.join(wd, 'worldfix', 'make_empty_plugin.py'), p], wd, log)
    log('  empty CapitalSounds.esp written (placeholder until the audio stage exists)')


def meshes(cfg, log):
    """loose meshes: keyframed-collision fixes, animated doors, meshes the bulk conversion skipped, terminal hybrids (+ turning the placed terminals)"""
    wd = cfg['workdir']
    py = _py(cfg)
    out = os.path.join(wd, 'tool', 'output')
    _run(py + [os.path.join(wd, 'worldfix', 'scan_animated_nifs.py'), '--out', os.path.join(out, 'loose')], wd, log)
    _run(py + [os.path.join(wd, 'worldfix', 'build_door_anims.py')], wd, log)
    audit = os.path.join(wd, 'lab', 'audit.txt')
    os.makedirs(os.path.dirname(audit), exist_ok=True)
    with open(audit, 'w', encoding='utf-8') as f:
        p = subprocess.run(py + [os.path.join(wd, 'worldfix', 'audit_meshes.py')], cwd=wd, stdout=f, stderr=subprocess.STDOUT, creationflags=0x08000000 if os.name == 'nt' else 0)
    if p.returncode != 0:                                       # a failed audit used to be logged as "exit 1" and the stage still said done: the repair then silently did nothing
        raise RuntimeError('the mesh audit failed (exit %d): see %s' % (p.returncode, audit))
    log('  audit_meshes -> lab/audit.txt (ok)')
    lines = []
    _run(py + [os.path.join(wd, 'worldfix', 'convert_missing.py'), audit], wd, log, tolerate=True, collect=lines)
    ok = sum(1 for l in lines if l.startswith('OK '))
    absent = sum(1 for l in lines if l.startswith('ABSENT '))
    bad = [l for l in lines if l.startswith('FAIL ')]
    log('  mesh repair: %d converted, %d are missing in Fallout 3 itself (nothing to convert), %d could not be converted' % (ok, absent, len(bad)))
    if bad:
        _warn(cfg, '%d meshes could not be converted and stay missing (see raw-output.log): the objects that use them are invisible in the game' % len(bad))
    # the doors Elric crashes on (reported 'model missing from archives' by build_door_anims): convert them one by one, then give them their animation
    for rel, extra in (('dungeons/metro/exterior/metrotunneltransdoorload01.nif', ['--no-collision']), ('dungeons/vault/halls/vdoor01.nif', []),
                       ('dungeons/vaultruined/doors/vdoorr01.nif', [])):
        rc = _run(py + [os.path.join(wd, 'worldfix', 'convert_single_mesh.py'), rel] + extra, wd, log, tolerate=True)
        if rc != 0 or not os.path.isfile(os.path.join(out, 'loose', 'meshes', 'new_vegas', *rel.split('/'))):
            _warn(cfg, 'the door mesh %s was not repaired: that door will not animate properly (Vault 101 door, metro doors)' % rel)
    _run(py + [os.path.join(wd, 'worldfix', 'build_door_anims.py')], wd, log)
    _run(py + [os.path.join(wd, 'worldfix', 'add_terminal_hybrid.py')], wd, log)
    _run(py + [os.path.join(wd, 'worldfix', 'fix_terminal_refs.py'), '--delta', '-90'], wd, log)


def _extract_head_assets(cfg, log):
    """lab/heads: FO3 head meshes + FaceGen morph/texture files (BSA) and the two FO4 base heads (BA2), as headfit.py / skin.py expect"""
    wd = cfg['workdir']
    heads = os.path.join(wd, 'lab', 'heads')
    os.makedirs(heads, exist_ok=True)
    sys.path.insert(0, os.path.join(wd, 'worldfix'))
    import bsa_extract, ba2_extract
    f, recs, comp, embed = bsa_extract.open_bsa(os.path.join(cfg['fo3_data'], 'Fallout - Meshes.bsa'))
    n = 0
    for r in recs:
        rp = r[0].replace(chr(92), '/')
        if rp.startswith('meshes/characters/head/') and rp.count('/') == 3 and os.path.splitext(rp)[1] in ('.nif', '.egm', '.egt', '.tri'):
            open(os.path.join(heads, os.path.basename(rp)), 'wb').write(bsa_extract.get(f, r, comp, embed))
            n += 1
    f2, names, recs2 = ba2_extract.open_ba2(os.path.join(cfg['fo4'], 'Data', 'Fallout4 - Meshes.ba2'))
    import zlib
    for nm, rec in zip(names, recs2):
        low = nm.lower().replace(chr(92), '/')
        if low in ('meshes/actors/character/characterassets/basemalehead.nif', 'meshes/actors/character/characterassets/basefemalehead.nif'):
            off, psz, usz = rec
            f2.seek(off)
            d = f2.read(psz or usz)
            open(os.path.join(heads, 'fo4_' + os.path.basename(low).replace('basemalehead', 'BaseMaleHead').replace('basefemalehead', 'BaseFemaleHead')), 'wb').write(zlib.decompress(d) if psz else d)
            n += 1
    log('  extracted %d head files into lab/heads' % n)


def faces(cfg, log):
    """FO3 faces on the named clones: head-part survey, then apply_faces (needs FaceGen bakes for the faces to render; see README)"""
    wd = cfg['workdir']
    py = _py(cfg)
    _extract_head_assets(cfg, log)
    _run(py + [os.path.join(wd, 'npcfaces', 'fo4_headparts.py')], wd, log)
    _run(py + [os.path.join(wd, 'npcfaces', 'skin_survey.py')], wd, log)
    _run(py + [os.path.join(wd, 'npcfaces', 'survey_npcs.py')], wd, log)
    _run(py + [os.path.join(wd, 'npcfaces', 'apply_faces.py')], wd, log)


CALLS = {'furn_keywords': furn_keywords, 'sounds_placeholder': sounds_placeholder, 'meshes': meshes, 'faces': faces, 'seed_worldfix': seed_worldfix, 'prepare': prepare, 'convert_plugins': convert_plugins, 'lod_settings': lod_settings, 'actors': actors, 'extras': extras, 'ui': ui}
