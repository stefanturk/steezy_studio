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

    def test_tiles_carry_the_tool_icon(self):
        self.assertEqual([t["icon"] for t in self.api.list_tools()], ["", ""])

    def test_only_tools_you_have_get_a_tile_the_rest_are_offered(self):
        self.assertEqual([t["shown"] for t in self.api.list_tools()], [False, False])
        self.repo("a")
        self.assertEqual([t["shown"] for t in self.api.list_tools()], [True, False])

    def test_a_tool_being_installed_keeps_its_tile(self):
        self.api._installing = "b"
        self.assertEqual([t["shown"] for t in self.api.list_tools()], [False, True])

    def test_tool_for_another_computer_is_offered_but_flagged_unsupported(self):
        with open(self.reg, "w") as f:
            json.dump({"tools": [{"id": "w", "name": "W", "repo": "x", "folder": "w", "build": ["./m"], "app": "W.app",
                                  "platforms": ["windows"], "about": "Does W.", "needs": ["Windows"]}]}, f)
        (t,) = gui.Api(self.reg, self.root, app_dirs=(self.apps,)).list_tools() if not gui.platform_paths.is_windows() else []
        self.assertFalse(t["shown"] and t["supported"])
        self.assertFalse(t["supported"]); self.assertEqual((t["about"], t["needs"]), ("Does W.", ["Windows"]))

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

    def test_open_is_locked_while_a_tool_updates_or_installs(self):
        self.repo("a"); os.makedirs(os.path.join(self.apps, "A.app"))
        self.assertTrue(self.api.list_tools()[0]["openable"])
        self.api._working_on = "a"
        a = self.api.list_tools()[0]
        self.assertFalse(a["openable"]); self.assertTrue(a["updating"])
        self.assertFalse(self.api.open_tool("a")["ok"])               # never rebuilt underneath itself
        self.api._working_on, self.api._installing = None, "a"
        self.assertFalse(self.api.list_tools()[0]["openable"])

    def test_a_tool_waiting_its_turn_opens_and_skips_this_update(self):
        # One slow tool (pip, a big build) used to keep every other tool's Open greyed out for minutes.
        self.repo("a"); os.makedirs(os.path.join(self.apps, "A.app"))
        self.api._queued = {"a"}
        self.assertTrue(self.api.list_tools()[0]["openable"])
        with mock.patch.object(gui.subprocess, "Popen") as popen:
            self.assertTrue(self.api.open_tool("a")["ok"])
        popen.assert_called_once()
        self.assertNotIn("a", self.api._queued); self.assertIn("a", self.api._skipped)
        self.assertTrue(self.api._skip(self.api._tools()[0]))         # the running update passes it by

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

    def test_polling_the_tiles_does_not_rerun_git_every_time(self):
        p = self.repo("a"); gui._VERSIONS.clear()
        real, calls = gui._git, []
        with mock.patch.object(gui, "_git", side_effect=lambda *a: calls.append(a) or real(*a)):
            self.api.list_tools(); first = len(calls)
            self.api.list_tools(); self.api.list_tools()
            self.assertEqual(len(calls), first)                     # the page polls every 0.7 s while updating
            git(p, "commit", "-q", "--allow-empty", "-m", "two")    # a new commit is seen at once
            self.assertEqual(self.api.list_tools()[0]["version"], real(p, "rev-parse", "--short", "HEAD"))

    def test_untracked_files_are_not_local_changes(self):
        p = self.repo("a"); gui._VERSIONS.clear()
        open(os.path.join(p, "stray.log"), "w").write("x")
        self.assertFalse(gui.version_of(p)["dirty"])

    def test_a_build_that_failed_at_this_commit_does_not_rerun_every_launch(self):
        from studio import updater
        self.repo("a"); self.repo("b"); os.makedirs(os.path.join(self.apps, "B.app"))     # A has no app
        with mock.patch.object(registry, "studio_path", return_value=None):
            self.api._studio_tool = None
            self.assertTrue(self.api.needs_update())
            a = self.api._tools()[0]
            updater._record_build_failure(a)
            self.assertFalse(self.api.needs_update())          # same code, same failure: wait for new code
            git(a.path, "commit", "-q", "--allow-empty", "-m", "fix")
            self.assertTrue(self.api.needs_update())

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

    def test_update_all_pulls_the_studio_itself_first_and_says_restart(self):
        # First: the tools' builds copy shared files from the Studio's clone (build/pi_or_mac.py, lib.sh),
        # so they must see the new ones in the same run, not a launch later.
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
        self.assertEqual(s["results"][0]["id"], "studio")
        self.assertEqual(s["results"][0]["status"], "updated")
        self.assertIn("reopen", s["results"][0]["message"])
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
        self.assertEqual(len(o["tools"]), len(registry.load_tools()))
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


class PageBridge(unittest.TestCase):
    """The Studio page reaches the Api only by exact names (window.expose), never through js_api:
    pywebview follows dotted paths on a js_api object, underscores and all (2026-11-19 review)."""

    class Window:
        def __init__(self): self._functions, self._js_api, self.js = {}, None, []
        def expose(self, *fs):
            for f in fs:
                self._functions[f.__name__] = f
        def evaluate_js(self, js): self.js.append(js)

    def test_the_page_gets_exactly_the_functions_it_calls(self):
        import re
        html = open(os.path.join(os.path.dirname(gui.UI_FILE), "index.html")).read()
        used = set(re.findall(r"pywebview\.api\.([a-z_]+)\(", html))
        self.assertEqual(set(gui.PAGE_FUNCTIONS), used)
        w = self.Window(); gui.expose_api(w, gui.Api())
        self.assertEqual(set(w._functions), used)

    def test_the_real_bridge_cannot_walk_into_the_api(self):
        try:
            from webview import util
        except ImportError:
            self.skipTest("pywebview not installed")
        import time
        api = gui.Api(); w = self.Window(); gui.expose_api(w, api)
        for name, args in (("_update_kw.update", [{"build": "x"}]), ("list_tools.__func__.__globals__.clear", []),
                           ("list_tools.__self__._update_kw.update", [{"x": 1}]), ("__init__", [])):
            util.js_bridge_call(w, name, args, "1")
        time.sleep(0.3)
        self.assertEqual(api._update_kw, {}); self.assertTrue(callable(gui.app_for))
