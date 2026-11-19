"""signing_keychain.sh: the key that signs Steezy Studio.app sits in a keychain of its own. Its password used to be
a fixed word in this public repo and the keychain never locked, so any program running as you could sign itself
as Steezy Studio and inherit what you allowed it (Desktop access). Now each Mac gets a random password (a file
only you can read), and the keychain is locked after every build and on its own after 10 minutes.

These tests make a throwaway keychain (no certificate needed) and put the user's keychain search list back."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(HERE, "signing_keychain.sh")


@unittest.skipUnless(sys.platform == "darwin" and os.path.exists("/usr/bin/security"), "macOS keychains")
class Keychain(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="steezy sign ")          # a space: paths must survive word splitting
        self.kc = os.path.join(self.d, "test signing.keychain-db")
        self.env = dict(os.environ, STEEZY_SIGNING_KEYCHAIN=self.kc, STEEZY_ENGINE_DIR=os.path.join(self.d, "engine"))
        self.saved = subprocess.run(["security", "list-keychains", "-d", "user"], capture_output=True, text=True).stdout
        self.addCleanup(self.restore)

    def restore(self):
        paths = [l.strip().strip('"') for l in self.saved.splitlines() if l.strip()]
        subprocess.run(["security", "list-keychains", "-d", "user", "-s", *paths], check=True)
        subprocess.run(["security", "delete-keychain", self.kc], capture_output=True)

    def sh(self, script):
        return subprocess.run(["bash", "-c", '. "%s"; set -e; %s' % (LIB, script)], env=self.env,
                              capture_output=True, text=True, timeout=60)

    def search_list(self):
        out = subprocess.run(["security", "list-keychains", "-d", "user"], capture_output=True, text=True).stdout
        return [os.path.realpath(l.strip().strip('"')) for l in out.splitlines() if l.strip()]

    def test_a_new_keychain_gets_a_random_private_password(self):
        r = self.sh('create_signing_keychain; signing_password')
        self.assertEqual(r.returncode, 0, r.stderr)
        pw = r.stdout.strip().splitlines()[-1]
        self.assertNotEqual(pw, "steezy-studio"); self.assertGreaterEqual(len(pw), 24)
        f = os.path.join(self.d, "signing_password")
        self.assertEqual(open(f).read().strip(), pw)
        self.assertEqual(os.stat(f).st_mode & 0o077, 0)                    # only this user can read it
        self.assertNotEqual(self.sh('signing_password').returncode, 1)

    def test_an_old_keychain_with_the_public_password_is_moved_to_a_random_one(self):
        subprocess.run(["security", "create-keychain", "-p", "steezy-studio", self.kc], check=True)
        r = self.sh('open_signing_keychain; close_signing_keychain; signing_password')
        self.assertEqual(r.returncode, 0, r.stderr)
        pw = r.stdout.strip().splitlines()[-1]
        self.assertNotEqual(pw, "steezy-studio")
        self.assertNotEqual(subprocess.run(["security", "unlock-keychain", "-p", "steezy-studio", self.kc],
                                           capture_output=True).returncode, 0)      # the public word no longer opens it
        self.assertEqual(subprocess.run(["security", "unlock-keychain", "-p", pw, self.kc]).returncode, 0)

    def test_open_adds_it_to_the_search_list_once_keeping_the_others_and_close_locks_it(self):
        self.assertEqual(self.sh('create_signing_keychain').returncode, 0)
        kc = os.path.realpath(self.kc)
        before = [p for p in self.search_list() if p != kc]
        for _ in range(2):
            r = self.sh('open_signing_keychain'); self.assertEqual(r.returncode, 0, r.stderr)
        after = self.search_list()
        self.assertEqual(after.count(kc), 1)
        self.assertEqual([p for p in after if p != kc], before)           # nothing dropped or split apart
        info = subprocess.run(["security", "show-keychain-info", self.kc], capture_output=True, text=True)
        self.assertIn("timeout=600s", info.stderr + info.stdout)          # locks itself if a build dies midway
        self.assertIn("lock-on-sleep", info.stderr + info.stdout)
        r = self.sh('close_signing_keychain'); self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_made_identity_signs_like_a_build_does(self):
        self.env["STEEZY_SIGNING_NAME"] = "Steezy Test Signing %d" % os.getpid()
        r = subprocess.run(["bash", os.path.join(HERE, "make_signing_identity.sh")], env=self.env,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        tool = os.path.join(self.d, "hello"); open(tool, "w").write("#!/bin/sh\necho hi\n"); os.chmod(tool, 0o755)
        r = self.sh('open_signing_keychain; id="$(signing_identity)"; [ -n "$id" ]; '
                    'codesign --force --sign "$id" "%s"; close_signing_keychain; codesign --verify "%s"' % (tool, tool))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        again = subprocess.run(["bash", os.path.join(HERE, "make_signing_identity.sh")], env=self.env,
                               capture_output=True, text=True, timeout=60)
        self.assertIn("already exists", again.stdout)                       # a second run makes nothing new

    def test_the_build_locks_the_keychain_when_it_ends(self):
        mk = open(os.path.join(HERE, "make_app.sh")).read()
        self.assertIn("close_signing_keychain", mk)
        self.assertIn("trap", mk)


if __name__ == "__main__":
    unittest.main()
