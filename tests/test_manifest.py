"""Tests of SYNC-MANIFEST.json and tools/verify_manifest.py: the manifest describes the files of this repository (the program payload), line endings do not matter,
and a payload file that was edited, added or removed without updating the manifest is reported.

  python -m unittest tests.test_manifest -v
After editing a payload file run  python tools/verify_manifest.py --update  to bring the manifest up to date.
"""
import json, os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import verify_manifest as vm


class RepositoryTests(unittest.TestCase):
    def test_the_manifest_matches_this_repository(self):
        self.assertEqual(vm.check(), [], 'SYNC-MANIFEST.json is out of date: run  python tools/verify_manifest.py --update')

    def test_every_payload_file_is_listed_once_with_a_hash(self):
        files = vm.load()
        paths = [e['path'] for e in files]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(sorted(paths), vm.payload_files(ROOT))
        for e in files:
            self.assertRegex(e['sha256'], r'^[0-9a-f]{64}$')
            self.assertIn(e['origin'], ('dev', 'repo'))

    def test_files_that_only_live_here_are_not_marked_as_synced(self):
        origin = {e['path']: e['origin'] for e in vm.load()}
        for p in ('worldfix/elric_prep.py', 'worldfix/ref_reasons.py', 'start/build_start.py', 'builder/updater.py'):
            self.assertEqual(origin.get(p), 'repo', p)             # a sync that removes files the dev tree no longer supplies must never remove these


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.manifest = os.path.join(self.tmp, 'SYNC-MANIFEST.json')
        self.put('worldfix/a.py', b'print(1)\n')
        self.put('builder/b.py', b'print(2)\r\n')
        self.put('CREDITS.md', b'credits\n')

    def put(self, rel, data):
        p = os.path.join(self.tmp, *rel.split('/'))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(data)

    def test_fresh_manifest_matches(self):
        vm.write(self.tmp, self.manifest)
        self.assertEqual(vm.check(self.tmp, self.manifest), [])
        self.assertEqual([e['path'] for e in vm.load(self.manifest)], ['CREDITS.md', 'builder/b.py', 'worldfix/a.py'])

    def test_line_endings_do_not_matter(self):
        vm.write(self.tmp, self.manifest)
        self.put('builder/b.py', b'print(2)\n')                      # the same file checked out with LF
        self.put('worldfix/a.py', b'print(1)\r\n')                   # ... and with CRLF
        self.assertEqual(vm.check(self.tmp, self.manifest), [])

    def test_changed_missing_and_new_files_are_reported(self):
        vm.write(self.tmp, self.manifest)
        self.put('worldfix/a.py', b'print(3)\n')
        os.remove(os.path.join(self.tmp, 'builder', 'b.py'))
        self.put('worldfix/new.py', b'x\n')
        self.assertEqual(sorted(vm.check(self.tmp, self.manifest)), ['changed: worldfix/a.py', 'missing: builder/b.py', 'not in the manifest: worldfix/new.py'])

    def test_update_keeps_the_hash_of_the_development_copy(self):
        old = [{'path': 'worldfix/a.py', 'sha256': 'f' * 64}, {'path': 'builder/b.py', 'sha256': vm.digest(os.path.join(self.tmp, 'builder', 'b.py'))}]
        with open(self.manifest, 'w') as f:
            json.dump({'files': old}, f)
        files = {e['path']: e for e in vm.write(self.tmp, self.manifest)}
        self.assertEqual(files['worldfix/a.py']['dev_sha256'], 'f' * 64)            # what the development tree had, kept as provenance
        self.assertEqual(files['worldfix/a.py']['sha256'], vm.digest(os.path.join(self.tmp, 'worldfix', 'a.py')))
        self.assertEqual(files['worldfix/a.py']['origin'], 'dev')
        self.assertNotIn('dev_sha256', files['builder/b.py'])                       # identical to the development copy: nothing to record
        self.assertEqual(files['CREDITS.md']['origin'], 'repo')                      # a file the old manifest did not know
        self.assertEqual(vm.check(self.tmp, self.manifest), [])

    def test_a_sync_records_the_copy_it_made(self):
        vm.write(self.tmp, self.manifest, {'worldfix/a.py': 'a' * 64})
        e = {x['path']: x for x in vm.load(self.manifest)}['worldfix/a.py']
        self.assertEqual((e['origin'], e['dev_sha256']), ('dev', 'a' * 64))


class CommandLineTests(unittest.TestCase):
    def test_exit_code_and_message(self):
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'verify_manifest.py')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('matches SYNC-MANIFEST.json', r.stdout)
        tmp = tempfile.mkdtemp()
        try:
            r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'verify_manifest.py'), '--root', tmp], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn('missing: ', r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
