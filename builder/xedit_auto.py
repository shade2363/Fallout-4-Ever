"""Drive xEdit (xFOEdit64.exe) unattended for the builder: launch with a script, confirm its dialogs through UI Automation
(invoke patterns, never keyboard focus), wait until the script's output is finished, save when asked, close.

Dialogs seen (xEdit 4.1.5f): 'A message from the developer' (TfrmDeveloperMessage, Close), 'Module Selection' (TfrmModuleSelect, OK; its plugin tree
is custom drawn and not exposed to UIA, so the list comes pre-ticked from the plugin file given with -P:), and on exit 'Select files to save'
(TfrmFileSelect, OK).

    run_xedit(workdir, mode='FNV'|'FO4', data_dir, plugins, script, done_files=[...], save=False, timeout=1800, log=print)
"""
import glob, os, subprocess, time


def _desktop():
    from pywinauto import Desktop
    return Desktop(backend='uia')


def _main(d, pid):
    for w in d.windows():
        try:
            if w.class_name() == 'TfrmMain' and w.process_id() == pid:
                return w
        except Exception:
            pass
    return None


def _find(main, cls):
    try:
        for c in main.descendants():
            if c.class_name() == cls:
                return c
    except Exception:
        pass
    return None


def _top(d, pid, cls):
    for w in d.windows():
        try:
            if w.process_id() == pid and w.class_name() == cls:
                return w
        except Exception:
            pass
    return None


def _click(dlg, text):
    for b in dlg.descendants(control_type='Button'):
        if b.window_text() == text:
            b.invoke()
            return True
    return False


def _stable(path, secs=12):
    if not os.path.exists(path):
        return False
    a = os.path.getsize(path)
    time.sleep(secs)
    return os.path.exists(path) and os.path.getsize(path) == a and a > 0


def run_xedit(workdir, mode, data_dir, plugins, script, done_files=(), save=False, timeout=1800, log=print, extra_args=()):
    xedit = os.path.join(workdir, 'tool', 'xedit', 'xFOEdit64.exe')
    plist = os.path.join(workdir, 'lab', 'plugins_%s.txt' % mode.lower())
    open(plist, 'w', newline='').write(''.join('*%s\r\n' % p for p in plugins))
    ini = os.path.join(workdir, 'lab', 'Fallout.ini')
    args = [xedit, '-' + mode, '-D:' + data_dir, '-I:' + ini, '-P:' + plist, '-autoload', '-script:' + script] + list(extra_args)
    for f in done_files:
        if os.path.exists(f):
            os.remove(f)
    log('  xEdit %s: %s on %s' % (mode, script, ', '.join(plugins)))
    proc = subprocess.Popen(args, cwd=os.path.dirname(xedit), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = _desktop()
    t0 = time.time()
    ok_clicked = False
    try:
        while time.time() - t0 < timeout:
            if proc.poll() is not None:
                break
            main = _main(d, proc.pid)
            if main is not None:
                dev = _find(main, 'TfrmDeveloperMessage')
                if dev is not None:
                    try:
                        _click(dev, 'Close')
                    except Exception:
                        pass
                mod = _find(main, 'TfrmModuleSelect')
                if mod is not None and not ok_clicked:
                    time.sleep(2)
                    try:
                        if _click(mod, 'OK'):
                            ok_clicked = True
                            log('    module selection confirmed')
                    except Exception:
                        pass
            if ok_clicked and done_files and all(os.path.exists(f) for f in done_files):
                if all(_stable(f) for f in done_files):
                    log('    outputs written: ' + ', '.join(os.path.basename(f) for f in done_files))
                    break
            time.sleep(3)
        else:
            raise RuntimeError('xEdit run timed out after %d s' % timeout)
        if proc.poll() is None:
            if save:
                main = _main(d, proc.pid)
                try:
                    main.close()
                except Exception:
                    pass
                t1 = time.time()
                while time.time() - t1 < 300 and proc.poll() is None:
                    dlg = _top(d, proc.pid, 'TfrmFileSelect')
                    if dlg is None:
                        m = _main(d, proc.pid)
                        dlg = _find(m, 'TfrmFileSelect') if m is not None else None
                    if dlg is not None:
                        try:
                            if _click(dlg, 'OK'):
                                log('    save dialog confirmed')
                        except Exception:
                            pass
                    time.sleep(3)
            if proc.poll() is None:
                time.sleep(3)
                proc.kill()
    finally:
        if proc.poll() is None:
            proc.kill()
    missing = [f for f in done_files if not os.path.exists(f)]
    if missing:
        raise RuntimeError('xEdit finished without writing: ' + ', '.join(missing))
