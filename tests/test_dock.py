import os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "build"))
import appswap, dock_repin

if sys.platform.startswith("win"):
    raise unittest.SkipTest("Mac app and Dock helpers")


def pin(path, label="X"):
    return {"tile-data": {"file-label": label, "book": b"stale",
                          "file-data": {"_CFURLString": dock_repin.file_url(path), "_CFURLStringType": 15}}}


class Repin(unittest.TestCase):
    def test_pin_moves_to_the_new_app_and_loses_its_stale_bookmark(self):
        prefs = {"persistent-apps": [pin("/Users/me/Applications/Beat Thief.app", "Beat Thief"), pin("/Applications/Other.app")]}
        n = dock_repin.repoint(prefs, "/Users/me/Applications/Beat Thief.app", "/Applications/Beat Thief.app")
        self.assertEqual(n, 1)
        moved, other = prefs["persistent-apps"]
        self.assertEqual(moved["tile-data"]["file-data"]["_CFURLString"], "file:///Applications/Beat%20Thief.app/")
        self.assertNotIn("book", moved["tile-data"]); self.assertIn("book", other["tile-data"])

    def test_nothing_pinned_changes_nothing(self):
        prefs = {"persistent-apps": [pin("/Applications/Other.app")]}
        self.assertEqual(dock_repin.repoint(prefs, "/a/Old.app", "/b/Old.app"), 0)

    def test_never_points_a_pin_at_an_app_that_is_not_there(self):
        self.assertEqual(dock_repin.repin("/a/Old.app", "/nonexistent/New.app"), 0)


class Swap(unittest.TestCase):
    def make(self, root, name, marker):
        p = os.path.join(root, name); os.makedirs(p)
        open(os.path.join(p, "marker"), "w").write(marker); return p

    def test_new_app_replaces_the_old_and_nothing_is_left_behind(self):
        d = tempfile.mkdtemp()
        final = self.make(d, "A.app", "old"); staged = self.make(d, ".A.app.building", "new")
        appswap.swap(staged, final)
        self.assertEqual(open(os.path.join(final, "marker")).read(), "new")
        self.assertEqual(sorted(os.listdir(d)), ["A.app"])

    def test_first_install_just_moves_it_in(self):
        d = tempfile.mkdtemp()
        staged = self.make(d, ".B.app.building", "new"); final = os.path.join(d, "B.app")
        appswap.swap(staged, final)
        self.assertEqual(sorted(os.listdir(d)), ["B.app"])

    def test_fallback_when_the_atomic_swap_is_unavailable(self):
        d = tempfile.mkdtemp()
        final = self.make(d, "C.app", "old"); staged = self.make(d, ".C.app.building", "new")
        real = appswap._swap_atomically
        appswap._swap_atomically = lambda a, b: False
        try:
            appswap.swap(staged, final)
        finally:
            appswap._swap_atomically = real
        self.assertEqual(open(os.path.join(final, "marker")).read(), "new")
        self.assertEqual(sorted(os.listdir(d)), ["C.app"])

    def test_fallback_puts_the_old_app_back_if_the_new_one_cannot_move_in(self):
        d = tempfile.mkdtemp()
        final = self.make(d, "D.app", "old"); staged = self.make(d, ".D.app.building", "new")
        real_swap, real_rename = appswap._swap_atomically, appswap.os.rename
        calls = []
        def rename(a, b):
            calls.append(a)
            if a == staged:
                raise OSError("disk full")
            return real_rename(a, b)
        appswap._swap_atomically, appswap.os.rename = (lambda a, b: False), rename
        try:
            with self.assertRaises(OSError):
                appswap.swap(staged, final)
        finally:
            appswap._swap_atomically, appswap.os.rename = real_swap, real_rename
        self.assertEqual(open(os.path.join(final, "marker")).read(), "old")       # never left with no app


class Builds(unittest.TestCase):
    def test_building_somewhere_else_never_deletes_the_installed_studio(self):
        # `./make_app.sh /tmp/x` used to rm -rf "/Applications/Steezy Studio.app"; and for a user who
        # can't write /Applications, that failing rm stopped every build under set -e.
        sh = open(os.path.join(HERE, "make_app.sh")).read()
        self.assertNotIn('rm -rf "/Applications/Steezy Studio.app"', sh)


if __name__ == "__main__":
    unittest.main()
