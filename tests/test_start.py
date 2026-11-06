"""Tests of the New Game start builder (no game needed): plugin structure, script sources, spawn-point check.

  python -m unittest tests.test_start -v
"""
import os, re, struct, sys, tempfile, unittest, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'navmesh'))
from navlib import iter_records, subrecords, record, sub, group

# build_start.py runs main() on import: load its functions without running it
SRC = open(os.path.join(ROOT, 'start', 'build_start.py'), encoding='utf-8').read().rsplit('\nmain()', 1)[0]
NS = {'__file__': os.path.join(ROOT, 'start', 'build_start.py'), '__name__': 'build_start'}
exec(compile(SRC, 'build_start.py', 'exec'), NS)


class StartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_plugin_has_the_two_quests(self):
        out = os.path.join(self.tmp, 'CapitalStart.esp')
        NS['build_plugin'](out)
        d = open(out, 'rb').read()
        quests = {}
        for r in iter_records(d):
            if r.sig == 'QUST':
                s = dict(subrecords(d, r))
                quests[s['EDID'].rstrip(b'\0').decode()] = (r.fid, s)
        self.assertEqual(set(quests), {'CapitalStartDemo', 'CapitalEscape'})
        fid, s = quests['CapitalStartDemo']
        self.assertEqual(fid, (2 << 24) | 0x800)
        flags = struct.unpack('<H', s['DNAM'][:2])[0]
        self.assertTrue(flags & 1, 'Start Game Enabled')
        self.assertIn(b'CapStartDemo', s['VMAD'])
        fid, s = quests['CapitalEscape']
        self.assertEqual(fid, (2 << 24) | 0x801)
        self.assertEqual(s['FULL'].rstrip(b'\0'), b'Escape!')
        self.assertFalse(struct.unpack('<H', s['DNAM'][:2])[0] & 1, 'the Escape! quest is started by the script, not at game start')
        self.assertIn('QOBJ', s)
        # masters: Fallout4.esm and Fallout3.esm, in that order
        self.assertLess(d.index(b'Fallout4.esm'), d.index(b'Fallout3.esm'))

    def test_sources_have_no_unfilled_placeholders_and_the_right_ids(self):
        src = os.path.join(self.tmp, 'src')
        files = NS['write_sources'](src)
        qs = open(files['CapStartDemo.psc.tmpl'], encoding='utf-8').read()
        fr = open(files['QF_MQ101_0001ED86.psc.tmpl'], encoding='utf-8').read()
        for t in (qs, fr):
            self.assertIsNone(re.search(r'@[A-Z0-9]+@', t))
        self.assertIn('Game.GetFormFromFile(%d, "Fallout3.esm")' % NS['EXIT_LOCAL'], fr)
        self.assertIn('Game.GetFormFromFile(%d, "CapitalStart.esp")' % NS['START_ID'], fr)
        self.assertIn('Game.GetFormFromFile(%d, "CapitalStart.esp")' % NS['ESC_ID'], qs)
        self.assertIn('Game.GetFormFromFile(%d, "Fallout4.esm")' % NS['PIPBOY'], qs)
        self.assertTrue(os.path.isfile(os.path.join(src, 'Fragments', 'Quests', 'QF_MQ101_0001ED86.psc')))

    def test_fragment_keeps_every_vanilla_function_name_and_only_item_01_does_anything(self):
        fr = open(os.path.join(ROOT, 'start', 'QF_MQ101_0001ED86.psc.tmpl'), encoding='utf-8').read()
        funcs = re.findall(r'(?m)^Function (Fragment_Stage_\w+)\(\)$', fr)
        self.assertEqual(len(funcs), 92)
        self.assertIn('Fragment_Stage_0000_Item_01', funcs)
        bodies = re.findall(r'(?ms)^Function (Fragment_Stage_\w+)\(\)\n(.*?)^EndFunction', fr)
        busy = [n for n, b in bodies if b.strip()]
        self.assertEqual(busy, ['Fragment_Stage_0000_Item_01'])

    def test_spawn_point_check(self):
        want = (1 << 24) | NS['EXIT_LOCAL']
        hdr = record('TES4', 0, [sub('HEDR', struct.pack('<fII', 1.0, 1, 0x800))], ver=131)
        good = os.path.join(self.tmp, 'good.esm')
        open(good, 'wb').write(hdr + record('REFR', want, [sub('NAME', struct.pack('<I', 1))], ver=131))
        bad = os.path.join(self.tmp, 'bad.esm')
        open(bad, 'wb').write(hdr + record('REFR', want + 1, [sub('NAME', struct.pack('<I', 1))], ver=131))
        self.assertTrue(NS['check_spawn_point'](good))
        self.assertFalse(NS['check_spawn_point'](bad))

    def test_compiler_search_path_puts_our_sources_first(self):
        # the game's own source folder holds a script with the same name as our intro fragment: if it came first we would compile (and install) the original
        src = open(os.path.join(ROOT, 'start', 'build_start.py'), encoding='utf-8').read()
        self.assertIn("'-i=%s;%s' % (src, base)", src)
        self.assertIn("b'F4EVER' not in frag", src)

    def test_start_script_fades_in_and_does_not_duplicate_the_pipboy(self):
        qs = open(os.path.join(ROOT, 'start', 'CapStartDemo.psc.tmpl'), encoding='utf-8').read()
        self.assertIn('Game.FadeOutGame(False, True', qs)
        self.assertIn('GetItemCount(pip) < 1', qs)

    def test_no_game_text_in_our_scripts(self):
        # the only words shown to the player are our own: quest name, objective, log line
        text = open(os.path.join(ROOT, 'start', 'build_start.py'), encoding='utf-8').read()
        self.assertIn('You made it out of Vault 101.', text)


if __name__ == '__main__':
    unittest.main()


class BaseSourcesTests(unittest.TestCase):
    """the game's script sources may be unpacked (Creation Kit did it) or only present as Base.zip: both must work, and nothing is written into the game folder"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fo4 = os.path.join(self.tmp, 'Fallout 4')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unpacked_sources_are_used_in_place(self):
        base = os.path.join(self.fo4, 'Data', 'Scripts', 'Source', 'Base')
        os.makedirs(base)
        for n in ('Game.psc', 'Institute_Papyrus_Flags.flg'):
            open(os.path.join(base, n), 'w').write('x')
        got, flags = NS['find_base'](self.fo4, os.path.join(self.tmp, 'scratch'))
        self.assertEqual(os.path.normcase(got), os.path.normcase(base))
        self.assertTrue(flags.endswith('Institute_Papyrus_Flags.flg'))

    def test_only_the_zip_is_unpacked_into_the_scratch_folder(self):
        import zipfile
        base = os.path.join(self.fo4, 'Data', 'Scripts', 'Source', 'Base')
        os.makedirs(base)
        with zipfile.ZipFile(os.path.join(base, 'Base.zip'), 'w') as z:
            z.writestr('Game.psc', 'x')
            z.writestr('Institute_Papyrus_Flags.flg', 'x')
        scratch = os.path.join(self.tmp, 'scratch')
        got, flags = NS['find_base'](self.fo4, scratch)
        self.assertTrue(os.path.isfile(os.path.join(got, 'Game.psc')))
        self.assertTrue(os.path.normcase(got).startswith(os.path.normcase(scratch)))
        self.assertEqual(sorted(os.listdir(base)), ['Base.zip'])            # the game folder is untouched

    def test_nothing_found_gives_a_clear_message(self):
        os.makedirs(self.fo4)
        with self.assertRaises(SystemExit) as cm:
            NS['find_base'](self.fo4, os.path.join(self.tmp, 'scratch'))
        self.assertIn('Creation Kit', str(cm.exception))
