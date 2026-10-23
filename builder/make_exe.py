"""Build the release folder dist\\CapitalConvert\\  (PyInstaller one-folder exe + our pipeline scripts as payload).

  python builder\\make_exe.py [--zip]

The payload is only our own scripts (a few MB): no game files, no third-party tools (those are downloaded at setup and hash-checked),
no Bethesda programs.  Run tools\\leak_scan.py on the result before publishing.
"""
import os, shutil, subprocess, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from stages import PAYLOAD_DIRS, PAYLOAD_FILES, PAYLOAD_SKIP_DIRS, PAYLOAD_SKIP_EXT

DIST = os.path.join(ROOT, 'dist')
APP = os.path.join(DIST, 'CapitalConvert')


def build_exe():
    work = os.path.join(ROOT, 'build', 'capitalconvert')
    hidden = ['PIL', 'PIL.Image', 'PIL.ImageTk', 'tkinter', 'winreg', 'ctypes', 'zlib', 'struct', 'json', 'glob',
              'detect', 'stages', 'steps', 'gui', 'wasteland_art', 'fetch_tools', 'xedit_auto', 'capital_builder']
    cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--name', 'CapitalConvert', '--distpath', DIST, '--workpath', work,
           '--specpath', work, '--paths', HERE, '--noconsole', '--icon', os.path.join(ROOT, 'assets', 'app.ico'), os.path.join(HERE, 'capital_builder.py')]
    for h in hidden:
        cmd += ['--hidden-import', h]
    for pkg in ('PIL', 'pywinauto', 'comtypes'):
        cmd += ['--collect-all', pkg]
    for ex in ('numpy', 'scipy', 'sklearn', 'matplotlib', 'pandas', 'py7zr', 'IPython', 'pytest'):
        cmd += ['--exclude-module', ex]
    print(' '.join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def copy_payload():
    dst = os.path.join(APP, '_internal', 'payload')
    shutil.rmtree(dst, ignore_errors=True)
    n = 0
    for rel in PAYLOAD_DIRS:
        s = os.path.join(ROOT, rel)
        if not os.path.isdir(s):
            print('  (missing, skipped) %s' % rel)
            continue
        for root, dirs, files in os.walk(s):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')
                       and os.path.relpath(os.path.join(root, d), ROOT).replace(os.sep, '/') not in PAYLOAD_SKIP_DIRS]
            for f in files:
                if os.path.splitext(f)[1].lower() in PAYLOAD_SKIP_EXT:
                    continue
                o = os.path.join(dst, os.path.relpath(os.path.join(root, f), ROOT))
                os.makedirs(os.path.dirname(o), exist_ok=True)
                shutil.copy2(os.path.join(root, f), o)
                n += 1
    for rel in PAYLOAD_FILES:
        s = os.path.join(ROOT, rel)
        if os.path.exists(s):
            o = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(o), exist_ok=True)
            shutil.copy2(s, o)
            n += 1
    print('payload: %d files' % n)


def copy_docs():
    for f in ('README.md', 'CREDITS.md', 'NOTICE.md', 'LICENSE', 'CHANGELOG.md'):
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy2(os.path.join(ROOT, f), os.path.join(APP, f))
    for d in ('docs', 'THIRD_PARTY_LICENSES'):
        if os.path.isdir(os.path.join(ROOT, d)):
            shutil.copytree(os.path.join(ROOT, d), os.path.join(APP, d), dirs_exist_ok=True)


def zip_app():
    z = os.path.join(DIST, 'CapitalConvert.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _, files in os.walk(APP):
            for f in files:
                p = os.path.join(root, f)
                zf.write(p, os.path.relpath(p, DIST))
    print('wrote', z, os.path.getsize(z) // 1048576, 'MB')


if __name__ == '__main__':
    build_exe()
    copy_payload()
    copy_docs()
    if '--zip' in sys.argv:
        zip_app()
    print('done:', os.path.join(APP, 'CapitalConvert.exe'))
