import os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from studio import registry, updater as U


def git(path, *a, **kw):
    return subprocess.run(["git", "-C", path, "-c", "user.email=t@t", "-c", "user.name=t", *a],
                          check=True, capture_output=True, text=True, **kw).stdout.strip()


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.builds = []

    def make(self, name):
        """A 'GitHub' bare repo, a clone of it (the tool folder), and a second clone to push new work from."""
        bare = os.path.join(self.d, name + ".git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare], check=True)
        seed = os.path.join(self.d, name + "_seed")
        subprocess.run(["git", "clone", "-q", bare, seed], check=True, capture_output=True)
        open(os.path.join(seed, "f"), "w").close()
        git(seed, "add", "."); git(seed, "commit", "-q", "-m", "one"); git(seed, "push", "-q", "origin", "HEAD:main")
        folder = os.path.join(self.d, "tools", name)
        subprocess.run(["git", "clone", "-q", bare, folder], check=True, capture_output=True)
        t = registry.Tool(id=name, name=name, repo=bare, folder=name, path=folder, build=["x"], app="x.app", platforms=["mac"])
        return t, seed

    def push_new(self, seed):
        git(seed, "commit", "-q", "--allow-empty", "-m", "new"); git(seed, "push", "-q", "origin", "HEAD:main")

    def build(self, ok=True):
        def f(t):
            self.builds.append(t.id); return ok, "" if ok else "boom"
        return f

    def run_one(self, t, **kw):
        return U.update_tool(t, refresh=lambda t: (True, ""), build=kw.pop("build", self.build()), **kw)

    def head(self, t): return git(t.path, "rev-parse", "HEAD")

    def test_up_to_date_does_not_build(self):
        t, _ = self.make("a")
        r = self.run_one(t); self.assertEqual(r.status, U.UP_TO_DATE); self.assertEqual(self.builds, [])

    def test_behind_pulls_and_rebuilds(self):
        t, seed = self.make("a"); self.push_new(seed)
        r = self.run_one(t); self.assertEqual(r.status, U.UPDATED); self.assertEqual(self.builds, ["a"])
        self.assertEqual(self.head(t), git(seed, "rev-parse", "HEAD"))

    def test_dirty_tree_is_skipped_and_untouched(self):
        t, seed = self.make("a"); self.push_new(seed)
        open(os.path.join(t.path, "f"), "w").write("my edit"); before = self.head(t)
        r = self.run_one(t); self.assertEqual(r.status, U.SKIPPED_DIRTY)
        self.assertEqual(self.head(t), before); self.assertEqual(open(os.path.join(t.path, "f")).read(), "my edit")
        self.assertEqual(self.builds, [])

    def test_ahead_is_left_alone(self):
        t, _ = self.make("a"); git(t.path, "commit", "-q", "--allow-empty", "-m", "mine"); before = self.head(t)
        r = self.run_one(t); self.assertEqual(r.status, U.SKIPPED_AHEAD); self.assertEqual(self.head(t), before)

    def test_diverged_is_left_alone(self):
        t, seed = self.make("a"); self.push_new(seed)
        git(t.path, "commit", "-q", "--allow-empty", "-m", "mine"); before = self.head(t)
        r = self.run_one(t); self.assertEqual(r.status, U.SKIPPED_DIVERGED); self.assertEqual(self.head(t), before)

    def test_no_network_leaves_tool_and_reports(self):
        t, _ = self.make("a"); git(t.path, "remote", "set-url", "origin", os.path.join(self.d, "gone.git"))
        r = self.run_one(t); self.assertEqual(r.status, U.NO_NETWORK); self.assertEqual(self.builds, [])

    def test_build_failure_keeps_going_with_other_tools(self):
        a, sa = self.make("a"); b, sb = self.make("b"); self.push_new(sa); self.push_new(sb)
        def build(t):
            self.builds.append(t.id); return (t.id != "a"), "boom"
        results = U.update_all([a, b], refresh=lambda t: (True, ""), build=build)
        self.assertEqual([r.status for r in results], [U.BUILD_FAILED, U.UPDATED]); self.assertEqual(self.builds, ["a", "b"])

    def test_exception_in_one_tool_does_not_stop_the_rest(self):
        a, sa = self.make("a"); b, sb = self.make("b"); self.push_new(sa); self.push_new(sb)
        def build(t):
            if t.id == "a": raise RuntimeError("kaboom")
            self.builds.append(t.id); return True, ""
        results = U.update_all([a, b], refresh=lambda t: (True, ""), build=build)
        self.assertEqual([r.status for r in results], [U.BUILD_FAILED, U.UPDATED])

    def test_unusable_tool_reported_not_raised(self):
        t = registry.Tool("z", "Z", "", "", "/nope", [], "", [], state=registry.NO_ACCESS, message="Z is private. Ask Stefan for access.")
        r = U.update_tool(t); self.assertEqual(r.status, U.UNAVAILABLE); self.assertIn("Ask Stefan", r.message)

    def test_missing_app_builds_even_when_up_to_date(self):
        t, _ = self.make("a")
        r = self.run_one(t, app_exists=lambda t: False); self.assertEqual(r.status, U.UPDATED); self.assertEqual(self.builds, ["a"])

    def test_dry_run_changes_nothing_not_even_refs(self):
        t, seed = self.make("a"); self.push_new(seed)
        before = (self.head(t), git(t.path, "for-each-ref"), git(t.path, "status", "--porcelain"))
        r = self.run_one(t, dry_run=True)
        self.assertEqual(r.status, U.UP_TO_DATE)   # not fetched, so it only knows what it last saw
        self.assertEqual(before, (self.head(t), git(t.path, "for-each-ref"), git(t.path, "status", "--porcelain")))
        self.assertEqual(self.builds, [])
        git(t.path, "fetch", "-q")
        r = self.run_one(t, dry_run=True); self.assertEqual(r.status, U.WOULD_UPDATE)
        self.assertEqual(self.builds, [])


if __name__ == "__main__":
    unittest.main()
