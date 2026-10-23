"""Tests of the build pipeline's own plumbing (no game needed): log filter, stage dependency check, mesh audit guard, crash handling.

  python -m unittest tests.test_builder -v
"""
import os, re, subprocess, sys, tempfile, unittest, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'builder'))
from logfilter import LogFilter
from stages import STAGES


class LogFilterTests(unittest.TestCase):
    def test_converter_flood_becomes_progress_lines(self):
        raw = os.path.join(tempfile.mkdtemp(), 'raw.log')
        f = LogFilter(raw)
        shown = []
        for i in range(120000):
            shown += f.feed('<00:08:15.358> record %d' % i)
        shown += f.feed('a normal line')
        shown += f.finish()
        self.assertLess(len(shown), 10)
        self.assertIn('a normal line', shown)
        with open(raw, encoding='utf-8') as fh:
            self.assertEqual(sum(1 for _ in fh), 120001)         # the full text still reaches the file
        shutil.rmtree(os.path.dirname(raw), ignore_errors=True)

    def test_extract_progress_is_thinned(self):
        f = LogFilter(None)
        shown = []
        for i in range(1, 2501):
            shown += f.feed('Extracting: %d/2500 - x.nif' % i)
        self.assertLessEqual(len(shown), 5)

    def test_failures_are_counted(self):
        f = LogFilter(None)
        f.feed('<00:00:01.000> mesh FAILED to convert')
        f.feed('<00:00:01.001> ok')
        self.assertIn('1 meshes it could not convert', ' '.join(f.finish()))


class DemoDependencyTests(unittest.TestCase):
    """every file a demo stage requires must be a game file or be produced by an EARLIER demo stage: a stage must never read something the demo does not build"""
    def test_requires_are_produced_earlier(self):
        produced = set()
        for st in STAGES:
            for req in st.get('requires', []):
                if req.startswith(('{fo3}', '{fo4}')):
                    continue
                self.assertIn(req, produced, '%s requires %s, which no earlier demo stage produces' % (st['id'], req))
            produced.update(st.get('produces', []))

    def test_mesh_audit_only_reads_plugins_the_demo_builds_or_skips_missing_ones(self):
        src = open(os.path.join(ROOT, 'worldfix', 'audit_meshes.py'), encoding='utf-8').read()
        self.assertIn('os.path.isfile(plugin)', src)          # CapitalItems.esp is not built by the demo: the audit must skip it, not crash
        self.assertIn('continue', src.split('os.path.isfile(plugin)', 1)[1][:200])

    def test_install_script_has_no_regex_class_broken_over_a_line(self):
        # a character class that contains a real line break behaves differently with LF and CRLF files and silently turned the CRLF ini into an LF one
        src = open(os.path.join(ROOT, 'install-output.ps1'), encoding='utf-8', newline='').read()
        self.assertNotIn('[^' + chr(10) + ']', src)
        self.assertNotIn('[^' + chr(13) + chr(10) + ']', src)

    def test_install_script_does_not_set_a_start_command(self):
        # the demo starts from New Game (CapitalStart.esp); a leftover sStartingConsoleCommand would skip the intro for every later game launch
        src = open(os.path.join(ROOT, 'install-output.ps1'), encoding='utf-8').read()
        self.assertNotIn('sStartingConsoleCommand', src)
        self.assertNotIn('coc MegatonEntrance', src)


class CrashHandlingTests(unittest.TestCase):
    def test_script_crash_exits_nonzero_without_a_dialog(self):
        tmp = tempfile.mkdtemp()
        bad = os.path.join(tmp, 'boom.py')
        with open(bad, 'w') as f:
            f.write('raise FileNotFoundError("nope")\n')
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'builder', 'capital_builder.py'), '--script', bad], capture_output=True, text=True, timeout=60,
                           env=dict(os.environ, LOCALAPPDATA=tmp))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('FileNotFoundError', r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(tmp, 'CapitalConvert', 'crash.log')))
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
