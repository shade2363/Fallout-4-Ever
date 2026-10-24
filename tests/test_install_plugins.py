"""Tests of install-output.ps1 on a throw-away sandbox (its -Sandbox switch redirects Data, plugins.txt, the ini files and the backups into a temp folder; no game is touched):
the plugin list is a clean one that keeps the earlier list safe, the uninstall puts it back, the loose-file message is only printed when there are loose files.

  python -m unittest tests.test_install_plugins -v          (Windows PowerShell 5.1 or newer)
"""
import os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'install-output.ps1')
HEADER = '# This file is used by Fallout4 to keep track of your downloaded content.'


def have_powershell():
    try:
        return subprocess.run(['powershell', '-NoProfile', '-Command', 'exit 0'], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@unittest.skipUnless(os.name == 'nt' and have_powershell(), 'needs Windows PowerShell')
class InstallPluginsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.out = os.path.join(self.tmp, 'output')
        os.makedirs(self.out)
        for n in ('Fallout3.esm', 'CapitalActors.esp', 'Fallout3 - Main.ba2'):
            with open(os.path.join(self.out, n), 'wb') as f:
                f.write(b'x' * 64)
        self.fo3 = os.path.join(self.tmp, 'fo3data')                    # an empty Data folder: no Fallout 3 videos to copy
        os.makedirs(self.fo3)
        self.sb = os.path.join(self.tmp, 'sandbox')
        self.pl_dir = os.path.join(self.sb, 'LocalAppData', 'Fallout4')
        os.makedirs(self.pl_dir)
        self.plugins = os.path.join(self.pl_dir, 'plugins.txt')
        self.prefs = os.path.join(self.sb, 'MyGames', 'Fallout4Prefs.ini')
        os.makedirs(os.path.dirname(self.prefs))
        with open(self.prefs, 'w') as f:
            f.write('[Launcher]\r\nbEnableFileSelection=0\r\n')
        self.seed(['*FNV_Test.esp', 'Other.esp'])

    def seed(self, lines):
        with open(self.plugins, 'w', encoding='ascii', newline='') as f:
            f.write('\r\n'.join([HEADER] + lines) + '\r\n')

    def lines(self):
        with open(self.plugins, encoding='ascii') as f:
            return [l.strip() for l in f if l.strip()]

    def run_ps(self, *extra, uninstall=False, env=None):
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', SCRIPT, '-Sandbox', self.sb, '-OutDir', self.out, '-Fo3Data', self.fo3]
        if uninstall:
            cmd.append('-Uninstall')
        r = subprocess.run(cmd + list(extra), capture_output=True, text=True, timeout=300, env=dict(os.environ, **(env or {})))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def backups(self):
        d = os.path.join(self.sb, 'backup')
        return sorted(n for n in os.listdir(d) if n.startswith('plugins.txt.pre-capital')) if os.path.isdir(d) else []

    # ---- install
    def test_the_default_is_a_clean_list_and_the_old_one_is_saved(self):
        text = self.run_ps()
        self.assertEqual(self.lines(), [HEADER, '*Fallout3.esm', '*CapitalActors.esp'])
        self.assertEqual(self.backups(), ['plugins.txt.pre-capital'])
        with open(os.path.join(self.sb, 'backup', 'plugins.txt.pre-capital'), encoding='ascii') as f:
            self.assertIn('*FNV_Test.esp', f.read())
        self.assertIn('NOT enabled now', text)                                    # the user is told
        self.assertIn('Changed outside Fallout 4', text)
        self.assertIn('bEnableFileSelection=1', text)

    def test_merge_keeps_the_other_plugins(self):
        text = self.run_ps('-MergePlugins')
        self.assertEqual(self.lines(), [HEADER, '*FNV_Test.esp', 'Other.esp', '*Fallout3.esm', '*CapitalActors.esp'])
        self.assertIn('kept your 2 other plugin', text)

    def test_merge_can_come_from_the_environment_the_builder_sets(self):
        self.run_ps(env={'CAPITAL_MERGE_PLUGINS': '1'})
        self.assertIn('*FNV_Test.esp', self.lines())

    def test_installing_again_keeps_the_original_backup(self):
        self.run_ps()
        self.run_ps()
        self.assertEqual(self.lines(), [HEADER, '*Fallout3.esm', '*CapitalActors.esp'])
        self.assertEqual(self.backups(), ['plugins.txt.pre-capital'])              # the second run had nothing of the user's to save
        with open(os.path.join(self.sb, 'backup', 'plugins.txt.pre-capital'), encoding='ascii') as f:
            self.assertIn('*FNV_Test.esp', f.read())

    def test_a_list_the_user_rebuilt_since_is_saved_too(self):
        self.run_ps()
        self.seed(['*Another.esp', '*Fallout3.esm', '*CapitalActors.esp'])
        self.run_ps()
        self.assertEqual(self.lines(), [HEADER, '*Fallout3.esm', '*CapitalActors.esp'])
        self.assertEqual(len(self.backups()), 2)

    def test_dry_run_writes_nothing(self):
        text = self.run_ps('-DryRun')
        self.assertIn('would write plugins.txt', text)
        self.assertIn('saved to', text)
        self.assertEqual(self.lines(), [HEADER, '*FNV_Test.esp', 'Other.esp'])
        self.assertEqual(self.backups(), [])

    def test_no_loose_file_message_when_nothing_is_loose(self):
        self.assertNotIn('as loose files', self.run_ps())                          # the demo's textures are in .ba2 archives: the old message was wrong

    def test_loose_textures_are_announced(self):
        tex = os.path.join(self.out, 'loose', 'textures', 'Capital')
        os.makedirs(tex)
        with open(os.path.join(tex, 'a.dds'), 'wb') as f:
            f.write(b'x')
        self.assertIn('Installing 1 textures / faces / materials as loose files', self.run_ps())

    # ---- uninstall
    def test_uninstall_puts_the_earlier_list_back(self):
        self.run_ps()
        text = self.run_ps(uninstall=True)
        self.assertEqual(self.lines(), [HEADER, '*FNV_Test.esp', 'Other.esp'])
        self.assertIn('putting back your earlier list', text)
        self.assertFalse(os.path.exists(os.path.join(self.sb, 'Data', 'Fallout3.esm')))

    def test_uninstall_keeps_what_was_added_since(self):
        self.run_ps()
        self.seed(['*Fallout3.esm', '*CapitalActors.esp', '*Added.esp'])
        self.run_ps(uninstall=True)
        self.assertEqual(self.lines(), [HEADER, '*FNV_Test.esp', 'Other.esp', '*Added.esp'])

    def test_uninstall_after_a_merge_install_only_removes_ours(self):
        self.run_ps('-MergePlugins')
        self.run_ps(uninstall=True)
        self.assertEqual(self.lines(), [HEADER, '*FNV_Test.esp', 'Other.esp'])

    def test_uninstall_dry_run_changes_nothing(self):
        self.run_ps()
        before = self.lines()
        text = self.run_ps('-DryRun', uninstall=True)
        self.assertIn('putting back your earlier list', text)
        self.assertEqual(self.lines(), before)

    def test_the_ini_edit_is_still_undone(self):
        self.run_ps()
        with open(self.prefs) as f:
            self.assertIn('bEnableFileSelection=1', f.read())
        self.run_ps(uninstall=True)
        with open(self.prefs) as f:
            self.assertIn('bEnableFileSelection=0', f.read())


class ScriptTextTests(unittest.TestCase):
    def test_no_plain_python_call_is_left_in_the_install_step(self):
        # a PC with only the packaged program has no python on the PATH: the install used to stop there
        with open(SCRIPT, encoding='utf-8') as f:
            src = f.read()
        for line in src.splitlines():
            code = line.split('#')[0]
            self.assertNotRegex(code, r'&\s*python\b', line)
        self.assertIn('Invoke-CapitalPy', src)


if __name__ == '__main__':
    unittest.main()
