"""Tests of the publish gate on throw-away git repositories: it must block personal data, secrets, game files, bad identities and unsafe pushes.

  python -m unittest tests.test_publish -v
"""
import io, os, subprocess, sys, tempfile, unittest, shutil, contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'publish'))
import publish as P

CFG = {'repo': 'someone/some-repo', 'author_name': 'someone', 'author_email': 'someone@users.noreply.github.com',
       'private_strings': ['jdoe123', 'acme-corp.example', 'D:\\Secret Folder'], 'signing_key_paths': []}
ENV = {'GIT_AUTHOR_NAME': 'someone', 'GIT_AUTHOR_EMAIL': 'someone@users.noreply.github.com', 'GIT_COMMITTER_NAME': 'someone',
       'GIT_COMMITTER_EMAIL': 'someone@users.noreply.github.com'}


def sh(root, *a, env=None):
    e = dict(os.environ)
    e.update(env or ENV)
    return subprocess.run(['git', '-C', root] + list(a), capture_output=True, text=True, env=e)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        sh(self.d, 'init', '-q', '-b', 'main')
        self.keyfile = os.path.join(self.d, '..', 'fake-private.key')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)
        try:
            os.remove(self.keyfile)
        except OSError:
            pass

    def commit(self, files, msg='x', env=None):
        for rel, content in files.items():
            p = os.path.join(self.d, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'wb') as f:
                f.write(content if isinstance(content, bytes) else content.encode('utf-8'))
        sh(self.d, 'add', '-A')
        r = sh(self.d, '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', msg, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def problems(self, cfg=None):
        pr, _ = P.check_tree(self.d, 'HEAD', cfg or CFG)
        return pr

    def test_clean_tree_passes(self):
        self.commit({'README.md': 'hello', 'src/a.py': 'print(1)'})
        self.assertEqual(self.problems(), [])

    def test_private_string_is_found_in_any_file_case_insensitively(self):
        self.commit({'src/a.py': 'path = "C:/x/JDoe123/y"'})
        self.assertTrue(any('private string' in p for p in self.problems()))

    def test_private_path_with_backslash_is_found(self):
        self.commit({'docs/a.md': 'see D:\\Secret Folder\\notes'})
        self.assertTrue(any('private string' in p for p in self.problems()))

    def test_personal_windows_path_is_found_even_if_not_configured(self):
        self.commit({'a.txt': 'C:' + chr(92) + 'Us' + 'ers' + chr(92) + 'SomebodyElse' + chr(92) + 'Documents'})   # built in pieces so this file itself passes the gate
        self.assertTrue(any('personal Windows path' in p for p in self.problems()))

    def test_credentials_are_found(self):
        self.commit({'a.txt': 'token = ghp_' + 'A' * 36})
        self.assertTrue(any('credential' in p for p in self.problems()))
        self.commit({'b.txt': '-' * 5 + 'BEGIN PRIV' + 'ATE KEY' + '-' * 5 + '\nabc'})            # built in pieces so this file passes the gate itself
        self.assertTrue(len([p for p in self.problems() if 'credential' in p]) >= 2)

    def test_the_real_signing_key_is_found_without_being_printed(self):
        secret = 'ab' * 40
        with open(self.keyfile, 'w') as f:
            f.write(secret)
        cfg = dict(CFG, signing_key_paths=[self.keyfile])
        self.commit({'notes.txt': 'oops ' + secret})
        pr = self.problems(cfg)
        self.assertTrue(any('PRIVATE SIGNING KEY' in p for p in pr))
        self.assertFalse(any(secret in p for p in pr))

    def test_game_files_programs_and_keys_are_forbidden(self):
        self.commit({'Fallout3.esm': 'x', 'a/b.ba2': 'x', 'tool.exe': 'x', 'id_rsa': 'x', 'my.pfx': 'x', 'dist/z.zip': 'x', 'assets/local/p.jpg': 'x', 'publish/local/config.json': '{}'})
        pr = ' '.join(self.problems())
        for name in ('Fallout3.esm', 'b.ba2', 'tool.exe', 'id_rsa', 'my.pfx', 'dist/z.zip', 'assets/local/p.jpg', 'publish/local/config.json'):
            self.assertIn(name, pr, name)

    def test_only_committed_files_count_not_the_working_folder(self):
        self.commit({'ok.txt': 'fine'})
        with open(os.path.join(self.d, 'untracked.txt'), 'w') as f:
            f.write('jdoe123')
        self.assertEqual(self.problems(), [])
        self.assertTrue(P.check_state(self.d, skip_tests=True))              # but a dirty tree is reported

    def test_config_rejects_a_real_email(self):
        import json
        p = os.path.join(self.d, 'c.json')
        with open(p, 'w') as f:
            json.dump(dict(CFG, author_email='me@gmail.com'), f)
        with self.assertRaises(P.Gate):
            P.load_cfg(p)

    def test_snapshot_makes_clean_public_history_and_never_uses_the_working_identity(self):
        real = {'GIT_AUTHOR_NAME': 'Real Name', 'GIT_AUTHOR_EMAIL': 'real@work.example', 'GIT_COMMITTER_NAME': 'Real Name', 'GIT_COMMITTER_EMAIL': 'real@work.example'}
        self.commit({'README.md': 'hello'}, msg='my real commit', env=real)
        with contextlib.redirect_stdout(io.StringIO()):
            P.cmd_snapshot(self.d, CFG, '0.1.0', skip_tests=True)
        self.assertEqual(P.check_identity(self.d, 'refs/heads/public', CFG), [])
        self.assertEqual(sh(self.d, 'log', 'main', '--format=%ae').stdout.split(), ['real@work.example'])       # local history keeps the real one
        self.assertEqual(sh(self.d, 'log', 'public', '--format=%ae|%ce').stdout.split(), ['someone@users.noreply.github.com|someone@users.noreply.github.com'])

    def test_snapshot_refuses_when_the_tree_is_dirty_or_leaks(self):
        self.commit({'a.py': 'user = "jdoe123"'})
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(P.Gate):
                P.cmd_snapshot(self.d, CFG, 'x', skip_tests=True)
        self.assertEqual(sh(self.d, 'rev-parse', '--verify', '-q', 'refs/heads/public').stdout.strip(), '')

    def test_identity_check_catches_a_real_email_on_the_public_branch(self):
        real = {'GIT_AUTHOR_NAME': 'someone', 'GIT_AUTHOR_EMAIL': 'real@work.example', 'GIT_COMMITTER_NAME': 'someone', 'GIT_COMMITTER_EMAIL': 'real@work.example'}
        self.commit({'a': '1'}, env=real)
        sh(self.d, 'branch', 'public')
        pr, _ = P.check_public_history(self.d, CFG)
        self.assertTrue(any('e-mail is not your no-reply' in p for p in pr))

    def test_hook_blocks_everything_except_public_to_main(self):
        self.commit({'a': '1'})
        with contextlib.redirect_stdout(io.StringIO()):
            P.cmd_snapshot(self.d, CFG, 'x', skip_tests=True)
        pub = sh(self.d, 'rev-parse', 'public').stdout.strip()
        main = sh(self.d, 'rev-parse', 'main').stdout.strip()
        url = 'https://github.com/someone/some-repo.git'

        def hook(lines, u=url):
            old = sys.stdin
            sys.stdin = io.StringIO(lines)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    return P.cmd_hook(self.d, CFG, 'origin', u)
            finally:
                sys.stdin = old
        self.assertEqual(hook('refs/heads/public %s refs/heads/main %s\n' % (pub, P.ZERO)), 0)
        self.assertEqual(hook('refs/heads/main %s refs/heads/main %s\n' % (main, P.ZERO)), 1)             # the local branch never goes out
        self.assertEqual(hook('refs/heads/public %s refs/heads/other %s\n' % (pub, P.ZERO)), 1)
        self.assertEqual(hook('(delete) %s refs/heads/main %s\n' % (P.ZERO, pub)), 1)
        self.assertEqual(hook('refs/heads/public %s refs/heads/main %s\n' % (pub, P.ZERO), 'https://github.com/evil/other.git'), 1)


if __name__ == '__main__':
    unittest.main()
