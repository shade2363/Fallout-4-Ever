"""Tests of the plugin conversion step (stage 03) without xConvert: it must be safe to run again after any stop.

A user whose first run stopped after Fallout3 and Anchorage were converted got, on the next run:
    xConvert: "A file of that name exists already." + an access violation, exit code 0
    rename-master.ps1: "Master FalloutNV.esm not found in ...\\Anchorage.esm"
because the DLC output is the final file and was already renamed.  These tests keep that fixed.

  python -m unittest tests.test_convert_plugins -v
"""
import os, shutil, struct, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'builder'))
sys.path.insert(0, os.path.join(ROOT, 'navmesh'))
import steps
from navlib import record, sub, group


def make_plugin(path, masters, groups=3, old=False):
    """a small but structurally complete plugin: TES4 header with the given masters, then a few top-level groups"""
    subs = [sub('HEDR', struct.pack('<fII', 1.0, 0, 0x800))]
    for m in masters:
        subs += [sub('MAST', m.encode() + b'\0'), sub('DATA', bytes(8))]
    data = record('TES4', 0, subs, ver=131) + b''.join(group(('GR%02d' % i).encode(), 0, record('STAT', 0x800 + i, [sub('EDID', b'x\0')], ver=131)) for i in range(groups))
    with open(path, 'wb') as f:
        f.write(data)
    if old:
        os.utime(path, (1000000000, 1000000000))
    return data


def read(path):
    with open(path, 'rb') as f:
        return f.read()


class PluginReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def p(self, name='a.esm'):
        return os.path.join(self.tmp, name)

    def test_masters_are_read_in_order(self):
        make_plugin(self.p(), ['Fallout4.esm', 'FalloutNV.esm'])
        self.assertEqual(steps.plugin_masters(self.p()), ['Fallout4.esm', 'FalloutNV.esm'])

    def test_a_complete_plugin(self):
        make_plugin(self.p(), ['Fallout4.esm'])
        self.assertTrue(steps.plugin_complete(self.p()))

    def test_a_plugin_without_masters_is_still_a_plugin(self):
        make_plugin(self.p(), [])
        self.assertEqual(steps.plugin_masters(self.p()), [])
        self.assertTrue(steps.plugin_complete(self.p()))

    def test_a_cut_short_plugin_is_not_complete(self):
        data = make_plugin(self.p(), ['Fallout4.esm'])
        for keep in (len(data) - 1, len(data) // 2, 30):
            with open(self.p(), 'wb') as f:
                f.write(data[:keep])
            self.assertFalse(steps.plugin_complete(self.p()), keep)

    def test_garbage_and_missing_files(self):
        with open(self.p('junk.esm'), 'wb') as f:
            f.write(b'not a plugin at all, just text')
        self.assertIsNone(steps.plugin_masters(self.p('junk.esm')))
        self.assertFalse(steps.plugin_complete(self.p('junk.esm')))
        self.assertIsNone(steps.plugin_masters(self.p('missing.esm')))
        self.assertFalse(steps.plugin_complete(self.p('missing.esm')))


class ConvertPluginsTests(unittest.TestCase):
    """steps.convert_plugins with fake xConvert / rename-master processes that behave like the real ones, including xConvert's refusal to overwrite"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.wd = os.path.join(self.tmp, 'work')
        self.fo3 = os.path.join(self.tmp, 'fo3data')
        for d in (os.path.join(self.wd, 'lab', 'fnv', 'Data'), os.path.join(self.wd, 'lab', 'Data'), self.fo3):
            os.makedirs(d)
        make_plugin(os.path.join(self.fo3, 'Fallout3.esm'), [], old=True)
        make_plugin(os.path.join(self.fo3, 'Anchorage.esm'), ['Fallout3.esm'], old=True)
        self.cfg = {'workdir': self.wd, 'fo3_data': self.fo3}
        self.calls = []
        self.messages = []
        self.real_run = steps._run
        steps._run = self.fake_run
        self.addCleanup(setattr, steps, '_run', self.real_run)
        self.fail_xconvert = False

    def lab(self, name):
        return os.path.join(self.wd, 'lab', 'Data', name)

    def fake_run(self, cmd, cwd, log, env=None, tolerate=False, collect=None, only=None):
        if os.path.basename(cmd[0]).lower() == 'xconvert.exe':
            arg = cmd[1]
            self.calls.append(('xconvert', arg))
            out = self.lab(arg)
            if self.fail_xconvert:
                lines = ['<00:00:01.000> Unexpected Error: <EAccessViolation: Access violation>']
            elif os.path.exists(out):                                # what the real converter does: refuses, crashes, exits 0
                lines = ['<00:00:10.143> A file of that name exists already.', '<00:00:10.143> Unexpected Error: <EAccessViolation: Access violation>']
            else:
                make_plugin(out, ['Fallout4.esm'] if arg == 'FalloutNV.esm' else ['Fallout4.esm', 'FalloutNV.esm'], groups=5)
                lines = ['<00:00:10.143> All Done.']
            for l in lines:
                if collect is not None and (only is None or any(s in l for s in only)):
                    collect.append(l)
            return 0
        if any(str(c).endswith('rename-master.ps1') for c in cmd):                 # simulate rename-master.ps1 on the plugin's master list
            a = {cmd[i]: cmd[i + 1] for i in range(len(cmd) - 1) if str(cmd[i]).startswith('-')}
            self.calls.append(('rename', os.path.basename(a['-Plugin']), a['-From'], a['-To']))
            masters = steps.plugin_masters(a['-Plugin'])
            if a['-From'] not in masters:
                raise RuntimeError('Master %s not found in %s' % (a['-From'], a['-Plugin']))
            make_plugin(a.get('-Out', a['-Plugin']), [a['-To'] if m == a['-From'] else m for m in masters], groups=5)
            return 0
        raise AssertionError('unexpected command %r' % (cmd,))

    def run_step(self):
        steps.convert_plugins(self.cfg, self.messages.append)

    def kinds(self):
        return [c[0] + ':' + ':'.join(c[1:]) for c in self.calls]

    # ---- the first run
    def test_first_run_converts_and_renames(self):
        self.run_step()
        self.assertEqual(self.kinds(), ['rename:Anchorage.esm:Fallout3.esm:FalloutNV.esm', 'xconvert:FalloutNV.esm', 'xconvert:Anchorage.esm',
                                         'rename:Anchorage.esm:FalloutNV.esm:Fallout3.esm'])
        self.assertEqual(steps.plugin_masters(self.lab('Anchorage.esm')), ['Fallout4.esm', 'Fallout3.esm'])
        self.assertTrue(os.path.isfile(self.lab('Fallout3.esm')))

    # ---- running it again (the failing report)
    def test_a_second_run_after_a_finished_one_does_nothing_and_does_not_fail(self):
        self.run_step()
        self.calls.clear()
        self.run_step()                                                           # used to: xConvert refuses to overwrite, then "Master FalloutNV.esm not found"
        self.assertEqual([c for c in self.kinds() if c.startswith('xconvert')], [])
        self.assertEqual([c for c in self.kinds() if c.startswith('rename') and 'FalloutNV.esm:Fallout3.esm' in c], [])
        self.assertTrue(any('not converting again' in m for m in self.messages))
        self.assertTrue(any('nothing to rename' in m for m in self.messages))
        self.assertEqual(steps.plugin_masters(self.lab('Anchorage.esm')), ['Fallout4.esm', 'Fallout3.esm'])

    def test_run_three_times_in_a_row(self):
        for _ in range(3):
            self.run_step()
        self.assertEqual(sum(1 for c in self.kinds() if c.startswith('xconvert')), 2)       # each plugin converted exactly once

    def test_the_patched_input_being_newer_than_the_output_does_not_force_a_reconversion(self):
        self.run_step()
        self.calls.clear()
        for n in ('FalloutNV.esm', 'Anchorage.esm'):                                  # every run rewrites the patched copies that xConvert reads
            os.utime(os.path.join(self.wd, 'lab', 'fnv', 'Data', n), None)
        self.run_step()
        self.assertEqual([c for c in self.kinds() if c.startswith('xconvert')], [])

    # ---- outputs that are not finished
    def test_a_cut_short_output_is_removed_and_converted_again(self):
        self.run_step()
        self.calls.clear()
        data = read(self.lab('Anchorage.esm'))
        with open(self.lab('Anchorage.esm'), 'wb') as f:
            f.write(data[:len(data) // 2])
        self.run_step()
        self.assertEqual([c for c in self.kinds() if c.startswith('xconvert')], ['xconvert:Anchorage.esm'])
        self.assertTrue(steps.plugin_complete(self.lab('Anchorage.esm')))
        self.assertEqual(steps.plugin_masters(self.lab('Anchorage.esm')), ['Fallout4.esm', 'Fallout3.esm'])
        self.assertTrue(any('removing the earlier output' in m for m in self.messages))

    def test_an_output_older_than_the_game_file_is_converted_again(self):
        self.run_step()
        self.calls.clear()
        os.utime(os.path.join(self.fo3, 'Anchorage.esm'), None)                       # the game file was patched since: it is newer than our output now
        os.utime(self.lab('Anchorage.esm'), (1000000100, 1000000100))
        self.run_step()
        self.assertEqual([c for c in self.kinds() if c.startswith('xconvert')], ['xconvert:Anchorage.esm'])

    def test_a_converted_but_not_yet_renamed_output_is_renamed_not_converted_again(self):
        self.run_step()
        self.calls.clear()
        make_plugin(self.lab('Anchorage.esm'), ['Fallout4.esm', 'FalloutNV.esm'], groups=5)          # the run stopped between xConvert and the rename
        self.run_step()
        self.assertEqual([c for c in self.kinds() if c.startswith('xconvert')], [])
        self.assertEqual(steps.plugin_masters(self.lab('Anchorage.esm')), ['Fallout4.esm', 'Fallout3.esm'])

    # ---- xConvert failing
    def test_xconvert_errors_are_not_ignored_although_it_exits_with_zero(self):
        self.fail_xconvert = True
        with self.assertRaises(RuntimeError) as cm:
            self.run_step()
        self.assertIn('xConvert failed on FalloutNV.esm', str(cm.exception))
        self.assertIn('Unexpected Error', str(cm.exception))

    def test_a_missing_dlc_is_skipped(self):
        os.remove(os.path.join(self.fo3, 'Anchorage.esm'))
        self.run_step()
        self.assertEqual([c for c in self.kinds() if c.startswith('xconvert')], ['xconvert:FalloutNV.esm'])
        self.assertTrue(any('Anchorage.esm not installed' in m for m in self.messages))


@unittest.skipUnless(os.name == 'nt', 'needs Windows PowerShell')
class RenameMasterScriptTests(unittest.TestCase):
    """the real rename-master.ps1: it can be repeated"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.plugin = os.path.join(self.tmp, 'a.esm')
        make_plugin(self.plugin, ['Fallout4.esm', 'FalloutNV.esm'])

    def run_ps(self, *extra):
        r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', os.path.join(ROOT, 'rename-master.ps1'), '-Plugin', self.plugin] + list(extra),
                           capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def test_rename_then_repeat(self):
        rc, out = self.run_ps('-From', 'FalloutNV.esm', '-To', 'Fallout3.esm')
        self.assertEqual(rc, 0, out)
        self.assertEqual(steps.plugin_masters(self.plugin), ['Fallout4.esm', 'Fallout3.esm'])
        before = read(self.plugin)
        rc, out = self.run_ps('-From', 'FalloutNV.esm', '-To', 'Fallout3.esm')          # used to throw "Master FalloutNV.esm not found"
        self.assertEqual(rc, 0, out)
        self.assertIn('already Fallout3.esm', out)
        self.assertEqual(read(self.plugin), before)
        self.assertTrue(steps.plugin_complete(self.plugin))

    def test_repeat_with_a_different_output_file_still_writes_it(self):
        self.run_ps('-From', 'FalloutNV.esm', '-To', 'Fallout3.esm')
        out_path = os.path.join(self.tmp, 'final.esm')
        rc, out = self.run_ps('-From', 'FalloutNV.esm', '-To', 'Fallout3.esm', '-Out', out_path)
        self.assertEqual(rc, 0, out)
        self.assertEqual(read(out_path), read(self.plugin))

    def test_a_master_that_is_neither_there_is_still_an_error(self):
        rc, out = self.run_ps('-From', 'Nothing.esm', '-To', 'Other.esm')
        self.assertNotEqual(rc, 0)
        self.assertIn('not found', out)


if __name__ == '__main__':
    unittest.main()
