import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from studio import registry as R


def write(d, name, obj):
    p = os.path.join(d, name)
    with open(p, "w") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))
    return p


GOOD = {"id": "a", "name": "A", "repo": "https://x/a.git", "folder": "a", "build": ["./m.sh"], "app": "A.app"}


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.root = os.path.join(self.d, "root")
        os.makedirs(self.root)

    def load(self, obj, **kw):
        return R.load_tools(write(self.d, "r.json", obj), root=self.root, **kw)

    def test_real_registry_loads_four_tools(self):
        tools = R.load_tools(root=self.root)
        self.assertEqual([t.id for t in tools], ["beat_thief", "ableton_loader", "session_sync", "movie_maker"])
        self.assertTrue(all(t.state == R.NOT_INSTALLED for t in tools))

    def test_ready_when_git_checkout_present(self):
        os.makedirs(os.path.join(self.root, "a", ".git"))
        (t,) = self.load({"tools": [GOOD]})
        self.assertEqual(t.state, R.READY); self.assertTrue(t.usable)

    def test_missing_folder_is_not_installed_not_an_error(self):
        (t,) = self.load({"tools": [GOOD]})
        self.assertEqual(t.state, R.NOT_INSTALLED); self.assertFalse(t.usable)

    def test_folder_without_git(self):
        os.makedirs(os.path.join(self.root, "a"))
        (t,) = self.load({"tools": [GOOD]})
        self.assertEqual(t.state, R.NOT_GIT); self.assertIn("Ask Stefan", t.message)

    def test_no_repo_access_says_ask_stefan(self):
        (t,) = self.load({"tools": [GOOD]}, has_access=lambda t: False)
        self.assertEqual(t.state, R.NO_ACCESS); self.assertIn("Ask Stefan for access", t.message)

    def test_access_check_that_crashes_is_ignored(self):
        def boom(t): raise OSError("offline")
        (t,) = self.load({"tools": [GOOD]}, has_access=boom)
        self.assertEqual(t.state, R.NOT_INSTALLED)

    def test_access_check_not_asked_for_installed_tools(self):
        os.makedirs(os.path.join(self.root, "a", ".git"))
        def boom(t): raise AssertionError("should not be asked")
        (t,) = self.load({"tools": [GOOD]}, has_access=boom)
        self.assertEqual(t.state, R.READY)

    def test_malformed_entries_become_broken_tiles(self):
        bad = [{"id": "x", "name": "X"}, "nope", dict(GOOD, build="make"), GOOD, dict(GOOD, name="Dup")]
        tools = self.load({"tools": bad})
        self.assertEqual([t.state for t in tools],
                         [R.BROKEN, R.BROKEN, R.BROKEN, R.NOT_INSTALLED, R.BROKEN])
        self.assertTrue(all("Ask Stefan" in t.message for t in tools if t.state == R.BROKEN))

    def test_unreadable_registry_never_raises(self):
        for content in ("{not json", '{"tools": 5}', "{}", "[]", ""):
            tools = R.load_tools(write(self.d, "bad.json", content), root=self.root)
            self.assertEqual(len(tools), 1); self.assertEqual(tools[0].state, R.BROKEN)
        tools = R.load_tools(os.path.join(self.d, "absent.json"), root=self.root)
        self.assertEqual(tools[0].state, R.BROKEN)


if __name__ == "__main__":
    unittest.main()
