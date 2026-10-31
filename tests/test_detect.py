"""Detection tests on fake game folders (no real games needed): Steam-style libraries, odd folder names, Epic manifests, drive scan, bad folders.

  python -m unittest discover -s tests -v
"""
import json, os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'builder'))
import detect


def touch(*parts):
    p = os.path.join(*parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(b'x')
    return p


def make_fo4(root):
    touch(root, 'Fallout4.exe')
    touch(root, 'Data', 'Fallout4.esm')
    touch(root, 'Tools', 'Archive2', 'Archive2.exe')
    touch(root, 'Tools', 'Elric', 'Elrich.exe')
    touch(root, 'CreationKit.exe')
    touch(root, 'Papyrus Compiler', 'PapyrusCompiler.exe')
    return root


def make_fo3(root, dlc=True, archives=True):
    d = os.path.join(root, 'Data')
    touch(d, 'Fallout3.esm')
    if archives:
        for b in ('Fallout - Meshes.bsa', 'Fallout - Textures.bsa', 'Fallout - Misc.bsa', 'Fallout - Sound.bsa', 'Fallout - Voices.bsa'):
            touch(d, b)
    if dlc:
        for n in detect.FO3_DLC:
            touch(d, n + '.esm')
    return d


class DetectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for k in ('FO4_DIR', 'FO3_DATA'):
            os.environ.pop(k, None)
        self.saved = (detect.steam_libraries, detect._bethesda_reg, detect.gog_paths, detect.epic_paths)     # isolate from the games installed on this PC
        detect.steam_libraries = lambda: []
        detect._bethesda_reg = lambda name: None
        detect.gog_paths = lambda reg_root=None: []
        detect.epic_paths = lambda manifest_dir=None: []

    def tearDown(self):
        detect.steam_libraries, detect._bethesda_reg, detect.gog_paths, detect.epic_paths = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_env_override_wins(self):
        fo4 = make_fo4(os.path.join(self.tmp, 'my games', "Fallout 4 (it's here)"))
        os.environ['FO4_DIR'] = fo4
        self.assertEqual(detect.find_fo4(), fo4)

    def test_folder_with_spaces_apostrophe_and_unicode(self):
        fo3 = make_fo3(os.path.join(self.tmp, 'Jeux \u00e9t\u00e9', "Fallout 3 goty - Bob's copy"))
        self.assertEqual(detect.find_fo3_data(extra=[fo3]), fo3)

    def test_invalid_folders_are_rejected(self):
        empty = os.path.join(self.tmp, 'Fallout 4')
        os.makedirs(os.path.join(empty, 'Data'))
        touch(empty, 'Data', 'Fallout4.esm')                    # no Fallout4.exe
        self.assertIsNone(detect.find_fo4(extra=[empty]))
        fo3 = os.path.join(self.tmp, 'Fallout 3', 'Data')
        touch(fo3, 'Fallout3.esm')                              # no archives
        self.assertIsNone(detect.find_fo3_data(extra=[fo3]))

    def test_drive_scan_finds_a_game_installed_anywhere(self):
        deep = make_fo3(os.path.join(self.tmp, 'Games', 'Stuff', 'Fallout 3 GOTY'))
        self.assertIsNone(detect.find_fo3_data(extra=[], scan=False))
        hit = detect.find_fo3_data(extra=[], scan=[self.tmp])
        self.assertIsNotNone(hit)
        self.assertEqual(os.path.normcase(hit), os.path.normcase(deep))

    def test_scan_depth_is_limited(self):
        make_fo3(os.path.join(self.tmp, 'a', 'b', 'c', 'd', 'e', 'f', 'Fallout 3'))
        self.assertEqual(detect.scan_roots(['Fallout 3'], [self.tmp], max_depth=3), [])
        self.assertEqual(len(detect.scan_roots(['Fallout 3'], [self.tmp], max_depth=8)), 1)

    def test_epic_manifest_is_read(self):
        man = os.path.join(self.tmp, 'Manifests')
        os.makedirs(man)
        with open(os.path.join(man, 'abc.item'), 'w', encoding='utf-8') as f:
            json.dump({'DisplayName': 'Fallout 3: Game of the Year Edition', 'InstallLocation': os.path.join(self.tmp, 'Epic', 'Fallout3')}, f)
        with open(os.path.join(man, 'broken.item'), 'w') as f:
            f.write('{not json')
        got = self.saved[3](man)
        self.assertEqual(len(got), 1)
        self.assertIn('Fallout 3', got[0][0])

    def test_inspect_reports_missing_pieces(self):
        fo4 = os.path.join(self.tmp, 'fo4')
        touch(fo4, 'Fallout4.exe')
        touch(fo4, 'Data', 'Fallout4.esm')
        fo3 = make_fo3(os.path.join(self.tmp, 'fo3'), dlc=False)
        facts, problems = detect.inspect_install(fo4, fo3)
        msgs = ' '.join(m for _, m in problems)
        self.assertIn('Archive2', msgs)
        self.assertIn('Elrich', msgs)
        self.assertIn('DLC missing', msgs)
        self.assertTrue(any(lv == 'error' for lv, _ in problems))

    def test_inspect_clean_install_has_no_errors(self):
        fo4 = make_fo4(os.path.join(self.tmp, 'fo4'))
        fo3 = make_fo3(os.path.join(self.tmp, 'fo3'))
        facts, problems = detect.inspect_install(fo4, fo3)
        self.assertFalse([p for p in problems if p[0] == 'error'], problems)

    def test_nothing_found_gives_clear_errors(self):
        facts, problems = detect.inspect_install(None, None)
        self.assertEqual(len([p for p in problems if p[0] == 'error']), 2)

    # ---- a game window larger than the screen: the SPECIAL screen's Done button is off screen and the player stays stuck behind it
    def prefs(self, w, h, full=0, borderless=1):
        p = os.path.join(self.tmp, 'Fallout4Prefs.ini')
        with open(p, 'w') as f:
            f.write('[Display]\r\niSize H=%d\r\nbFull Screen=%d\r\niSize W=%d\r\nbBorderless=%d\r\n[Launcher]\r\nbEnableFileSelection=0\r\n' % (h, full, w, borderless))
        return p

    def test_window_larger_than_the_screen_is_a_warning(self):
        msg = detect.oversize_window_warning(self.prefs(2560, 1440), (1920, 1080))
        self.assertIn('2560x1440', msg)
        self.assertIn('1920x1080', msg)
        self.assertIn('SPECIAL', msg)
        self.assertIn('--no-special-screen', msg)

    def test_a_window_that_fits_is_no_problem(self):
        self.assertIsNone(detect.oversize_window_warning(self.prefs(1920, 1080), (1920, 1080)))
        self.assertIsNone(detect.oversize_window_warning(self.prefs(1280, 720), (2560, 1440)))

    def test_only_one_side_too_big_is_enough(self):
        self.assertIsNotNone(detect.oversize_window_warning(self.prefs(1920, 1200), (1920, 1080)))
        self.assertIsNotNone(detect.oversize_window_warning(self.prefs(2560, 1080), (1920, 1080)))

    def test_full_screen_picks_a_mode_the_screen_supports(self):
        self.assertIsNone(detect.oversize_window_warning(self.prefs(2560, 1440, full=1), (1920, 1080)))

    # ---- a screen above 60 Hz lets Fallout 4 draw more than 60 fps, and above 60 fps its world runs faster than real time
    def test_a_fast_screen_is_a_warning_with_the_fix(self):
        for hz in (62, 75, 120, 144, 165, 240):
            msg = detect.fast_screen_warning(hz)
            self.assertIn('%d Hz' % hz, msg)
            self.assertIn('60 fps', msg)
            self.assertIn('Time runs too fast', msg)
            self.assertLess(len(msg), 260)                                          # the CHECKS panel of the window is small: one short paragraph

    def test_a_60_hz_screen_is_no_problem(self):
        for hz in (30, 59, 60, 61, 0):
            self.assertIsNone(detect.fast_screen_warning(hz))

    def test_without_an_argument_it_asks_windows(self):
        real = detect.refresh_rate_hz
        try:
            detect.refresh_rate_hz = lambda: 144
            self.assertIn('144 Hz', detect.fast_screen_warning())
            detect.refresh_rate_hz = lambda: None
            self.assertIsNone(detect.fast_screen_warning())
        finally:
            detect.refresh_rate_hz = real

    def test_a_fast_screen_reaches_the_checks_panel(self):
        import capital_builder as cb
        real = detect.fast_screen_warning
        detect.fast_screen_warning = lambda hz=None: 'FAST SCREEN TEST'
        try:
            facts, problems = cb.preflight({'fo4': None, 'fo3_data': None, 'workdir': self.tmp})
        finally:
            detect.fast_screen_warning = real
        self.assertIn(('warn', 'FAST SCREEN TEST'), problems)

    def test_the_windows_structure_has_the_documented_layout(self):
        import ctypes
        self.assertEqual(ctypes.sizeof(detect.DEVMODEW), 220)                      # the size Windows documents for DEVMODEW
        self.assertEqual(detect.DEVMODEW.dmPelsWidth.offset, 172)
        self.assertEqual(detect.DEVMODEW.dmDisplayFrequency.offset, 184)

    def test_the_refresh_rate_is_a_sane_number_or_none(self):
        hz = detect.refresh_rate_hz()
        self.assertTrue(hz is None or 20 <= hz <= 1000, hz)

    def test_no_prefs_file_or_no_screen_size_is_silent(self):
        self.assertIsNone(detect.oversize_window_warning(os.path.join(self.tmp, 'missing.ini'), (1920, 1080)))
        self.assertIsNone(detect.oversize_window_warning(self.prefs(2560, 1440), None) if detect.desktop_size() is None else None)
        with open(os.path.join(self.tmp, 'bad.ini'), 'w') as f:
            f.write('[Display]\r\niSize W=wide\r\n')
        self.assertIsNone(detect.oversize_window_warning(os.path.join(self.tmp, 'bad.ini'), (1920, 1080)))


if __name__ == '__main__':
    unittest.main()
