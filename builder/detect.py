"""Find Fallout 3 / Fallout 4 installs (Steam libraries, Bethesda registry keys, common folders) and validate them."""
import os, re, shutil, sys

FO3_DLC = ['Anchorage', 'ThePitt', 'BrokenSteel', 'PointLookout', 'Zeta']


def _winreg():
    try:
        import winreg
        return winreg
    except ImportError:
        return None


def steam_libraries():
    wr = _winreg()
    steam = None
    if wr:
        for hive, key, val in ((wr.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                               (wr.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath'),
                               (wr.HKEY_LOCAL_MACHINE, r'SOFTWARE\Valve\Steam', 'InstallPath')):
            try:
                with wr.OpenKey(hive, key) as k:
                    steam = wr.QueryValueEx(k, val)[0]
                    break
            except OSError:
                pass
    cands = [steam] if steam else []
    for d in (r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam'):
        if os.path.isdir(d):
            cands.append(d)
    libs = []
    for s in cands:
        s = s.replace('/', '\\')
        libs.append(s)
        vdf = os.path.join(s, 'steamapps', 'libraryfolders.vdf')
        if os.path.exists(vdf):
            txt = open(vdf, encoding='utf-8', errors='replace').read()
            libs += [m.replace('\\\\', '\\') for m in re.findall(r'"path"\s+"([^"]+)"', txt)]
    out = []
    for l in libs:
        if l.lower() not in [o.lower() for o in out] and os.path.isdir(l):
            out.append(l)
    return out


def _bethesda_reg(name):
    wr = _winreg()
    if not wr:
        return None
    for view in (wr.KEY_WOW64_32KEY, wr.KEY_WOW64_64KEY):
        try:
            with wr.OpenKey(wr.HKEY_LOCAL_MACHINE, r'SOFTWARE\Bethesda Softworks\%s' % name, 0, wr.KEY_READ | view) as k:
                return wr.QueryValueEx(k, 'installed path')[0]
        except OSError:
            pass
    return None


def _file_version(path):
    """Windows file version (a.b.c.d) of an exe, or None"""
    try:
        import ctypes
        from ctypes import wintypes
        size = ctypes.windll.version.GetFileVersionInfoSizeW(path, None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        ctypes.windll.version.GetFileVersionInfoW(path, 0, size, buf)
        p = ctypes.c_void_p()
        n = wintypes.UINT()
        if not ctypes.windll.version.VerQueryValueW(buf, '\\', ctypes.byref(p), ctypes.byref(n)):
            return None
        v = (wintypes.DWORD * 13).from_address(p.value)
        return '%d.%d.%d.%d' % (v[4] >> 16, v[4] & 0xffff, v[5] >> 16, v[5] & 0xffff)
    except Exception:
        return None


def gog_paths(reg_root=None):
    """install folders of GOG games from the registry key SOFTWARE/WOW6432Node/GOG.com/Games/<id> (the Fallout 3 GOTY is on GOG)"""
    wr = _winreg()
    out = []
    if not wr:
        return out
    try:
        base = wr.OpenKey(wr.HKEY_LOCAL_MACHINE, reg_root or r'SOFTWARE\WOW6432Node\GOG.com\Games', 0, wr.KEY_READ | wr.KEY_WOW64_64KEY)
    except OSError:
        return out
    i = 0
    while True:
        try:
            sub = wr.EnumKey(base, i)
        except OSError:
            break
        i += 1
        try:
            with wr.OpenKey(base, sub) as k:
                out.append(wr.QueryValueEx(k, 'path')[0])
        except OSError:
            pass
    return out


def epic_paths(manifest_dir=None):
    """InstallLocation of every Epic Games Store install (the .item files under ProgramData/Epic/EpicGamesLauncher/Data/Manifests)"""
    import json
    d = manifest_dir or os.path.join(os.environ.get('ProgramData', r'C:\ProgramData'), 'Epic', 'EpicGamesLauncher', 'Data', 'Manifests')
    out = []
    if os.path.isdir(d):
        for n in os.listdir(d):
            if n.lower().endswith('.item'):
                try:
                    j = json.load(open(os.path.join(d, n), encoding='utf-8'))
                    if j.get('InstallLocation'):
                        out.append((j.get('DisplayName', ''), j['InstallLocation']))
                except (OSError, ValueError):
                    pass
    return out


def fixed_drives():
    try:
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        out = []
        for i in range(26):
            if mask & (1 << i):
                root = '%s:' % chr(65 + i) + chr(92)
                if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:         # DRIVE_FIXED
                    out.append(root)
        return out
    except Exception:
        return []


def scan_roots(names, roots, max_depth=4, seconds=20):
    """folders called one of `names` (case-insensitive) below the given roots, at most max_depth levels down; stops after `seconds`"""
    import time
    want = {n.lower() for n in names}
    skip = {'windows', '$recycle.bin', 'system volume information', 'node_modules', '.git', 'appdata', 'winsxs', 'drivers'}
    end = time.time() + seconds
    found = []
    stack = [(r, 0) for r in roots]
    while stack and time.time() < end:
        d, depth = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    if not e.is_dir(follow_symlinks=False):
                        continue
                    n = e.name.lower()
                    if n in want:
                        found.append(e.path)
                    elif depth < max_depth and n not in skip:
                        stack.append((e.path, depth + 1))
        except OSError:
            continue
    return found


def _fo4_candidates(extra, scan):
    cands = [os.environ.get('FO4_DIR')] + list(extra)
    r = _bethesda_reg('Fallout4')
    if r:
        cands.append(r)
    for l in steam_libraries():
        cands.append(os.path.join(l, 'steamapps', 'common', 'Fallout 4'))
    for name, loc in epic_paths():
        if 'fallout 4' in name.lower():
            cands.append(loc)
    if scan:
        cands += scan_roots(['Fallout 4', 'Fallout4'], scan if isinstance(scan, (list, tuple)) else fixed_drives())
    return cands


def _fo3_candidates(extra, scan):
    cands = [os.environ.get('FO3_DATA')] + list(extra)
    r = _bethesda_reg('fallout3')
    if r:
        cands.append(os.path.join(r, 'Data'))
    for l in steam_libraries():
        for n in ('Fallout 3 goty', 'Fallout 3'):
            cands.append(os.path.join(l, 'steamapps', 'common', n, 'Data'))
    for g in gog_paths():
        cands.append(os.path.join(g, 'Data'))
    for name, loc in epic_paths():
        if 'fallout 3' in name.lower():
            cands.append(os.path.join(loc, 'Data'))
    if scan:
        for f in scan_roots(['Fallout 3 goty', 'Fallout 3', 'Fallout3', 'Fallout 3 GOTY'], scan if isinstance(scan, (list, tuple)) else fixed_drives()):
            cands += [os.path.join(f, 'Data'), f]
    return cands


def valid_fo4(path):
    return bool(path) and os.path.isfile(os.path.join(path, 'Data', 'Fallout4.esm')) and os.path.isfile(os.path.join(path, 'Fallout4.exe'))


def valid_fo3_data(path):
    return bool(path) and os.path.isfile(os.path.join(path, 'Fallout3.esm')) and os.path.isfile(os.path.join(path, 'Fallout - Meshes.bsa'))


def find_fo4(extra=(), scan=False):
    """first valid Fallout 4 folder: FO4_DIR, Bethesda registry, every Steam library, Epic; with scan=True also a search of the fixed drives"""
    for c in _fo4_candidates(extra, False):
        if valid_fo4(c):
            return c.rstrip('\\/')
    if scan:
        for c in _fo4_candidates(extra, scan):
            if valid_fo4(c):
                return c.rstrip('\\/')
    return None


def find_fo3_data(extra=(), scan=False):
    for c in _fo3_candidates(extra, False):
        if valid_fo3_data(c):
            return c.rstrip('\\/')
    if scan:
        for c in _fo3_candidates(extra, scan):
            if valid_fo3_data(c):
                return c.rstrip('\\/')
    return None


def inspect_install(fo4=None, fo3_data=None):
    """returns (facts dict, [(level, message)]); level 'error' blocks the build"""
    facts, problems = {}, []
    if not fo4:
        problems.append(('error', 'Fallout 4 was not found. Install it from Steam (or point the builder at its folder).'))
    else:
        facts['fo4'] = fo4
        exe = os.path.join(fo4, 'Fallout4.exe')
        ver = _file_version(exe) if os.path.exists(exe) else None
        facts['fo4_version'] = ver
        if ver and not ver.startswith('1.11.'):
            problems.append(('warn', 'Fallout 4 version %s: F4SE 0.7.9 and the bundled XDI need 1.11.x (the project was tested on 1.11.240); update the game in Steam.' % ver))
        needs = ((r'Tools\Archive2\Archive2.exe', 'Archive2', 'error'), (r'Tools\Elric\Elrich.exe', 'Elrich', 'error'),
                 ('CreationKit.exe', 'Creation Kit', 'warn'), (r'Papyrus Compiler\PapyrusCompiler.exe', 'Papyrus compiler', 'warn'))
        for rel, what, lvl in needs:
            ok = os.path.exists(os.path.join(fo4, rel))
            facts[what] = ok
            if not ok:
                problems.append((lvl, '%s not found in the Fallout 4 folder (install the free "Fallout 4 Creation Kit" from Steam: it provides it).' % what))
        try:
            t = os.path.join(fo4, 'Data', '.capital_write_test')
            open(t, 'w').close()
            os.remove(t)
            facts['fo4_writable'] = True
        except OSError:
            facts['fo4_writable'] = False
            problems.append(('warn', 'The Fallout 4 Data folder is not writable: run the builder as Administrator for the install step.'))
    if not fo3_data:
        problems.append(('error', 'Fallout 3 was not found. The Steam "Fallout 3 - Game of the Year Edition" (with all 5 DLC) is required.'))
    else:
        facts['fo3_data'] = fo3_data
        have = [d for d in FO3_DLC if os.path.exists(os.path.join(fo3_data, d + '.esm'))]
        facts['fo3_dlc'] = have
        missing = [d for d in FO3_DLC if d not in have]
        if missing:
            problems.append(('warn', 'Fallout 3 DLC missing (%s): those worlds will not be built.' % ', '.join(missing)))
        for b in ('Fallout - Meshes.bsa', 'Fallout - Textures.bsa', 'Fallout - Misc.bsa', 'Fallout - Sound.bsa', 'Fallout - Voices.bsa'):
            if not os.path.exists(os.path.join(fo3_data, b)):
                problems.append(('error', 'Fallout 3 archive missing: %s' % b))
    return facts, problems


def free_gb(path):
    try:
        return shutil.disk_usage(path).free / 1e9
    except OSError:
        return -1


def total_ram_gb():
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [('l', ctypes.c_ulong), ('ml', ctypes.c_ulong), ('tp', ctypes.c_ulonglong), ('ap', ctypes.c_ulonglong),
                        ('tpf', ctypes.c_ulonglong), ('apf', ctypes.c_ulonglong), ('tv', ctypes.c_ulonglong),
                        ('av', ctypes.c_ulonglong), ('ae', ctypes.c_ulonglong)]
        m = MS()
        m.l = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.tp / 1e9
    except Exception:
        return -1


if __name__ == '__main__':
    fo4, fo3 = find_fo4(), find_fo3_data()
    facts, problems = inspect_install(fo4, fo3)
    print(facts)
    for lv, m in problems:
        print(lv.upper(), m)
    print('RAM %.0f GB' % total_ram_gb())
