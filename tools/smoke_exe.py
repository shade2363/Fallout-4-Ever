"""Smoke test of the PACKAGED exe (not the source): run it the way a stranger would, in a brand-new work folder.

  python tools/smoke_exe.py [--exe dist\\CapitalConvert\\CapitalConvert.exe] [--workdir DIR]

Needs Fallout 3 + Fallout 4 installed (read-only), and the two tool downloads either in %LOCALAPPDATA%\\CapitalConvert\\downloads (hash-checked cache) or internet.
It never installs into the games.  Checks: terminal commands print, the pinned tool list is found inside the exe, step 1 downloads/extracts/verifies the tools,
a later step runs through the exe's script mode, update-check fails gracefully offline, uninstall previews, and the window opens.
Exit code 0 = all passed.  Run it after EVERY packaging change (docs/RELEASE-CHECKLIST.md).
"""
import argparse, os, shutil, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []


def run(exe, args, env=None, timeout=1800):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run([exe] + args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, env=e)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def check(name, ok, detail=''):
    print('%-4s %s%s' % ('PASS' if ok else 'FAIL', name, ('  - ' + detail[:200].replace('\n', ' | ')) if (detail and not ok) else ''))
    if not ok:
        fails.append(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', default=os.path.join(ROOT, 'dist', 'CapitalConvert', 'CapitalConvert.exe'))
    ap.add_argument('--workdir', default=os.path.join(tempfile.gettempdir(), 'CapitalSmoke'))
    ap.add_argument('--keep', action='store_true')
    a = ap.parse_args()
    exe, wd = a.exe, a.workdir
    shutil.rmtree(wd, ignore_errors=True)
    os.makedirs(wd)

    rc, out = run(exe, ['detect'])
    check('detect prints and exits 0', rc == 0 and 'fo4' in out, out)
    rc, out = run(exe, ['plan'])
    check('plan lists the stages', rc == 0 and '[18-install]' in out and '[06-actors]' in out, out)
    rc, out = run(exe, ['build', '--workdir', wd, '--only', '01-prepare', '--yes'])
    check('step 1 runs (tool list found in the exe, tools fetched + verified)', rc == 0 and '[01-prepare] done' in out and 'Traceback' not in out, out[-600:])
    check('converter extracted', os.path.exists(os.path.join(wd, 'tool', 'build', 'xedit_converter', 'xConvert.exe')))
    check('xEdit extracted (7z)', os.path.exists(os.path.join(wd, 'tool', 'xedit', 'xFOEdit.exe')))
    check('our xEdit scripts kept next to xEdit', os.path.exists(os.path.join(wd, 'tool', 'xedit', 'Edit Scripts', 'FO4 - Place actors.pas')))
    rc, out = run(exe, ['build', '--workdir', wd, '--only', '01-prepare', '--yes'])
    check('step 1 again is a no-op that still works', rc == 0 and 'Traceback' not in out, out[-400:])
    rc, out = run(exe, ['build', '--workdir', wd, '--only', '05-lod', '--yes'])
    check('a step with files from the payload runs', rc == 0 and '[05-lod] done' in out, out[-400:])
    rc, out = run(exe, ['update-check'], env={'CAPITAL_UPDATE_URL': 'http://127.0.0.1:9'})
    check('update-check fails politely offline', rc in (0, 3) and 'Traceback' not in out, out)
    rc, out = run(exe, ['uninstall', '--workdir', wd])
    check('uninstall shows a preview and changes nothing', rc == 0 and 'Traceback' not in out, out)
    p = subprocess.Popen([exe])
    time.sleep(8)
    alive = p.poll() is None
    check('window opens and stays up', alive)
    if alive:
        p.kill()
    if not a.keep:
        shutil.rmtree(wd, ignore_errors=True)
    print('\n%s' % ('ALL PASSED' if not fails else 'FAILED: ' + ', '.join(fails)))
    sys.exit(1 if fails else 0)


main()
