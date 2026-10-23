"""Capital Convert builder: detects a Fallout 3 + Fallout 4 install and builds the Capital Wasteland port from the user's own files.

  CapitalBuilder.exe                 -> window (detect, check, build, resume)
  CapitalBuilder.exe detect          -> print what was found and every problem
  CapitalBuilder.exe plan            -> list the stages and their state
  CapitalBuilder.exe build [--from ID] [--only ID] [--workdir DIR] [--fo4 DIR] [--fo3 DATADIR] [--yes]
  CapitalBuilder.exe status
  CapitalBuilder.exe --script FILE.py [args...]   (internal: run a pipeline script with the bundled interpreter)

The payload (our pipeline scripts + the third-party tools) is staged into a private work folder; every machine-specific path in the
staged copy is rewritten to the detected install, so the original scripts run unchanged.  No Bethesda assets are shipped inside the exe.
Progress is stored in <workdir>\\builder-state.json, so a stopped or failed build resumes at the failed stage.
"""
import json, os, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, 'frozen', False) else __file__))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect
from version import VERSION, STEPS_REV
NOWIN = 0x08000000 if os.name == 'nt' else 0          # CREATE_NO_WINDOW: the windowed exe must not flash console windows for its helper programs
from stages import STAGES, PAYLOAD_DIRS, PAYLOAD_FILES, PAYLOAD_SKIP_EXT, PAYLOAD_SKIP_DIRS, REWRITE_EXT

APP = 'Capital Convert Builder'
DEFAULT_WORK = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'CapitalBuild')   # C:\ root is not writable without admin


def payload_root():
    """folder that holds the project payload: an installed (signed) update if there is one, else PyInstaller's data dir when frozen, else the repo"""
    try:
        import updater
        a = updater.active_payload()
        if a:
            return a
    except Exception:
        pass
    if getattr(sys, 'frozen', False):
        return os.path.join(getattr(sys, '_MEIPASS', HERE), 'payload')
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------------------------------------------ staging
SOURCE_LITERALS = {            # machine specific literals found in the pipeline scripts -> config key
    r'X:\__CAPITAL_FO3_DATA__': 'fo3_data',
    r'X:\__CAPITAL_FO3_ROOT__': 'fo3_root',
    r'X:\__CAPITAL_FO4__': 'fo4',
    r'X:\__CAPITAL_WORKDIR__': 'workdir',
    r'X:\__CAPITAL_USERPROFILE__': 'userprofile',
}


def _variants(s):
    """a path literal in the spellings used by the scripts: backslash, doubled backslash, forward slash, MSYS style"""
    return [(s, 'back'), (s.replace('\\', '\\\\'), 'dbl'), (s.replace('\\', '/'), 'fwd')]


def make_rewriter(cfg):
    target = {'fo3_data': cfg['fo3_data'], 'fo3_root': os.path.dirname(cfg['fo3_data'].rstrip('\\/')), 'fo4': cfg['fo4'], 'workdir': cfg['workdir'], 'userprofile': os.environ.get('USERPROFILE', r'C:\Users\Public')}
    pairs = []
    for lit, key in SOURCE_LITERALS.items():
        t = target[key]
        for src, style in _variants(lit):
            dst = {'back': t, 'dbl': t.replace('\\', '\\\\'), 'fwd': t.replace('\\', '/')}[style]
            pairs.append((src, dst))
    pairs.sort(key=lambda p: -len(p[0]))                 # longest first (the project dir contains no other literal, but be safe)
    def rewrite(text):
        for a, b in pairs:
            if a in text:
                text = text.replace(a, b)
        return text
    return rewrite


def stage_payload(cfg, log):
    src, dst = payload_root(), cfg['workdir']
    rewrite = make_rewriter(cfg)
    n_files = n_rewritten = 0
    os.makedirs(dst, exist_ok=True)
    items = [(d, True) for d in PAYLOAD_DIRS] + [(f, False) for f in PAYLOAD_FILES]
    for rel, is_dir in items:
        s = os.path.join(src, rel)
        if not os.path.exists(s):
            log('  payload item missing (skipped): %s' % rel)
            continue
        walk = [(s, d2) for d2 in [os.path.join(dst, rel)]] if is_dir else None
        files = []
        if is_dir:
            for root, dirs, fs in os.walk(s):
                dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')
                           and os.path.relpath(os.path.join(root, d), src).replace(os.sep, '/') not in PAYLOAD_SKIP_DIRS]
                for f in fs:
                    files.append(os.path.join(root, f))
        else:
            files = [s]
        for f in files:
            r = os.path.relpath(f, src)
            ext = os.path.splitext(f)[1].lower()
            if ext in PAYLOAD_SKIP_EXT:
                continue
            o = os.path.join(dst, r)
            os.makedirs(os.path.dirname(o), exist_ok=True)
            if ext in REWRITE_EXT:
                try:
                    raw = open(f, 'rb').read()
                    text = raw.decode('utf-8')
                    new = rewrite(text)
                    if new != text:
                        n_rewritten += 1
                    open(o, 'wb').write(new.encode('utf-8'))
                    n_files += 1
                    continue
                except UnicodeDecodeError:
                    pass
            if not os.path.exists(o) or os.path.getsize(o) != os.path.getsize(f):
                shutil.copy2(f, o)
            n_files += 1
    log('staged %d files into %s (%d had machine paths rewritten)' % (n_files, dst, n_rewritten))


# ------------------------------------------------------------------------------------------------------ state / config
def state_path(workdir):
    return os.path.join(workdir, 'builder-state.json')


def load_state(workdir):
    try:
        return json.load(open(state_path(workdir)))
    except (OSError, ValueError):
        return {'done': {}, 'config': {}}


def save_state(workdir, st):
    os.makedirs(workdir, exist_ok=True)
    json.dump(st, open(state_path(workdir), 'w'), indent=1)


def resolve_config(args, st):
    cfg = dict(st.get('config', {}))
    cfg['workdir'] = args.get('workdir') or cfg.get('workdir') or DEFAULT_WORK
    cfg['fo4'] = args.get('fo4') or cfg.get('fo4') or detect.find_fo4() or detect.find_fo4(scan=True)             # quick search first, then every fixed drive
    cfg['fo3_data'] = args.get('fo3') or cfg.get('fo3_data') or detect.find_fo3_data() or detect.find_fo3_data(scan=True)
    return cfg


def preflight(cfg):
    facts, problems = detect.inspect_install(cfg.get('fo4'), cfg.get('fo3_data'))
    wd = cfg['workdir']
    drive = os.path.splitdrive(os.path.abspath(wd))[0] + os.sep
    free = detect.free_gb(drive if os.path.isdir(drive) else wd)
    ram = detect.total_ram_gb()
    facts['workdir'] = wd
    try:
        import subprocess
        tl = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Fallout4.exe', '/NH'], capture_output=True, text=True, timeout=15, creationflags=NOWIN).stdout
        if 'Fallout4.exe' in tl:
            problems.append(('warn', 'Fallout 4 is running: close it before building (a step clicks and types into xEdit) and before installing.'))
    except Exception:
        pass
    facts['free_gb'] = round(free, 1)
    facts['ram_gb'] = round(ram, 1)
    if 0 <= free < 150:
        problems.append(('error' if free < 60 else 'warn', 'Only %.0f GB free on %s: the build needs about 150 GB of working space (14 GB final output + conversion scratch).' % (free, drive)))
    if 0 <= ram < 32:
        problems.append(('error' if ram < 24 else 'warn', 'Only %.0f GB RAM: the base-world conversion peaked at ~20 GB working set (32 GB recommended).' % ram))
    if cfg.get('fo4') and cfg.get('fo3_data') and os.path.splitdrive(cfg['fo3_data'])[0].lower() == os.path.splitdrive(wd)[0].lower() and False:
        pass
    return facts, problems


# ------------------------------------------------------------------------------------------------------ running
def python_cmd():
    """command prefix that runs a python script with an interpreter that has the pipeline's libraries"""
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--script']
    return [sys.executable]


def run_stage(stage, cfg, log, state):
    wd = cfg['workdir']
    env = dict(os.environ)
    env.update({'FO4_DIR': cfg['fo4'], 'FO3_DATA': cfg['fo3_data'], 'CAPITAL_ROOT': wd, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'})
    def sub(a):
        return a.replace('{wd}', wd).replace('{fo3}', cfg['fo3_data']).replace('{fo4}', cfg['fo4'])
    for step in stage['steps']:
        kind, *rest = step if isinstance(step, (list, tuple)) else (step,)
        rest = [sub(a) if isinstance(a, str) else a for a in rest]
        if kind == 'py':
            cmd = python_cmd() + [os.path.join(wd, rest[0])] + [a for a in rest[1:]]
        elif kind == 'ps':
            cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', os.path.join(wd, rest[0])] + list(rest[1:])
        elif kind == 'exe':
            cmd = [os.path.join(wd, rest[0])] + list(rest[1:])
        elif kind == 'call':
            from steps import CALLS
            log('  > %s' % rest[0])
            CALLS[rest[0]](cfg, log, *rest[1:])
            continue
        else:
            raise RuntimeError('bad step %r' % (step,))
        cwd = os.path.join(wd, step_cwd(rest, kind)) if kind != 'call' else wd
        log('  > ' + ' '.join('"%s"' % c if ' ' in c else c for c in cmd))
        p = subprocess.Popen(cmd, cwd=wd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=NOWIN)
        from logfilter import LogFilter
        flt = LogFilter(env.get('CAPITAL_RAW_LOG'))         # millions of converter lines become a few progress lines; the full text goes to raw-output.log
        for line in p.stdout:
            for shown in flt.feed(line):
                log('    ' + shown.strip())
        for shown in flt.finish():
            log(shown)
        if p.wait() != 0 and not stage.get('tolerate_exit'):
            raise RuntimeError('step failed (exit %d): %s' % (p.returncode, cmd[-1]))


def step_cwd(rest, kind):
    return ''


def stage_ready(stage, cfg):
    """(ok, why): required inputs present?"""
    wd = cfg['workdir']
    for req in stage.get('requires', []):
        path = req.format(wd=wd, fo4=cfg['fo4'], fo3=cfg['fo3_data'])
        if not (os.path.exists(path) or any(True for _ in _glob(path))):
            return False, 'missing input: %s' % path
    return True, ''


def _glob(p):
    import glob
    return glob.glob(p)


def stage_done(stage, cfg, st):
    rec = st['done'].get(stage['id'])
    if not rec:
        return False
    wd = cfg['workdir']
    for out in stage.get('produces', []):
        if not (os.path.exists(out.format(wd=wd, fo4=cfg['fo4'], fo3=cfg['fo3_data'])) or _glob(out.format(wd=wd, fo4=cfg['fo4'], fo3=cfg['fo3_data']))):
            return False
    return True


# ------------------------------------------------------------------------------------------------------ change detection
# files / folders (relative to the work folder) that a 'call' step reads; script steps (py / ps / exe) are hashed from their own arguments
CALL_DEPS = {'prepare': [], 'convert_plugins': ['rename-master.ps1'], 'seed_worldfix': ['worldfix/apply-fixes.ps1'], 'lod_settings': [],
             'actors': ['actors', 'worldfix/place_disabled_actors.py', 'build-actor-map.ps1', 'tool/xedit/Edit Scripts'],
             'meshes': ['worldfix'], 'furn_keywords': [], 'sounds_placeholder': ['worldfix/make_empty_plugin.py']}
SCRIPT_DIRS = ('worldfix', 'actors', 'navmesh', 'packaging', 'start')
TOOL_STAGES = ('01-prepare', '02-assets', '03-plugins')           # these also depend on the pinned third-party tool versions


def _add_tree(h, wd, rel):
    p = os.path.join(wd, rel)
    items = []
    if os.path.isdir(p):
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in files:
                if not f.endswith('.pyc'):
                    items.append(os.path.join(root, f))
    elif os.path.isfile(p):
        items.append(p)
    for f in sorted(items):
        h.update(os.path.relpath(f, wd).replace(os.sep, '/').encode())
        h.update(open(f, 'rb').read())


def stage_hash(stage, wd):
    """fingerprint of everything that decides what a stage produces from the same game files: its steps, the scripts they run, the pinned tools"""
    import hashlib
    h = hashlib.sha256()
    h.update(repr((stage['id'], stage['steps'])).encode())
    deps = []
    for step in stage['steps']:
        kind, *rest = step if isinstance(step, (list, tuple)) else (step,)
        if kind in ('py', 'ps', 'exe'):
            deps.append(rest[0])
            top = rest[0].split('/')[0]
            if top in SCRIPT_DIRS:
                deps.append(top)
            if top == 'start':
                deps.append('navmesh/navlib.py')
        elif kind == 'call':
            deps += CALL_DEPS.get(rest[0], [])
            h.update(('call:%s:%s' % (rest[0], STEPS_REV)).encode())
    if stage['id'] in TOOL_STAGES:
        deps.append('builder/tools.lock.json')
    for d in sorted(set(deps)):
        _add_tree(h, wd, d)
    return h.hexdigest()


def invalidate_changed(cfg, st, log):
    """a stage whose fingerprint changed since it was built is out of date, and so is every stage after it (they read its output)"""
    hashes = st.setdefault('hashes', {})
    stale = None
    for s in STAGES:
        cur = stage_hash(s, cfg['workdir'])
        old = hashes.get(s['id'])
        if s['id'] in st['done'] and old is not None and old != cur and stale is None:
            stale = s['id']
        if stale is None and s['id'] in st['done'] and old is None:
            hashes[s['id']] = cur                                          # state from before change tracking: adopt it
    if stale:
        log('scripts changed since the last build: re-running from [%s]; earlier stages are kept' % stale)
        after = False
        for s in STAGES:
            after = after or s['id'] == stale
            if after:
                st['done'].pop(s['id'], None)
                hashes.pop(s['id'], None)
    return stale


def build(cfg, log, start=None, only=None, to=None, st=None, stop_flag=lambda: False, progress=lambda *a: None):
    st = st or load_state(cfg['workdir'])
    st['config'] = cfg
    ids = [s['id'] for s in STAGES]
    todo = [s for s in STAGES if (only is None or s['id'] == only) and (start is None or ids.index(s['id']) >= ids.index(start))
            and (to is None or ids.index(s['id']) <= ids.index(to))]
    log('=== %s %s: %d stage(s) ===' % (APP, VERSION, len(todo)))
    import steps
    del steps.WARNINGS[:]
    os.environ['CAPITAL_RAW_LOG'] = os.path.join(cfg['workdir'], 'raw-output.log')
    if only is None:
        invalidate_changed(cfg, st, log)
        save_state(cfg['workdir'], st)
    for i, stage in enumerate(todo):
        if stop_flag():
            log('stopped by the user')
            return False
        progress(i, len(todo), stage)
        if stage_done(stage, cfg, st) and only is None:
            log('[%s] %s: already done, skipping' % (stage['id'], stage['title']))
            continue
        ok, why = stage_ready(stage, cfg)
        if not ok:
            log('[%s] %s: BLOCKED - %s' % (stage['id'], stage['title'], why))
            st['done'].pop(stage['id'], None)
            save_state(cfg['workdir'], st)
            if stage.get('optional'):
                continue
            return False
        log('[%s] %s  (about %s)' % (stage['id'], stage['title'], stage.get('eta', '?')))
        t0 = time.time()
        try:
            run_stage(stage, cfg, log, st)
        except Exception as e:
            log('[%s] FAILED: %s' % (stage['id'], e))
            st['done'].pop(stage['id'], None)
            save_state(cfg['workdir'], st)
            if stage.get('optional'):
                log('  (optional stage: continuing)')
                continue
            return False
        st.setdefault('hashes', {})[stage['id']] = stage_hash(stage, cfg['workdir'])
        st['done'][stage['id']] = {'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'secs': round(time.time() - t0)}
        save_state(cfg['workdir'], st)
        log('[%s] done in %d s' % (stage['id'], time.time() - t0))
    progress(len(todo), len(todo), None)
    if steps.WARNINGS:
        log('')
        log('=== %d warning(s): the build finished, but these things need your attention ===' % len(steps.WARNINGS))
        for w in steps.WARNINGS:
            log('  ! ' + w)
        log('  (details: builder.log and raw-output.log in the work folder)')
    return True


# ------------------------------------------------------------------------------------------------------ cli
def parse(argv):
    a = {'cmd': None, 'yes': False}
    i = 0
    while i < len(argv):
        t = argv[i]
        if t in ('--workdir', '--fo4', '--fo3', '--from', '--only', '--to') and i + 1 < len(argv):
            a[t[2:]] = argv[i + 1]
            i += 2
            continue
        if t == '--yes':
            a['yes'] = True
        elif not t.startswith('--') and a['cmd'] is None:
            a['cmd'] = t
        i += 1
    return a


def cmd_detect(args):
    st = load_state(args.get('workdir') or DEFAULT_WORK)
    cfg = resolve_config(args, st)
    facts, problems = preflight(cfg)
    for k, v in facts.items():
        print('%-18s %s' % (k, v))
    for lv, m in problems:
        print('%-6s %s' % (lv.upper(), m))
    return 1 if any(lv == 'error' for lv, _ in problems) else 0


def cmd_plan(args):
    st = load_state(args.get('workdir') or DEFAULT_WORK)
    cfg = resolve_config(args, st)
    for s in STAGES:
        mark = 'done' if (cfg.get('fo4') and stage_done(s, cfg, st)) else '    '
        print('[%s] %-4s %-48s %s%s' % (s['id'], mark, s['title'], s.get('eta', ''), '  (optional)' if s.get('optional') else ''))
    return 0


def _fix_std_streams(argv):
    """windowed exe (no console): sys.stdout / stderr start as None.  Order: (1) a handle the parent gave us (a pipe, a file redirect, or the pipe of a
    --script helper) is used as is; (2) a command typed in a terminal attaches to that terminal; (3) otherwise the void (never a crash)."""
    import ctypes
    k32 = ctypes.windll.kernel32
    k32.GetStdHandle.restype = ctypes.c_void_p

    def valid(h):
        return h not in (None, 0, -1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)
    for name, std in (('stdout', -11), ('stderr', -12)):
        if getattr(sys, name) is None:
            h = k32.GetStdHandle(std)
            if valid(h):
                try:
                    import msvcrt
                    setattr(sys, name, os.fdopen(msvcrt.open_osfhandle(h, os.O_WRONLY), 'w', encoding='utf-8', errors='replace'))
                except Exception:
                    pass
    if sys.stdout is None and argv and argv[:1] != ['--script'] and not argv[0].lower().endswith('.py'):
        try:
            if k32.AttachConsole(-1):                               # ATTACH_PARENT_PROCESS: print into the terminal the user typed the command in
                sys.stdout = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
                if sys.stderr is None:
                    sys.stderr = sys.stdout
        except OSError:
            pass
    for name in ('stdout', 'stderr'):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, 'w'))


def cmd_uninstall(args):
    st = load_state(args.get('workdir') or DEFAULT_WORK)
    wd = (st.get('config') or {}).get('workdir') or args.get('workdir') or DEFAULT_WORK
    ps1 = os.path.join(wd, 'install-output.ps1')
    if not os.path.isfile(ps1):
        print('nothing to uninstall: %s not found (pass --workdir)' % ps1)
        return 1
    base = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1, '-Uninstall']
    print(subprocess.run(base + ['-DryRun'], capture_output=True, text=True, creationflags=NOWIN).stdout)
    if not args['yes']:
        print('this was a preview; run again with --yes to remove these files')
        return 0
    r = subprocess.run(base, capture_output=True, text=True, creationflags=NOWIN)
    print(r.stdout)
    return r.returncode


def main(argv):
    if getattr(sys, 'frozen', False):
        _fix_std_streams(argv)
    if getattr(sys, 'frozen', False) and argv and argv[0].lower().endswith('.py') and os.path.isfile(argv[0]):
        argv = ['--script'] + list(argv)                             # the pipeline scripts call sys.executable <script.py>: inside the packaged exe that means --script
    if argv[:1] == ['--script']:                                     # internal: run a pipeline script inside the bundled interpreter
        import runpy
        script = argv[1]
        sys.argv = [script] + argv[2:]
        sys.path.insert(0, os.path.dirname(script))
        runpy.run_path(script, run_name='__main__')
        return 0
    args = parse(argv)
    if args['cmd'] is None:
        if getattr(sys, 'frozen', False):
            try:                                     # double-clicked exe: hide the console window, the window has its own log pane
                import ctypes
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
            except Exception:
                pass
        from gui import run_gui
        return run_gui()
    if args['cmd'] == 'uninstall':
        return cmd_uninstall(args)
    if args['cmd'] in ('update-check', 'update-install', 'update-rollback'):
        import updater
        try:
            if args['cmd'] == 'update-rollback':
                updater.rollback(print)
                return 0
            info = updater.check()
            print('installer %s, scripts %s, latest release %s  (%s)' % (info['app'], info['current'], info['latest'], info['save_text']))
            if info['notes']:
                print('notes: ' + info['notes'])
            if args['cmd'] == 'update-install':
                updater.apply(info, print)
            elif info['newer']:
                print('a newer version is available: run "update-install"')
            else:
                print('up to date')
            return 0
        except updater.UpdateError as e:
            print('update: ' + str(e))
            return 3
    if args['cmd'] == 'detect':
        return cmd_detect(args)
    if args['cmd'] == 'plan':
        return cmd_plan(args)
    if args['cmd'] == 'status':
        st = load_state(args.get('workdir') or DEFAULT_WORK)
        print(json.dumps(st, indent=1))
        return 0
    if args['cmd'] == 'build':
        st = load_state(args.get('workdir') or DEFAULT_WORK)
        cfg = resolve_config(args, st)
        facts, problems = preflight(cfg)
        for lv, m in problems:
            print('%-6s %s' % (lv.upper(), m))
        if any(lv == 'error' for lv, _ in problems) and not args['yes']:
            print('Fix the errors above first (or pass --yes to try anyway).')
            return 1
        os.makedirs(cfg['workdir'], exist_ok=True)                      # a brand-new work folder used to get no builder.log at all
        logf = open(os.path.join(cfg['workdir'], 'builder.log'), 'a', encoding='utf-8')
        def log(m):
            print(m, flush=True)
            logf.write(m + '\n'); logf.flush()
        stage_payload(cfg, log)
        ok = build(cfg, log, start=args.get('from'), only=args.get('only'), to=args.get('to'), st=st)
        return 0 if ok else 2
    print(__doc__)
    return 1


if __name__ == '__main__':
    try:
        code = main(sys.argv[1:])
    except SystemExit:
        raise
    except BaseException:                    # a windowed exe would show a blocking error dialog that nobody sees (stalled one tester for hours): print and exit instead
        import traceback
        traceback.print_exc()
        try:
            d = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'CapitalConvert'); os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'crash.log'), 'a', encoding='utf-8') as cf:
                cf.write('--- %s' % time.strftime('%Y-%m-%d %H:%M:%S') + chr(10) + traceback.format_exc() + chr(10))
        except Exception:
            pass
        code = 1
    sys.exit(code)
