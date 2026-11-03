import json, os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from studio import gui


def git(path, *a):
    subprocess.run(["git", "-C", path, "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True)


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.root = os.path.join(self.d, "root"); os.makedirs(self.root)
        self.apps = os.path.join(self.d, "apps"); os.makedirs(self.apps)
        self.reg = os.path.join(self.d, "r.json")
        with open(self.reg, "w") as f:
            json.dump({"tools": [
                {"id": "a", "name": "A", "repo": "x", "folder": "a", "build": ["./m"], "app": "A.app"},
                {"id": "b", "name": "B", "repo": "x", "folder": "b", "build": ["./m"], "app": "B.app"}]}, f)
        self.api = gui.Api(self.reg, self.root, app_dirs=(self.apps,))

    def repo(self, name):
        p = os.path.join(self.root, name); os.makedirs(p)
        git(p, "init", "-q", "-b", "main")
        open(os.path.join(p, "f"), "w").write("1")
        git(p, "add", "."); git(p, "commit", "-q", "-m", "one")
        return p

    def test_missing_tool_is_a_message_not_an_error(self):
        tools = self.api.list_tools()
        self.assertEqual([t["usable"] for t in tools], [False, False])
        self.assertIn("isn't on this computer", tools[0]["message"])

    def test_installed_tool_shows_version_and_not_built(self):
        self.repo("a")
        a = self.api.list_tools()[0]
        self.assertTrue(a["usable"]); self.assertEqual(len(a["version"]), 7)
        self.assertFalse(a["dirty"]); self.assertIsNone(a["app"]); self.assertIsNone(a["behind"])

    def test_dirty_and_behind(self):
        p = self.repo("a")
        open(os.path.join(p, "f"), "w").write("2")
        self.assertTrue(self.api.list_tools()[0]["dirty"])
        up = os.path.join(self.d, "up"); subprocess.run(["git", "clone", "-q", p, up], check=True)
        git(p, "checkout", "-q", "--", "f")
        git(up, "commit", "-q", "--allow-empty", "-m", "two")
        git(p, "remote", "add", "origin", up); git(p, "fetch", "-q"); git(p, "branch", "-q", "-u", "origin/main")
        self.assertEqual(self.api.list_tools()[0]["behind"], 1)

    def test_open_unbuilt_and_unknown_and_missing(self):
        self.repo("a")
        self.assertIn("hasn't been built", self.api.open_tool("a")["message"])
        self.assertFalse(self.api.open_tool("b")["ok"])
        self.assertFalse(self.api.open_tool("zzz")["ok"])

    def test_open_built_app_runs_open(self):
        self.repo("a"); os.makedirs(os.path.join(self.apps, "A.app"))
        calls = []
        orig = gui.subprocess.Popen
        gui.subprocess.Popen = lambda cmd: calls.append(cmd)
        try:
            r = self.api.open_tool("a")
        finally:
            gui.subprocess.Popen = orig
        self.assertTrue(r["ok"]); self.assertEqual(calls, [["open", os.path.join(self.apps, "A.app")]])

    def test_non_git_folder_does_not_crash_version(self):
        os.makedirs(os.path.join(self.root, "a", ".git"))   # fake .git: git itself fails
        a = self.api.list_tools()[0]
        self.assertIsNone(a["version"])


class TestUpdateAllApi(T):
    def test_update_all_reports_each_tool_and_never_blocks(self):
        import time
        self.repo("a")
        self.api._update_kw = {"refresh": lambda t: (True, ""), "build": lambda t: (True, ""), "fetch": False}
        self.assertTrue(self.api.update_all()["started"])
        for _ in range(100):
            s = self.api.update_status()
            if not s["running"]:
                break
            time.sleep(0.05)
        self.assertFalse(s["running"])
        self.assertEqual({r["id"]: r["status"] for r in s["results"]}, {"a": "up_to_date", "b": "unavailable"})
        self.assertEqual(len(s["results"]), 2)
        self.assertIn("isn't on this computer", s["results"][1]["message"])


if __name__ == "__main__":
    unittest.main()
