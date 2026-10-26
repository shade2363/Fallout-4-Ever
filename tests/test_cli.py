"""Tests of the command line of CapitalConvert.exe (no game needed): real help, nothing is started by --help, mistakes are refused.

  python -m unittest tests.test_cli -v
"""
import contextlib, io, os, subprocess, sys, tempfile, unittest, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'builder'))
import capital_builder as cb


def parse(argv):
    """-> (result dict or None, exit code or None, stdout text, stderr text)"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            return cb.parse(argv), None, out.getvalue(), err.getvalue()
        except SystemExit as e:
            return None, e.code, out.getvalue(), err.getvalue()


class HelpTests(unittest.TestCase):
    def test_plain_help_prints_the_commands_and_exits_zero(self):
        for argv in (['--help'], ['-h'], ['/?'], ['-?'], ['help']):
            res, code, out, _ = parse(argv)
            self.assertEqual(code, 0, argv)
            self.assertIsNone(res)
            for word in ('detect', 'plan', 'build', 'status', 'uninstall', 'update-check', 'update-rollback'):
                self.assertIn(word, out, argv)

    def test_uninstall_help_is_help_not_an_uninstall(self):
        for argv in (['uninstall', '--help'], ['uninstall', '-h'], ['help', 'uninstall']):
            res, code, out, _ = parse(argv)
            self.assertEqual(code, 0, argv)
            self.assertIsNone(res)                       # parse never returns a command to run
            self.assertIn('uninstall', out)
            self.assertIn('--yes', out)

    def test_build_help_names_its_options(self):
        _, code, out, _ = parse(['help', 'build'])
        self.assertEqual(code, 0)
        for opt in ('--from', '--only', '--to', '--workdir', '--fo4', '--fo3', '--yes', '--keep-other-plugins', '--no-special-screen'):
            self.assertIn(opt, out)

    def test_version(self):
        _, code, out, _ = parse(['--version'])
        self.assertEqual(code, 0)
        self.assertIn(cb.VERSION, out)

    def test_a_mistake_is_refused_with_exit_2_and_nothing_runs(self):
        for argv in (['uninstall', '--hlep'], ['bild'], ['build', '--from'], ['detect', '--yes'], ['status', '--fo4', 'x']):
            res, code, _, err = parse(argv)
            self.assertEqual(code, 2, argv)
            self.assertIsNone(res)
            self.assertIn('usage:', err)


class ParseTests(unittest.TestCase):
    def test_no_arguments_means_the_window(self):
        res, code, _, _ = parse([])
        self.assertIsNone(code)
        self.assertIsNone(res['cmd'])
        self.assertFalse(res['yes'])

    def test_build_options(self):
        res, _, _, _ = parse(['build', '--from', '02-assets', '--only', '16-start', '--to', '18-install', '--workdir', 'D:\\w', '--fo4', 'D:\\fo4', '--fo3', 'D:\\fo3\\Data', '--yes'])
        self.assertEqual((res['cmd'], res['from'], res['only'], res['to'], res['workdir'], res['fo4'], res['fo3'], res['yes']),
                         ('build', '02-assets', '16-start', '18-install', 'D:\\w', 'D:\\fo4', 'D:\\fo3\\Data', True))

    def test_the_two_user_options_are_tri_state(self):
        res, _, _, _ = parse(['build'])
        self.assertNotIn('keep_other_plugins', res)           # not given: the saved choice stays
        self.assertNotIn('special_screen', res)
        res, _, _, _ = parse(['build', '--keep-other-plugins', '--no-special-screen'])
        self.assertIs(res['keep_other_plugins'], True)
        self.assertIs(res['special_screen'], False)
        res, _, _, _ = parse(['build', '--no-keep-other-plugins', '--special-screen'])
        self.assertIs(res['keep_other_plugins'], False)
        self.assertIs(res['special_screen'], True)

    def test_the_options_are_saved_in_the_config(self):
        cfg = cb.resolve_config({'workdir': 'W', 'fo4': 'F4', 'fo3': 'F3', 'keep_other_plugins': True, 'special_screen': False}, {})
        self.assertIs(cfg['merge_plugins'], True)
        self.assertEqual(cfg['start_special'], 'default')
        later = cb.resolve_config({'workdir': 'W', 'fo4': 'F4', 'fo3': 'F3'}, {'config': cfg})          # a later run without the flags keeps them
        self.assertIs(later['merge_plugins'], True)
        self.assertEqual(later['start_special'], 'default')

    def test_an_option_change_reruns_the_stage_that_uses_it(self):
        wd = tempfile.mkdtemp()
        try:
            by_id = {s['id']: s for s in cb.STAGES}
            base = {s['id']: cb.stage_hash(s, wd, {}) for s in cb.STAGES}
            self.assertEqual(base, {s['id']: cb.stage_hash(s, wd) for s in cb.STAGES})            # no config: as before
            self.assertNotEqual(base['16-start'], cb.stage_hash(by_id['16-start'], wd, {'start_special': 'default'}))
            self.assertNotEqual(base['18-install'], cb.stage_hash(by_id['18-install'], wd, {'merge_plugins': True}))
            self.assertEqual(base['10-navmesh'], cb.stage_hash(by_id['10-navmesh'], wd, {'start_special': 'default', 'merge_plugins': True}))
            self.assertEqual(base['16-start'], cb.stage_hash(by_id['16-start'], wd, {'start_special': 'screen'}))          # the default is no change
        finally:
            shutil.rmtree(wd, ignore_errors=True)


class ProcessTests(unittest.TestCase):
    """the real entry point, as a separate process"""

    def run_cli(self, *args):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        env = dict(os.environ, LOCALAPPDATA=tmp)
        return subprocess.run([sys.executable, os.path.join(ROOT, 'builder', 'capital_builder.py')] + list(args), capture_output=True, text=True, timeout=120, env=env), tmp

    def test_uninstall_help_runs_nothing(self):
        r, tmp = self.run_cli('uninstall', '--help')
        self.assertEqual(r.returncode, 0)
        self.assertIn('usage: CapitalConvert uninstall', r.stdout)
        self.assertNotIn('nothing to uninstall', r.stdout)
        self.assertNotIn('preview', r.stdout)
        self.assertEqual(os.listdir(tmp), [])                    # no work folder, no log, no crash.log

    def test_plain_help_does_not_open_the_window(self):
        r, _ = self.run_cli('--help')
        self.assertEqual(r.returncode, 0)
        self.assertIn('commands:', r.stdout)

    def test_script_mode_accepts_the_options_of_a_python_call(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        script = os.path.join(tmp, 'show.py')
        with open(script, 'w') as f:
            f.write('import sys\nprint("ARGS", sys.argv[1:])\n')
        for opts in ([], ['-I'], ['-I', '-B']):
            r = subprocess.run([sys.executable, os.path.join(ROOT, 'builder', 'capital_builder.py'), '--script'] + opts + [script, 'a', '--b'], capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("ARGS ['a', '--b']", r.stdout)


class ShimTests(unittest.TestCase):
    def test_python_shim_runs_a_plain_python_call_through_the_program(self):
        wd = tempfile.mkdtemp()
        try:
            d = cb.python_shim(wd)
            with open(os.path.join(d, 'python.cmd'), encoding='ascii', newline='') as f:
                text = f.read()
            self.assertIn('"%CAPITAL_PY%" --script %*', text)
            self.assertEqual(cb.python_shim(wd), d)             # idempotent
        finally:
            shutil.rmtree(wd, ignore_errors=True)

    def test_script_env_only_changes_the_path_for_the_packaged_program(self):
        env = cb.script_env({'workdir': tempfile.gettempdir()})
        self.assertEqual(env['CAPITAL_PY'], sys.executable)
        self.assertEqual(env['CAPITAL_PY_ARGS'], '')
        self.assertNotIn('PATH', env)                           # a source run uses the python on the PATH
        self.assertNotIn('CAPITAL_MERGE_PLUGINS', env)
        self.assertEqual(cb.script_env({'workdir': tempfile.gettempdir(), 'merge_plugins': True})['CAPITAL_MERGE_PLUGINS'], '1')


if __name__ == '__main__':
    unittest.main()
