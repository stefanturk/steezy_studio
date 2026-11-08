import json, os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest import mock
from studio import gui, registry


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


class TestOpenOnlyWhenReady(T):
    def _wait(self):
        import time
        for _ in range(200):
            s = self.api.update_status()
            if not s["running"]:
                return s
            time.sleep(0.05)
        raise AssertionError("never finished")

    def test_open_is_locked_while_a_tool_waits_or_updates(self):
        self.repo("a"); os.makedirs(os.path.join(self.apps, "A.app"))
        self.assertTrue(self.api.list_tools()[0]["openable"])
        self.api._queued = {"a"}
        self.assertFalse(self.api.list_tools()[0]["openable"])
        self.api._queued, self.api._working_on = set(), "a"
        a = self.api.list_tools()[0]
        self.assertFalse(a["openable"]); self.assertTrue(a["updating"])
        self.api._working_on, self.api._installing = None, "a"
        self.assertFalse(self.api.list_tools()[0]["openable"])

    def test_a_failed_update_still_opens_with_a_note(self):
        self.repo("a"); os.makedirs(os.path.join(self.apps, "A.app"))
        p = os.path.join(self.root, "a")
        up = os.path.join(self.d, "up"); subprocess.run(["git", "clone", "-q", p, up], check=True)
        git(p, "remote", "add", "origin", up); git(p, "fetch", "-q"); git(p, "branch", "-q", "-u", "origin/main")
        git(up, "commit", "-q", "--allow-empty", "-m", "two")
        self.api._studio_tool = None
        with mock.patch.object(registry, "studio_path", return_value=None):
            self.api._update_kw = {"refresh": lambda t: (False, "no wheel"), "build": lambda t: (True, "")}
            self.api.update_all()
            s = self._wait()
        a = next(r for r in s["results"] if r["id"] == "a")
        self.assertEqual(a["status"], "build_failed")
        self.assertIn("still open the version you have", a["message"])
        self.assertTrue(self.api.list_tools()[0]["openable"])

    def test_needs_update_when_behind_or_never_built(self):
        with mock.patch.object(registry, "studio_path", return_value=None):
            self.assertFalse(self.api.needs_update())                 # nothing installed
            self.repo("a")
            self.assertTrue(self.api.needs_update())                  # cloned, never built
            os.makedirs(os.path.join(self.apps, "A.app"))
            self.assertFalse(self.api.needs_update())


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

    def _studio_with_upstream(self):
        """A Studio clone that is one commit behind its upstream (already fetched)."""
        p = os.path.join(self.d, "studio"); os.makedirs(p)
        git(p, "init", "-q", "-b", "main")
        open(os.path.join(p, "f"), "w").write("1")
        git(p, "add", "."); git(p, "commit", "-q", "-m", "one")
        up = os.path.join(self.d, "studio_up")
        subprocess.run(["git", "clone", "-q", p, up], check=True)
        git(p, "remote", "add", "origin", up); git(p, "fetch", "-q"); git(p, "branch", "-q", "-u", "origin/main")
        return p, up

    def test_check_updates_fetches_so_behind_becomes_real(self):
        p, up = self._studio_with_upstream()
        self.api._studio_tool = registry.studio_tool(p)
        self.assertEqual(self.api.studio_status()["behind"], 0)
        git(up, "commit", "-q", "--allow-empty", "-m", "two")      # new upstream commit, not yet fetched
        self.assertEqual(self.api.studio_status()["behind"], 0)
        self.assertEqual(self.api.check_updates()["behind"], 1)

    def test_studio_without_a_known_clone_is_just_unknown(self):
        with mock.patch.object(registry, "studio_path", return_value=None):
            self.assertEqual(self.api.studio_status(), {"known": False, "behind": None})
            self.assertEqual(self.api.check_updates(), {"known": False, "behind": None, "update_needed": False})

    def test_update_all_pulls_the_studio_itself_last_and_says_restart(self):
        import time
        p, up = self._studio_with_upstream()
        git(up, "commit", "-q", "--allow-empty", "-m", "two")
        self.api._studio_tool = registry.studio_tool(p)
        self.api._update_kw = {"refresh": lambda t: (True, ""), "build": lambda t: (True, "")}
        self.api.update_all()
        for _ in range(200):
            s = self.api.update_status()
            if not s["running"]:
                break
            time.sleep(0.05)
        self.assertEqual(s["results"][-1]["id"], "studio")
        self.assertEqual(s["results"][-1]["status"], "updated")
        self.assertIn("reopen", s["results"][-1]["message"])
        self.assertEqual(self.api.studio_status()["behind"], 0)

    def test_studio_path_on_mac_reads_the_file_make_app_writes(self):
        clone = os.path.join(self.d, "clone"); os.makedirs(os.path.join(clone, ".git"))
        eng = os.path.join(self.d, "Steezy Studio", "engine"); os.makedirs(eng)
        open(os.path.join(self.d, "Steezy Studio", "studio_dir"), "w").write(clone + "\n")
        with mock.patch.dict(os.environ, {"STEEZY_ENGINE_DIR": eng}), mock.patch.object(sys, "platform", "darwin"):
            self.assertEqual(registry.studio_path(), clone)
        os.remove(os.path.join(self.d, "Steezy Studio", "studio_dir"))
        with mock.patch.dict(os.environ, {"STEEZY_ENGINE_DIR": eng}), mock.patch.object(sys, "platform", "darwin"):
            self.assertIsNone(registry.studio_path())

    def test_studio_path_on_windows_is_the_source_folder(self):
        with mock.patch.object(sys, "platform", "win32"):
            self.assertTrue(os.path.isdir(os.path.join(registry.studio_path(), "studio")))


if __name__ == "__main__":
    unittest.main()


class ShareApi(unittest.TestCase):
    def setUp(self):
        self.api = gui.Api(root="/nonexistent")

    def test_share_options_payload(self):
        o = self.api.share_options()
        self.assertIn("install.sh", o["studio"]["mac"])
        self.assertEqual(len(o["tools"]), 4)
        self.assertIn(False, [t["private"] for t in o["tools"]])

    def test_copy_text_uses_pbcopy(self):
        calls = []
        orig = gui.subprocess.run
        gui.subprocess.run = lambda cmd, **kw: calls.append((cmd, kw["input"]))
        try:
            self.assertEqual(self.api.copy_text("hello"), {"ok": True})
        finally:
            gui.subprocess.run = orig
        self.assertEqual(calls, [(["pbcopy"], "hello")])

    def test_copy_text_failure_is_not_an_error(self):
        orig = gui.subprocess.run
        def boom(*a, **k): raise OSError("no pbcopy")
        gui.subprocess.run = boom
        try:
            self.assertEqual(self.api.copy_text("x"), {"ok": False})
        finally:
            gui.subprocess.run = orig

    def test_invite_friend_rejects_bad_name_without_calling_gh(self):
        res = self.api.invite_friend("bad name!")
        self.assertTrue(res and not any(r["ok"] for r in res))
