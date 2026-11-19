import json, os, re, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from studio import registry as R


def write(d, name, obj):
    p = os.path.join(d, name)
    with open(p, "w") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))
    return p


HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_IDS = [t["id"] for t in json.load(open(os.path.join(HERE, "registry.json")))["tools"]]
GOOD = {"id": "a", "name": "A", "repo": "https://x/a.git", "folder": "a", "build": ["./m.sh"], "app": "A.app"}


class Shipped(unittest.TestCase):
    """The one tool list is registry.json. Everything else must agree with it, so adding a tool
    is one edit there and these say what else (the installer's --list, the README) was missed."""

    def test_every_tool_says_what_it_is_for_and_what_it_needs(self):
        for t in R.load_tools(root="/nonexistent"):
            self.assertTrue(t.about, t.id + " has no 'about' line")
            self.assertTrue(t.needs, t.id + " has no 'needs' lines")

    def test_install_sh_list_names_every_tool(self):
        with open(os.path.join(HERE, "install.sh")) as f:
            text = f.read()
        listed = re.search(r'--list.*?\n\s*echo "([^"]+)"', text, re.S).group(1)
        for tool_id in REGISTRY_IDS:
            self.assertIn(tool_id, listed.split(), tool_id + " missing from install.sh --list")

    def test_every_tool_has_an_icon_shipped_in_the_studio(self):
        # The art ships inside the Studio: a tool that isn't installed has no folder to read it from.
        for t in R.load_tools(root="/nonexistent"):
            self.assertTrue(t.icon, t.id + " has no 'icon'")
            self.assertTrue(os.path.isfile(os.path.join(HERE, "ui", t.icon)), t.id + ": ui/" + t.icon + " is missing")

    def test_readme_names_every_tool(self):
        with open(os.path.join(HERE, "README.md")) as f:
            head = f.read().lower().replace("_", " ")
        for tool_id in REGISTRY_IDS:
            self.assertIn(tool_id.replace("_", " "), head, tool_id + " missing from the README")


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.root = os.path.join(self.d, "root")
        os.makedirs(self.root)

    def load(self, obj, **kw):
        return R.load_tools(write(self.d, "r.json", obj), root=self.root, **kw)

    def test_real_registry_loads_all_tools(self):
        tools = R.load_tools(root=self.root)
        self.assertEqual([t.id for t in tools], REGISTRY_IDS)
        self.assertTrue(len(tools) >= 4)
        self.assertTrue(all(t.state == R.NOT_INSTALLED for t in tools))

    def test_icon_is_read_and_defaults_to_empty(self):
        (a, b) = self.load({"tools": [dict(GOOD, icon="icons/a.svg"), dict(GOOD, id="b", folder="b")]})
        self.assertEqual(a.icon, "icons/a.svg"); self.assertEqual(b.icon, "")

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
