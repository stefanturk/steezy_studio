import io, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build"))
import pi_or_mac as P


def opener_for(answers):
    """A fake urlopen: url -> dict (JSON), bytes, or an exception to raise."""
    asked = []

    def op(url, timeout=None):
        asked.append(url)
        a = answers.get(url, OSError("refused"))
        if isinstance(a, Exception):
            raise a
        return io.BytesIO(a if isinstance(a, bytes) else json.dumps(a).encode())
    op.asked = asked
    return op


LIGHTS = {"audio_kick_level_raw": 1, "audio_sound_floor": 2, "scene": "x"}
VIDEO = {"mode": "logo", "angles": [], "bands": ["Litty D"], "show": False}


class Addresses(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(P.normalize("video.lan"), "http://video.lan")
        self.assertEqual(P.normalize(" 192.168.8.161:9200 "), "http://192.168.8.161:9200")
        self.assertEqual(P.normalize("http://sound.lan:9000/state"), "http://sound.lan:9000")
        self.assertEqual(P.normalize("mypi.local"), "http://mypi.local")
        for bad in ("", "   ", "ftp://x", "http://", "a b", "x:notaport"):
            self.assertIsNone(P.normalize(bad), bad)


class Fingerprints(unittest.TestCase):
    def test_each_app_only_recognises_its_own_pi(self):
        self.assertTrue(P.lights_state(LIGHTS)); self.assertFalse(P.lights_state(VIDEO))
        self.assertTrue(P.video_state(VIDEO)); self.assertFalse(P.video_state(LIGHTS))
        self.assertFalse(P.video_state({})); self.assertFalse(P.lights_state({"ok": True}))

    def test_looks_like_needs_the_right_json(self):
        op = opener_for({"http://a/state": LIGHTS, "http://b/state": b"<html>router</html>", "http://c/state": [1, 2]})
        self.assertTrue(P.looks_like("http://a", P.lights_state, opener=op))
        self.assertFalse(P.looks_like("http://b", P.lights_state, opener=op))      # a router's page
        self.assertFalse(P.looks_like("http://c", P.lights_state, opener=op))      # JSON, but not an object
        self.assertFalse(P.looks_like("http://d", P.lights_state, opener=op))      # nothing there
        self.assertFalse(P.looks_like("http://a", P.video_state, opener=op))       # the other app's Pi


class Finding(unittest.TestCase):
    def test_first_recognised_wins_and_each_is_tried_once(self):
        tried = []
        probe = lambda u: tried.append(u) or u == "http://video.lan:9200"
        self.assertEqual(P.find_pi(["video.lan", "VIDEO.lan", "", "video.lan:9200", "x.lan"], probe), "http://video.lan:9200")
        self.assertEqual(tried, ["http://video.lan", "http://video.lan:9200"])

    def test_nothing_found(self):
        self.assertIsNone(P.find_pi(["a", "b"], lambda u: False))


class FakeWindow:
    def __init__(self): self.loaded = []
    def load_url(self, u): self.loaded.append(u)


class StartPage(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.pis = {"http://video.lan"}
        self.started = []

        def run_here():
            self.started.append(1)
            return True, "http://127.0.0.1:9200/"
        self.s = P.Start("Video Streamer", self.d, ["video.lan", "video.lan:9200"], lambda u: u in self.pis, run_here, "the show")
        self.w = FakeWindow(); self.s.attach(self.w)

    def test_found_pi_is_offered_and_using_it_starts_nothing_here(self):
        look = self.s.look()
        self.assertEqual(look["found"], "http://video.lan"); self.assertEqual(look["last"], "pi")
        self.assertTrue(self.s.use_pi(look["found"])["ok"])
        self.assertEqual(self.w.loaded, ["http://video.lan/"])
        self.assertEqual(self.started, [])
        self.assertEqual(P.load_memory(self.d), {"pi": "http://video.lan", "last": "pi"})

    def test_remembered_pi_is_tried_first(self):
        self.pis = {"http://192.168.8.50:9200", "http://video.lan"}
        P.save_memory(self.d, pi="http://192.168.8.50:9200")
        self.assertEqual(self.s.look()["found"], "http://192.168.8.50:9200")

    def test_no_pi_defaults_to_this_mac_and_running_here_is_remembered(self):
        self.pis = set()
        look = self.s.look()
        self.assertIsNone(look["found"]); self.assertEqual(look["last"], "mac")
        self.assertTrue(self.s.run_here()["ok"])
        self.assertEqual(self.w.loaded, ["http://127.0.0.1:9200/"])
        self.assertEqual(P.load_memory(self.d)["last"], "mac")

    def test_last_choice_mac_stays_the_default_even_with_a_pi_about(self):
        P.save_memory(self.d, last="mac")
        look = self.s.look()
        self.assertEqual(look["found"], "http://video.lan"); self.assertEqual(look["last"], "mac")

    def test_connect_to_your_own_pi_by_address(self):
        self.pis = {"http://mypi.local:9000"}
        bad = self.s.connect("not an address")
        self.assertFalse(bad["ok"]); self.assertIn("doesn't look like an address", bad["message"])
        nothing = self.s.connect("10.0.0.9")
        self.assertFalse(nothing["ok"]); self.assertIn("Nothing at http://10.0.0.9 is running Video Streamer", nothing["message"])
        self.assertTrue(self.s.connect("mypi.local:9000")["ok"])
        self.assertEqual(self.w.loaded, ["http://mypi.local:9000/"])
        self.assertEqual(P.load_memory(self.d)["pi"], "http://mypi.local:9000")

    def test_a_pi_that_went_away_is_not_opened(self):
        self.pis = set()
        r = self.s.use_pi("http://video.lan")
        self.assertFalse(r["ok"]); self.assertEqual(self.w.loaded, [])

    def test_failing_to_start_here_is_a_message_never_a_hang(self):
        self.s._run_here = lambda: (False, "Video Streamer could not start. (port busy)")
        self.assertEqual(self.s.run_here(), {"ok": False, "message": "Video Streamer could not start. (port busy)"})

        def boom(): raise OSError("no ffmpeg")
        self.s._run_here = boom
        r = self.s.run_here()
        self.assertFalse(r["ok"]); self.assertIn("no ffmpeg", r["message"])
        self.assertEqual(self.w.loaded, [])

    def test_memory_survives_garbage(self):
        with open(os.path.join(self.d, P.MEMORY), "w") as f:
            f.write("{not json")
        self.assertEqual(P.load_memory(self.d), {})
        P.save_memory(self.d, last="mac")
        self.assertEqual(P.load_memory(self.d), {"last": "mac"})

    def test_after_leaving_the_start_page_the_functions_refuse(self):
        # The Pi's page (or anything it loads) gets the same window.pywebview.api: it must not drive the Mac.
        self.assertTrue(self.s.use_pi("http://video.lan")["ok"])
        for r in (self.s.run_here(), self.s.connect("video.lan"), self.s.use_pi("http://video.lan"), self.s.look()):
            self.assertFalse(r["ok"])
        self.assertEqual(self.started, []); self.assertEqual(self.w.loaded, ["http://video.lan/"])

    def test_memory_of_the_wrong_shape_is_ignored(self):
        for junk in ({"pi": 5, "last": ["x"]}, {"pi": "", "last": "elsewhere"}):
            with open(os.path.join(self.d, P.MEMORY), "w") as f:
                json.dump(junk, f)
            look = self.s.look()                           # never raises: the page would hang on "Looking..."
            self.assertEqual(look["found"], "http://video.lan"); self.assertIn(look["last"], ("pi", "mac"))

    def test_page_names_the_app_safely(self):
        html = P.page("A <b> & C")
        self.assertIn("A &lt;b&gt; &amp; C", html); self.assertNotIn("A <b>", html)
        self.assertIn("pywebview.api.look()", html)

    def test_page_always_shows_the_buttons_even_if_looking_fails(self):
        html = P.page("X")
        self.assertIn("catch", html)


class ExposeWindow(FakeWindow):
    """Just enough of a pywebview Window for its real bridge (webview.util.js_bridge_call)."""
    def __init__(self, js_api=None):
        super().__init__(); self._js_api, self._functions, self.js = js_api, {}, []
    def expose(self, *fs):
        for f in fs:
            self._functions[f.__name__] = f
    def evaluate_js(self, js): self.js.append(js)


class Bridge(unittest.TestCase):
    """The page reaches Python only by four exact names. pywebview follows dotted paths on a js_api object,
    underscores and all, so a page could otherwise walk to anything the object holds (2026-11-19 review)."""

    def make(self, run_here):
        s = P.Start("Video Streamer", tempfile.mkdtemp(), ["video.lan"], lambda u: False, run_here, "the show")
        w = ExposeWindow(js_api=s)                   # what the launchers pass: create_window(..., js_api=start)
        s.attach(w)
        return s, w

    def test_attach_exposes_only_the_page_functions_and_drops_the_js_api(self):
        s, w = self.make(lambda: (True, "http://127.0.0.1:1/"))
        self.assertEqual(sorted(w._functions), ["connect", "look", "run_here", "use_pi"])
        self.assertIsNone(w._js_api)

    def test_the_real_bridge_cannot_reach_private_attributes(self):
        try:
            from webview import util
        except ImportError:
            self.skipTest("pywebview not installed")
        import subprocess, time

        class Local:                                  # like the launchers' Local: it holds subprocess.Popen
            popen = subprocess.Popen
            def __call__(self): return True, "http://127.0.0.1:1/"
        s, w = self.make(Local())
        marker = os.path.join(tempfile.mkdtemp(), "pwned")
        for name, args in (("_run_here.popen", [["/usr/bin/touch", marker]]),
                           ("run_here.__self__._run_here.popen", [["/usr/bin/touch", marker]]),
                           ("look.__func__.__globals__.clear", []),
                           ("look.__globals__.clear", []), ("attach", [None])):
            util.js_bridge_call(w, name, args, "1")
        util.js_bridge_call(w, "look", [], "2")
        time.sleep(0.5)
        self.assertFalse(os.path.exists(marker))
        self.assertTrue(callable(P.normalize))        # the module's globals are intact
        self.assertTrue(any('"found"' in js or "found" in js for js in w.js))   # the real names still work
