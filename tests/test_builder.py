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


class ElricFailureListTests(unittest.TestCase):
    """steps.py reads elric-failures.txt (meshes the bulk Elric pass gave up on) to convert them one by one"""

    def test_paths_are_normalised(self):
        import steps
        tmp = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp, 'elric-failures.txt'), 'w', encoding='utf-8') as f:
                f.write('Fallout3\tmeshes\\new_vegas\\Armor\\HeadGear\\PartyHat\\M\\PartyHatGO.nif\n')
                f.write('Zeta\tmeshes\\new_vegas\\dlc05\\clutter\\rubblepile\\dlc05rubblepile01.nif\n')
                f.write('Zeta\tmeshes\\new_vegas\\dlc05\\clutter\\rubblepile\\dlc05rubblepile01.nif\n')       # twice: once
                f.write('garbage line without a tab\n')
            self.assertEqual(steps._elric_failures({'workdir': tmp}), ['armor/headgear/partyhat/m/partyhatgo.nif', 'dlc05/clutter/rubblepile/dlc05rubblepile01.nif'])
            self.assertEqual(steps._elric_failures({'workdir': os.path.join(tmp, 'nothing')}), [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class DoorModelTests(unittest.TestCase):
    """build_door_anims must find a door model that only exists as a repaired loose file (the Vault 101 door, the metro door): it used to look in the archives only"""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, 'worldfix'))
        sys.path.insert(0, os.path.join(ROOT, 'navmesh'))
        import build_door_anims
        self.m = build_door_anims
        self.tmp = tempfile.mkdtemp()
        self.root = self.tmp + os.sep

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def loose(self, key, data):
        p = self.m.loose_path(key, self.root)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data)

    def test_a_loose_model_is_found_without_any_archive(self):
        key = 'meshes/new_vegas/dungeons/vault/halls/vdoor01.nif'
        self.loose(key, b'REPAIRED')
        self.assertEqual(self.m.read_model(key, {}, self.root), b'REPAIRED')

    def test_the_archive_is_used_when_there_is_no_loose_file(self):
        import io
        key = 'meshes/new_vegas/a/door.nif'
        arch = io.BytesIO(b'..' + b'FROM-ARCHIVE')
        self.assertEqual(self.m.read_model(key, {key: (arch, (2, 0, 12))}, self.root), b'FROM-ARCHIVE')

    def test_the_loose_file_wins_over_the_archive(self):
        import io
        key = 'meshes/new_vegas/a/door.nif'
        self.loose(key, b'LOOSE')
        self.assertEqual(self.m.read_model(key, {key: (io.BytesIO(b'ARCHIVE'), (0, 0, 7))}, self.root), b'LOOSE')

    def test_a_model_nowhere_is_none(self):
        self.assertIsNone(self.m.read_model('meshes/new_vegas/none.nif', {}, self.root))

    def test_importing_the_script_reads_no_archive(self):
        # the module used to open six .ba2 files while being imported, so it could not be tested or reused
        self.assertTrue(callable(self.m.main))


class RefReasonTests(unittest.TestCase):
    """the reason a dropped placed reference cannot be restored is named instead of the opaque 'base not converted'"""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, 'worldfix'))
        sys.path.insert(0, os.path.join(ROOT, 'navmesh'))
        import ref_reasons
        self.r = ref_reasons.reason

    def test_editor_markers(self):
        self.assertEqual(self.r(('STAT', 'RoomMarker', ''), 0x1234), 'editor marker')
        self.assertEqual(self.r(('STAT', 'COCMarkerHeading', 'MarkerCOCHeading.nif'), 0x1234), 'editor marker')
        self.assertEqual(self.r(('STAT', 'CollisionMarker', ''), 0x1234), 'editor marker')

    def test_sound_effect_and_water(self):
        self.assertEqual(self.r(('SOUN', 'AMBWindMono01LP', ''), 1), 'ambient sound emitter')
        self.assertEqual(self.r(('PWAT', 'WaterMetroLong', 'Water_Placeable\\WaterP1x4.NIF'), 1), 'placeable water plane')
        self.assertIn('ambient effect', self.r(('MSTT', 'FXDustSimple01NoMesh', 'Effects\\Ambient\\FXDustSimple01NoMesh.NIF'), 1))

    def test_engine_forms_and_the_unexpected(self):
        self.assertEqual(self.r(None, 0x20), 'engine form (marker)')
        self.assertEqual(self.r(None, 0x0100ABCD), 'base record not found')
        # a visible object that was not converted must stand out, with its name
        self.assertEqual(self.r(('STAT', 'RCSmDoorFrame03', 'Architecture\\RC\\SmDoorFrame03.nif'), 1), 'other: STAT RCSmDoorFrame03')
        self.assertEqual(self.r(('MSTT', 'SomeRock', 'Landscape\\Rocks\\Rock01.nif'), 1), 'other: MSTT SomeRock')


class ConvertScriptTests(unittest.TestCase):
    """convert-fo3-assets.ps1 is exercised by hand on the real games; these checks keep its two fixes from being lost"""

    def setUp(self):
        with open(os.path.join(ROOT, 'convert-fo3-assets.ps1'), encoding='utf-8') as f:
            self.src = f.read()

    def test_meshes_are_made_safe_instead_of_being_removed_by_name(self):
        self.assertIn('elric_prep.py', self.src)
        self.assertNotIn('busshelter01', self.src)               # the hard-coded list of meshes removed before Elric (their objects were then missing)
        self.assertNotIn('megatonrampstraightreg', self.src)

    def test_crash_dumps_of_our_own_elric_runs_are_cleaned_up(self):
        self.assertIn("Elrich.exe.*.dmp", self.src)
        self.assertIn('$_.LastWriteTime -ge $since', self.src)    # never an older dump

    def test_a_failed_archive_stops_the_stage_and_sources_are_kept(self):
        self.assertIn('function Invoke-Archive2', self.src)
        self.assertIn('throw', self.src.split('function Invoke-Archive2', 1)[1].split('foreach ($plugin', 1)[0])
        # the extracted textures / meshes are deleted only after both archives were written
        packing = self.src.split("Step 'Packing BA2 archives'", 1)[1]
        self.assertLess(packing.index('Invoke-Archive2 "$plugin - Textures"'), packing.index('Remove-Item "$output\\$d"'))

    def test_files_the_texture_archive_cannot_hold_are_left_out_before_it_runs(self):
        self.assertIn("$_.Extension -ne '.dds'", self.src)


if __name__ == '__main__':
    unittest.main()
