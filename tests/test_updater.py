"""End-to-end tests of the update system against a local fake release server (no GitHub, no game files).

  python -m unittest discover -s tests -v
"""
import hashlib, http.server, json, os, shutil, sys, tempfile, threading, unittest, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'builder'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


class Server:
    def __init__(self, folder):
        h = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=folder, **k)
        self.srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h)
        self.url = 'http://127.0.0.1:%d' % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()


def make_release(folder, version, files, key, tamper_payload=False, save_compat='save-safe', min_app='0.1.0', bad_sig=False):
    os.makedirs(folder, exist_ok=True)
    pz = os.path.join(folder, 'CapitalPayload-%s.zip' % version)
    with zipfile.ZipFile(pz, 'w') as z:
        for n, c in files.items():
            z.writestr(n, c)
    m = {'version': version, 'notes': 'test ' + version, 'save_compat': save_compat, 'min_app_version': min_app,
         'payload': {'name': os.path.basename(pz), 'size': os.path.getsize(pz), 'sha256': hashlib.sha256(open(pz, 'rb').read()).hexdigest()}}
    mb = json.dumps(m, sort_keys=True).encode()
    open(os.path.join(folder, 'manifest.json'), 'wb').write(mb)
    sig = key.sign(mb + (b'x' if bad_sig else b'')).hex()
    open(os.path.join(folder, 'manifest.sig'), 'w').write(sig)
    if tamper_payload:
        with open(pz, 'ab') as f:
            f.write(b'extra')


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ['LOCALAPPDATA'] = self.tmp
        for m in ('updater', 'update_key'):
            sys.modules.pop(m, None)
        self.key = Ed25519PrivateKey.generate()
        pub = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
        import update_key
        update_key.PUBLIC_KEY_HEX = pub
        import updater
        self.u = updater
        self.rel = os.path.join(self.tmp, 'rel')
        self.srv = None

    def tearDown(self):
        if self.srv:
            self.srv.stop()
        os.environ.pop('CAPITAL_UPDATE_URL', None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def serve(self, **kw):
        if self.srv:
            self.srv.stop()
            shutil.rmtree(self.rel, ignore_errors=True)
        make_release(self.rel, kw.pop('version', '9.2.0'), kw.pop('files', {'worldfix/a.py': 'print(1)', 'README.md': 'x'}), self.key, **kw)
        self.srv = Server(self.rel)
        os.environ['CAPITAL_UPDATE_URL'] = self.srv.url
        return self.srv.url

    def test_valid_update_installs_and_becomes_active(self):
        self.serve()
        info = self.u.check()
        self.assertTrue(info['newer'])
        self.assertEqual(info['latest'], '9.2.0')
        self.u.apply(info, lambda *_: None)
        self.assertTrue(self.u.active_payload().endswith(os.path.join('9.2.0', 'payload')))
        self.assertTrue(os.path.exists(os.path.join(self.u.active_payload(), 'worldfix', 'a.py')))

    def test_same_version_is_not_newer(self):
        self.serve(version='0.1.0')
        self.assertFalse(self.u.check()['newer'])

    def test_bad_signature_is_refused(self):
        self.serve(bad_sig=True)
        with self.assertRaises(self.u.UpdateError):
            self.u.check()

    def test_manifest_signed_by_someone_else_is_refused(self):
        self.key = Ed25519PrivateKey.generate()          # a different key than the one the installer trusts
        self.serve()
        with self.assertRaises(self.u.UpdateError):
            self.u.check()

    def test_tampered_payload_is_refused(self):
        self.serve(tamper_payload=True)
        info = self.u.check()
        with self.assertRaises(self.u.UpdateError):
            self.u.apply(info, lambda *_: None)
        self.assertIsNone(self.u.active_payload())

    def test_forbidden_file_types_are_refused(self):
        self.serve(files={'evil.exe': 'MZ'})
        info = self.u.check()
        with self.assertRaises(self.u.UpdateError):
            self.u.apply(info, lambda *_: None)
        self.assertIsNone(self.u.active_payload())

    def test_path_traversal_is_refused(self):
        self.serve(files={'../outside.py': 'x'})
        info = self.u.check()
        with self.assertRaises(self.u.UpdateError):
            self.u.apply(info, lambda *_: None)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, 'CapitalConvert', 'outside.py')))

    def test_update_needing_newer_app_is_refused(self):
        self.serve(min_app='9.0.0')
        info = self.u.check()
        self.assertTrue(info['app_too_old'])
        with self.assertRaises(self.u.UpdateError):
            self.u.apply(info, lambda *_: None)

    def test_rollback_returns_to_previous_then_bundled(self):
        self.serve()
        self.u.apply(self.u.check(), lambda *_: None)
        self.serve(version='9.3.0', files={'worldfix/a.py': 'print(3)'})
        self.u.apply(self.u.check(), lambda *_: None)
        self.assertEqual(self.u.current_payload_version(), '9.3.0')
        self.u.rollback(lambda *_: None)
        self.assertEqual(self.u.current_payload_version(), '9.2.0')
        self.u.rollback(lambda *_: None)
        self.assertIsNone(self.u.active_payload())

    def test_offline_gives_a_plain_error(self):
        os.environ['CAPITAL_UPDATE_URL'] = 'http://127.0.0.1:9'
        with self.assertRaises(self.u.UpdateError) as cm:
            self.u.check()
        self.assertIn('could not reach', str(cm.exception))

    def test_refuses_foreign_download_hosts(self):
        os.environ.pop('CAPITAL_UPDATE_URL', None)
        with self.assertRaises(self.u.UpdateError):
            self.u._get('https://evil.example.com/manifest.json', 1000)


class ChangeDetectionTests(unittest.TestCase):
    FILES = ('worldfix/apply-fixes.ps1', 'worldfix/x.py', 'actors/y.py', 'navmesh/convert_navmesh.py', 'rename-master.ps1', 'convert-fo3-assets.ps1',
             'builder/tools.lock.json', 'build-actor-map.ps1', 'worldfix/place_disabled_actors.py', 'tool/xedit/Edit Scripts/s.pas',
             'worldfix/fix_crashers.py', 'install-output.ps1', 'capital-profile.ps1')

    def make(self):
        wd = tempfile.mkdtemp()
        for rel in self.FILES:
            p = os.path.join(wd, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'w').write('a')
        return wd

    def test_script_change_reruns_that_stage_and_later_only(self):
        import capital_builder as cb
        wd = self.make()
        try:
            st = {'done': {s['id']: {} for s in cb.STAGES}, 'hashes': {s['id']: cb.stage_hash(s, wd) for s in cb.STAGES}}
            self.assertIsNone(cb.invalidate_changed({'workdir': wd}, st, lambda *_: None))
            open(os.path.join(wd, 'navmesh', 'convert_navmesh.py'), 'w').write('changed')
            stale = cb.invalidate_changed({'workdir': wd}, st, lambda *_: None)
            self.assertEqual(stale, '10-navmesh')
            for early in ('01-prepare', '02-assets', '03-plugins', '04-worldfix', '06-actors'):
                self.assertIn(early, st['done'], early + ' must be kept')
            for late in ('10-navmesh', '12-fixes', '15-meshes', '18-install'):
                self.assertNotIn(late, st['done'], late + ' must re-run')
        finally:
            shutil.rmtree(wd, ignore_errors=True)

    def test_worldfix_change_keeps_the_slow_stages(self):
        import capital_builder as cb
        wd = self.make()
        try:
            st = {'done': {s['id']: {} for s in cb.STAGES}, 'hashes': {s['id']: cb.stage_hash(s, wd) for s in cb.STAGES}}
            open(os.path.join(wd, 'worldfix', 'x.py'), 'w').write('changed')
            stale = cb.invalidate_changed({'workdir': wd}, st, lambda *_: None)
            for slow in ('01-prepare', '02-assets', '03-plugins'):
                self.assertIn(slow, st['done'], slow + ' (hours) must not re-run for a script fix')
            self.assertIsNotNone(stale)
        finally:
            shutil.rmtree(wd, ignore_errors=True)

    def test_tool_version_change_reruns_everything_from_prepare(self):
        import capital_builder as cb
        wd = self.make()
        try:
            st = {'done': {s['id']: {} for s in cb.STAGES}, 'hashes': {s['id']: cb.stage_hash(s, wd) for s in cb.STAGES}}
            open(os.path.join(wd, 'builder', 'tools.lock.json'), 'w').write('b')
            self.assertEqual(cb.invalidate_changed({'workdir': wd}, st, lambda *_: None), '01-prepare')
        finally:
            shutil.rmtree(wd, ignore_errors=True)

    def test_state_from_before_tracking_is_adopted_not_rerun(self):
        import capital_builder as cb
        wd = self.make()
        try:
            st = {'done': {s['id']: {} for s in cb.STAGES}}
            self.assertIsNone(cb.invalidate_changed({'workdir': wd}, st, lambda *_: None))
            self.assertEqual(len(st['done']), len(cb.STAGES))
            self.assertEqual(len(st['hashes']), len(cb.STAGES))
        finally:
            shutil.rmtree(wd, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
