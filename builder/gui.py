"""Capital Convert window, styled as a green-phosphor terminal: ruined-DC banner, bracketed panels, monospace text, blinking cursor.

Everything visual is drawn in code (wasteland_art.py); no game art, logos or fonts are used.  One big button: INSTALL / RESUME.
"""
import os, queue, sys, threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

import capital_builder as cb
from stages import STAGES

W, H, HERO = 1040, 872, 250
BG, PANEL, TXT, DIM, BRIGHT, WARN, ERR = '#020b05', '#03140a', '#4dff88', '#1f9a4c', '#b8ffd0', '#ffb000', '#ff5a3c'
FONT, FONTB, MONO = ('Consolas', 10), ('Consolas', 10, 'bold'), ('Consolas', 9)
PANELS = {'paths': (24, 262, 560, 412), 'checks': (576, 262, 1016, 412), 'stages': (24, 426, 560, 696),
          'log': (576, 426, 1016, 696), 'bottom': (24, 710, 1016, 856)}


def make_background():
    """PIL image W x H: phosphor banner on top, dark scanlined body with bracketed panels; None when Pillow is missing"""
    try:
        from PIL import Image, ImageDraw, ImageChops, ImageFilter
        from wasteland_art import make_wasteland, phosphor
    except ImportError:
        return None
    out = Image.new('RGB', (W, H), (1, 9, 4))
    out.paste(phosphor(make_wasteland(W, HERO)), (0, 0))
    d = ImageDraw.Draw(out)
    for y in range(HERO, H, 3):                                                 # scanlines over the body
        d.line((0, y, W, y), fill=(0, 6, 2))
    vg = Image.new('L', (W, H), 0)                                              # soft vignette
    ImageDraw.Draw(vg).ellipse((-W * 0.2, -H * 0.2, W * 1.2, H * 1.2), fill=255)
    vg = vg.filter(ImageFilter.GaussianBlur(110)).point(lambda p: 120 + int(p * 0.53))
    out = ImageChops.multiply(out, Image.merge('RGB', (vg, vg, vg)))
    d = ImageDraw.Draw(out)
    d.line((0, HERO, W, HERO), fill=(40, 190, 90), width=2)
    for x0, y0, x1, y1 in PANELS.values():
        d.rectangle((x0, y0, x1, y1), fill=(2, 20, 9), outline=(26, 120, 58))
        for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):      # corner brackets
            d.line((cx, cy, cx + 14 * sx, cy), fill=(77, 255, 136), width=2)
            d.line((cx, cy, cx, cy + 14 * sy), fill=(77, 255, 136), width=2)
    return out


def run_gui():
    root = tk.Tk()
    root.title('Fallout 4-Ever')
    root.geometry('%dx%d' % (W, H))
    root.resizable(False, False)
    root.configure(bg=BG)
    cv = tk.Canvas(root, width=W, height=H, highlightthickness=0, bg=BG)
    cv.pack()
    photo = None
    bg = make_background()
    if bg is not None:
        from PIL import ImageTk
        photo = ImageTk.PhotoImage(bg)
        cv.create_image(0, 0, image=photo, anchor='nw')
    else:
        for x0, y0, x1, y1 in PANELS.values():
            cv.create_rectangle(x0, y0, x1, y1, fill=PANEL, outline=DIM)
    for dx, dy, col in ((2, 2, '#04361a'), (0, 0, BRIGHT)):                       # title with a phosphor glow
        cv.create_text(30 + dx, 38 + dy, text='FALLOUT 4-EVER', anchor='w', fill=col, font=('Consolas', 30, 'bold'))
    cv.create_text(32, 78, text='> Capital Convert: Fallout 3 -> Fallout 4  |  demo: world, actors, navmesh', anchor='w', fill=TXT, font=('Consolas', 11))
    cv.create_text(W - 24, 52, text='by TikTok@yourstruly_0', anchor='e', fill=BRIGHT, font=('Consolas', 12, 'bold'))
    cv.create_text(W - 24, 74, text='with opness1549', anchor='e', fill=TXT, font=('Consolas', 12))
    cv.create_rectangle(W - 560, 90, W - 14, 108, fill='#021208', outline='', stipple='gray75')
    cv.create_text(W - 24, 98, text='powered by fnv-to-fo4 (terry-haire) | xEdit (TES5Edit team) | NifSkope (NifTools)', anchor='e', fill=TXT, font=MONO)
    cv.create_text(W - 24, 24, text='TERMINAL v' + getattr(cb, 'VERSION', '0.1.0'), anchor='e', fill=DIM, font=FONT)

    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=TXT, rowheight=20, borderwidth=0, font=MONO)
    style.configure('Treeview.Heading', background='#062a14', foreground=BRIGHT, font=FONTB, borderwidth=0, relief='flat')
    style.map('Treeview', background=[('selected', '#0a3d1d')], foreground=[('selected', BRIGHT)])
    style.configure('Bar.Horizontal.TProgressbar', troughcolor='#031a0b', background=TXT, borderwidth=0, thickness=12)

    st = cb.load_state(cb.DEFAULT_WORK)
    cfg = cb.resolve_config({}, st)
    q = queue.Queue()
    stop = {'v': False}
    vars_ = {k: tk.StringVar(value=cfg.get(k) or '') for k in ('fo4', 'fo3_data', 'workdir')}

    def place(widget, name, dx, dy, w=None, h=None):
        x0, y0 = PANELS[name][:2]
        cv.create_window(x0 + dx, y0 + dy, window=widget, anchor='nw', width=w, height=h)

    def title(name, text, hint=''):
        x0, y0 = PANELS[name][:2]
        cv.create_text(x0 + 18, y0 + 16, text='[ %s ]' % text, anchor='w', fill=BRIGHT, font=FONTB)
        if hint:
            cv.create_text(x0 + 24 + 8 * (len(text) + 4), y0 + 16, text=hint, anchor='w', fill=DIM, font=MONO)

    def tbutton(text, cmd, big=False):
        if big:
            return tk.Button(cv, text=text, command=cmd, bg=TXT, fg='#00210c', activebackground=BRIGHT, activeforeground='#00210c', disabledforeground='#1f6a3a',
                             relief='flat', bd=0, font=('Consolas', 15, 'bold'), cursor='hand2')
        return tk.Button(cv, text=text, command=cmd, bg='#04200f', fg=TXT, activebackground=TXT, activeforeground='#00210c', disabledforeground='#1f6a3a',
                         relief='flat', bd=0, highlightthickness=1, highlightbackground=DIM, font=FONT, cursor='hand2')

    # --- paths
    title('paths', 'YOUR GAMES', 'found automatically; change if needed')
    for i, (label, key) in enumerate((('Fallout 4 folder', 'fo4'), ('Fallout 3 Data folder', 'fo3_data'), ('Work folder (150 GB)', 'workdir'))):
        y = 40 + i * 34
        lb = tk.Label(cv, text=label, bg=PANEL, fg=DIM, font=MONO, anchor='w')
        place(lb, 'paths', 16, y + 3, 150, 20)
        e = tk.Entry(cv, textvariable=vars_[key], bg='#010a04', fg=TXT, insertbackground=TXT, relief='flat', font=MONO, highlightthickness=1,
                     highlightbackground=DIM, highlightcolor=TXT)
        place(e, 'paths', 168, y, 280, 26)
        place(tbutton('Browse', lambda k=key: vars_[k].set(filedialog.askdirectory(initialdir=vars_[k].get() or '/') or vars_[k].get())), 'paths', 456, y, 66, 26)

    # --- checks
    title('checks', 'CHECKS')
    checks = tk.Text(cv, bg=PANEL, fg=TXT, font=MONO, bd=0, highlightthickness=0, wrap='word', cursor='arrow')
    checks.tag_configure('error', foreground=ERR)
    checks.tag_configure('warn', foreground=WARN)
    checks.tag_configure('ok', foreground=BRIGHT)
    place(checks, 'checks', 14, 34, 410, 108)

    # --- stages
    title('stages', 'WHAT IT DOES', 'about 4 to 8 hours the first time')
    tree = ttk.Treeview(cv, columns=('title', 'eta', 'state'), show='headings', height=10)
    for c, w, t in (('title', 336, 'STEP'), ('eta', 84, 'TIME'), ('state', 90, 'STATE')):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor='w')
    place(tree, 'stages', 12, 34, 512, 226)

    # --- log
    title('log', 'LOG')
    log = tk.Text(cv, bg=PANEL, fg=DIM, font=MONO, bd=0, highlightthickness=0, wrap='word', state='disabled')
    place(log, 'log', 14, 34, 410, 226)

    # --- bottom
    bx, by = PANELS['bottom'][:2]
    bar = ttk.Progressbar(cv, maximum=len(STAGES), style='Bar.Horizontal.TProgressbar')
    place(bar, 'bottom', 16, 14, 984, 12)
    cv.create_text(bx + 18, by + 42, text='', anchor='w', fill=BRIGHT, font=('Consolas', 11), tags='status')
    legal = ('You must own Fallout 3 and Fallout 4 (with the Creation Kit). No game files are included: everything is built on this PC from your own copies, '
             'for your personal use only. Not affiliated with or endorsed by Bethesda Softworks or ZeniMax.')
    cv.create_text(bx + 18, by + 124, text=legal, anchor='w', fill=DIM, font=('Consolas', 8), width=950)
    blink = {'on': True, 'msg': 'READY'}

    def tick():
        blink['on'] = not blink['on']
        cv.itemconfigure('status', text='> ' + blink['msg'] + ('_' if blink['on'] else ' '))
        root.after(520, tick)

    def set_status(t):
        blink['msg'] = t

    def cur_cfg():
        c = dict(cfg)
        for k, v in vars_.items():
            c[k] = v.get().strip()
        return c

    def refresh(current=None):
        c = cur_cfg()
        s = cb.load_state(c['workdir'])
        facts, problems = cb.preflight(c)
        checks.configure(state='normal')
        checks.delete('1.0', 'end')
        for k, v in facts.items():
            checks.insert('end', '%-14s %s\n' % (k, v))
        for lv, m in problems:
            checks.insert('end', '%s %s\n' % ('[XX]' if lv == 'error' else '[!!]', m), lv)
        if not problems:
            checks.insert('end', '[OK] all checks passed\n', 'ok')
        checks.configure(state='disabled')
        tree.delete(*tree.get_children())
        for sg in STAGES:
            state = '[OK] done' if sg['id'] in s['done'] else ('[>>] running' if sg['id'] == current else '')
            tree.insert('', 'end', iid=sg['id'], values=(sg['title'], sg.get('eta', ''), state))
        return any(lv == 'error' for lv, _ in problems)

    def pump():
        try:
            while True:
                kind, val = q.get_nowait()
                if kind == 'log':
                    log.configure(state='normal')
                    log.insert('end', val + '\n')
                    log.see('end')
                    log.configure(state='disabled')
                elif kind == 'progress':
                    i, sg = val
                    bar['value'] = i
                    if sg:
                        set_status('STEP %d OF %d: %s' % (i + 1, len(STAGES), sg['title'].upper()))
                        refresh(sg['id'])
                    else:
                        set_status('FINISHED')
                elif kind == 'ask_uninstall':
                    uninstall_confirmed(*val)
                elif kind == 'refresh':
                    refresh()
                    build_btn.config(state='normal')
                    stop_btn.config(state='disabled')
        except queue.Empty:
            pass
        root.after(200, pump)

    def go(start=None):
        if refresh() and not messagebox.askyesno(cb.APP, 'The checks show errors. Try anyway?'):
            return
        c = cur_cfg()
        stop['v'] = False
        build_btn.config(state='disabled')
        stop_btn.config(state='normal')
        set_status('STARTING')

        def work():
            try:
                os.makedirs(c['workdir'], exist_ok=True)
                lf = open(os.path.join(c['workdir'], 'builder.log'), 'a', encoding='utf-8')

                def lg(m):
                    q.put(('log', m))
                    lf.write(m + '\n')
                    lf.flush()
                cb.stage_payload(c, lg)
                cb.build(c, lg, start=start, stop_flag=lambda: stop['v'], progress=lambda i, n, s: q.put(('progress', (i, s))))
            except Exception as e:
                q.put(('log', 'ERROR: %s' % e))
            q.put(('refresh', None))
        threading.Thread(target=work, daemon=True).start()

    def credits_text():
        for d in (cb.payload_root(), cb.HERE, os.path.dirname(cb.HERE)):
            p = os.path.join(d, 'CREDITS.md')
            if os.path.isfile(p):
                out = []
                for ln in open(p, encoding='utf-8').read().splitlines():
                    if ln.startswith('|---') or ln.startswith('| ---') or ln.startswith('|-'):
                        continue
                    if ln.startswith('|'):
                        cells = [c.strip().replace('**', '').replace('`', '') for c in ln.strip('|').split('|')]
                        if cells and cells[0] in ('Software',):
                            continue
                        out.append('  * ' + cells[0] + (' - ' + cells[1] if len(cells) > 1 else '') + (' [' + cells[2] + ']' if len(cells) > 2 else '') + (' ' + cells[3] if len(cells) > 3 else ''))
                    elif ln.startswith('## '):
                        out += ['', '[ ' + ln[3:].upper() + ' ]']
                    elif ln.startswith('# '):
                        out.append(ln[2:].upper())
                    else:
                        out.append(ln.replace('**', '').replace('`', ''))
                return chr(10).join(out)
        return 'Credits file not found. Fallout 4-Ever by TikTok@yourstruly_0, with opness1549. Built on fnv-to-fo4 (terry-haire), xEdit (TES5Edit team), NifSkope (NifTools).'

    def show_credits():
        win = tk.Toplevel(root)
        win.title('Credits')
        win.geometry('820x620')
        win.configure(bg=BG)
        txt = tk.Text(win, bg=PANEL, fg=TXT, font=MONO, bd=0, highlightthickness=1, highlightbackground=DIM, wrap='word', padx=14, pady=10)
        sb = tk.Scrollbar(win, command=txt.yview, bg=PANEL, troughcolor=BG)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        txt.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        txt.insert('1.0', credits_text())
        txt.configure(state='disabled')

    def show_updates():
        import updater
        win = tk.Toplevel(root)
        win.title('Updates')
        win.geometry('660x440')
        win.configure(bg=BG)
        out = tk.Text(win, bg=PANEL, fg=TXT, font=MONO, bd=0, highlightthickness=1, highlightbackground=DIM, wrap='word', padx=12, pady=10, state='disabled')
        out.pack(fill='both', expand=True, padx=8, pady=(8, 4))
        row = tk.Frame(win, bg=BG)
        row.pack(fill='x', padx=8, pady=(0, 8))
        res = {'info': None}
        q2 = queue.Queue()

        def say(t):
            out.configure(state='normal')
            out.insert('end', t + chr(10))
            out.see('end')
            out.configure(state='disabled')

        def run(fn, done):
            def w():
                try:
                    q2.put((True, fn(), done))
                except Exception as e:
                    q2.put((False, str(e), done))
            threading.Thread(target=w, daemon=True).start()

        def poll():
            try:
                while True:
                    ok, val, done = q2.get_nowait()
                    done(ok, val)
            except queue.Empty:
                pass
            if win.winfo_exists():
                win.after(200, poll)

        def header():
            a = updater.active_info()
            say('Installer version : %s' % updater.VERSION)
            say('Scripts version   : %s%s' % (updater.current_payload_version(), ' (installed update)' if a else ' (bundled)'))
            say('Update source     : github.com/%s (only contacted when you press Check)' % updater.UPDATE_REPO)
            say('')

        def after_check(ok, val):
            check_btn.config(state='normal')
            if not ok:
                say('Could not check: ' + val)
                return
            res['info'] = val
            say('Latest release    : %s' % val['latest'])
            if val['notes']:
                say('Notes: ' + val['notes'])
            say(val['save_text'])
            if val['app_too_old']:
                say('This update needs a newer installer: download the new release from github.com/%s/releases' % updater.UPDATE_REPO)
            elif val['newer']:
                say('A newer version is available.')
                install_btn.config(state='normal')
            else:
                say('You are up to date.')

        def do_check():
            check_btn.config(state='disabled')
            install_btn.config(state='disabled')
            say('Checking...')
            run(updater.check, after_check)

        def after_install(ok, val):
            if ok:
                say('Update %s installed. Close this window, then press INSTALL / RESUME: only the steps whose scripts changed will run again.' % val)
            else:
                say('Update NOT installed: ' + val)
            check_btn.config(state='normal')

        def do_install():
            install_btn.config(state='disabled')
            check_btn.config(state='disabled')
            say('Downloading and verifying...')
            run(lambda: updater.apply(res['info'], say), after_install)

        def do_rollback():
            try:
                v = updater.rollback(say)
                say('Now using scripts version %s. Press INSTALL / RESUME to rebuild what changed.' % v)
            except updater.UpdateError as e:
                say(str(e))

        check_btn = tbutton_in(row, 'Check for updates', do_check)
        install_btn = tbutton_in(row, 'Install update', do_install)
        install_btn.config(state='disabled')
        for b in (check_btn, install_btn, tbutton_in(row, 'Roll back', do_rollback)):
            b.pack(side='left', padx=(0, 8))
        header()
        poll()

    def tbutton_in(parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd, bg='#04200f', fg=TXT, activebackground=TXT, activeforeground='#00210c', disabledforeground='#1f6a3a',
                         relief='flat', bd=0, highlightthickness=1, highlightbackground=DIM, font=FONT, cursor='hand2', padx=10, pady=4)

    def do_uninstall():
        import subprocess
        c = cur_cfg()
        ps1 = os.path.join(c['workdir'], 'install-output.ps1')
        if not os.path.isfile(ps1):
            messagebox.showinfo(cb.APP, 'Nothing to uninstall: no installed build was found in the work folder:' + chr(10) + c['workdir'])
            return
        base = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1, '-Uninstall']

        def work():
            try:
                pre = subprocess.run(base + ['-DryRun'], capture_output=True, text=True, creationflags=cb.NOWIN).stdout
                q.put(('ask_uninstall', (base, pre)))
            except Exception as e:
                q.put(('log', 'ERROR: %s' % e))
        threading.Thread(target=work, daemon=True).start()

    def uninstall_confirmed(base, pre):
        lines = [l for l in pre.splitlines() if 'would' in l.lower() or 'files' in l.lower()]
        summary = chr(10).join(lines[-4:]) or 'The files listed in installed-files.txt will be removed.'
        if not messagebox.askyesno(cb.APP, 'Remove the installed files from Fallout 4?' + chr(10) + chr(10) + summary + chr(10) + chr(10) +
                                   'Only files this program installed are removed; replaced files are put back. Close Fallout 4 first.'):
            return

        def work():
            r = subprocess.run(base, capture_output=True, text=True, creationflags=cb.NOWIN)
            for ln in r.stdout.splitlines():
                q.put(('log', ln))
            q.put(('log', 'Uninstall finished (exit %d).' % r.returncode))
            q.put(('refresh', None))
        import subprocess
        threading.Thread(target=work, daemon=True).start()

    build_btn = tbutton('[ INSTALL / RESUME ]', go, big=True)
    place(build_btn, 'bottom', 16, 66, 290, 48)
    place(tbutton('Re-check', refresh), 'bottom', 322, 76, 100, 30)
    stop_btn = tbutton('Stop after this step', lambda: stop.update(v=True))
    stop_btn.config(state='disabled')
    place(stop_btn, 'bottom', 432, 76, 170, 30)
    place(tbutton('Uninstall', do_uninstall), 'bottom', 612, 76, 100, 30)
    place(tbutton('Updates', show_updates), 'bottom', 782, 76, 96, 30)
    place(tbutton('Credits', show_credits), 'bottom', 890, 76, 92, 30)
    cv.create_text(bx + 970, by + 42, text='Progress is saved; reopen to resume.', anchor='e', fill=DIM, font=MONO)
    refresh()
    pump()
    tick()
    root.mainloop()
    return 0
