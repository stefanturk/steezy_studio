import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from studio import feedback, feedback_config, gui
import feedback_sheet


class Env(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.logs = tempfile.mkdtemp()
        self.sent = []

    def post_ok(self, payload, url):
        self.sent.append((payload, url)); return True

    def post_fail(self, payload, url):
        return False


class T(Env):
    def test_empty_note_and_no_url_are_refused(self):
        self.assertFalse(feedback.send("  ", "beat_thief", False, "abc", url="u", state=self.state, post=self.post_ok)["ok"])
        r = feedback.send("hi", "beat_thief", False, "abc", url="", state=self.state, post=self.post_ok)
        self.assertFalse(r["ok"]); self.assertEqual(self.sent, [])

    def test_payload_shape_and_anonymous_id(self):
        feedback.send("it crashed", "beat_thief", False, "abc1234", url="u", state=self.state, post=self.post_ok)
        (p, url), = self.sent
        self.assertEqual(url, "u")
        self.assertEqual((p["note"], p["tool"], p["version"], p["log"], p["website"]), ("it crashed", "beat_thief", "abc1234", "", ""))
        self.assertEqual(p["token"], feedback_config.TOKEN)
        self.assertEqual(p["id"], feedback.tester_id(self.state))      # same id every time
        self.assertEqual(len(p["id"]), 12)

    def test_note_is_capped(self):
        feedback.send("x" * 5000, "t", False, "v", url="u", state=self.state, post=self.post_ok)
        self.assertEqual(len(self.sent[0][0]["note"]), feedback.MAX_NOTE)

    def test_log_tail_is_the_last_lines_with_home_removed(self):
        home = os.path.expanduser("~")
        with open(os.path.join(self.logs, "beat_thief.log"), "w") as f:
            f.write("".join("line %d %s/secret\n" % (i, home) for i in range(100)))
        feedback.send("bug", "beat_thief", True, "v", url="u", state=self.state, logs_dir=self.logs, post=self.post_ok)
        log = self.sent[0][0]["log"]
        self.assertIn("line 99", log); self.assertNotIn("line 50 ", log)
        self.assertNotIn(home, log); self.assertIn("~/secret", log)

    def test_no_log_without_the_box_ticked_or_for_unknown_tool(self):
        self.assertEqual(feedback.build_payload("n", "beat_thief", False, "v", self.state, self.logs)["log"], "")
        self.assertEqual(feedback.log_tail("nope", logs_dir=self.logs), "")

    def test_failed_send_is_kept_and_goes_next_time(self):
        r = feedback.send("first", "t", False, "v", url="u", state=self.state, post=self.post_fail)
        self.assertTrue(r["ok"]); self.assertIn("saved", r["message"])
        self.assertEqual(feedback.pending(self.state), 1)
        feedback.send("second", "t", False, "v", url="u", state=self.state, post=self.post_ok)
        self.assertEqual([p["note"] for p, _ in self.sent], ["first", "second"])
        self.assertEqual(feedback.pending(self.state), 0)

    def test_flush_stops_at_first_failure(self):
        for n in "abc":
            feedback.send(n, "t", False, "v", url="u", state=self.state, post=self.post_fail)
        calls = []
        feedback.flush("u", self.state, lambda p, u: calls.append(p["note"]) or False)
        self.assertEqual(calls, ["a"]); self.assertEqual(feedback.pending(self.state), 3)

    def test_outbox_is_capped(self):
        for i in range(feedback.OUTBOX_MAX + 5):
            feedback.send("n%d" % i, "t", False, "v", url="u", state=self.state, post=self.post_fail)
        self.assertEqual(feedback.pending(self.state), feedback.OUTBOX_MAX)

    def test_post_reads_ok_from_json_reply(self):
        class R:
            def __init__(s, b): s.b = b
            def read(s): return s.b
            def __enter__(s): return s
            def __exit__(s, *a): pass
        import urllib.request
        real = urllib.request.urlopen
        try:
            urllib.request.urlopen = lambda req, timeout=0: R(b'{"ok": true}')
            self.assertTrue(feedback._post({"a": 1}, "http://x"))
            urllib.request.urlopen = lambda req, timeout=0: R(b'{"ok": false}')
            self.assertEqual(feedback._post({"a": 1}, "http://x"), feedback.REJECTED)   # the sheet said no
            urllib.request.urlopen = lambda req, timeout=0: R(b'{"ok": false, "full": true}')
            self.assertFalse(feedback._post({"a": 1}, "http://x"))                      # full today: later
            def boom(req, timeout=0): raise OSError("offline")
            urllib.request.urlopen = boom
            self.assertFalse(feedback._post({"a": 1}, "http://x"))
        finally:
            urllib.request.urlopen = real


class Privacy(Env):
    """The log goes with every note (Stefan, 2026-11-19), minus what identifies the person or could be abused."""

    def test_names_addresses_and_secrets_come_out_of_the_log(self):
        import getpass, socket
        user, host = getpass.getuser(), socket.gethostname()
        text = ("hello from %s on %s (%s)\n" % (user, host, host.split(".")[0]) +
                "mail me@example.com, token=abc123secret X-Auth-Token: zzz9 ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\n"
                "pi at 192.168.8.161:9200 and 10.0.0.2, router 172.16.5.1; public 8.8.8.8 and 2606:4700::1111 at 12:30:45\n")
        out = feedback.scrub(text)
        for gone in (user, host, host.split(".")[0], "me@example.com", "abc123secret", "zzz9",
                     "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "8.8.8.8", "2606:4700::1111"):
            self.assertNotIn(gone, out, gone)
        for kept in ("192.168.8.161:9200", "10.0.0.2", "172.16.5.1", "hello from", "12:30:45"):
            self.assertIn(kept, out, kept)                                   # LAN addresses help fix bugs

    def test_a_short_login_name_does_not_eat_ordinary_words(self):
        self.assertEqual(feedback.scrub("stefan's mix restarted", user="st", host="box"), "stefan's mix restarted")
        self.assertEqual(feedback.scrub("user st here", user="st", host="box"), "user ~user here")

    def test_a_huge_log_is_read_from_its_end(self):
        path = os.path.join(self.logs, "movie_maker.log")
        with open(path, "w") as f:
            f.write("x" * 100 + "\n")
            for i in range(200000):
                f.write("line %d\n" % i)
        tail = feedback.log_tail("movie_maker", logs_dir=self.logs)
        self.assertTrue(tail.endswith("line 199999")); self.assertIn("line 199960", tail)
        self.assertNotIn("line 199959\n", tail)

    def test_big_logs_are_trimmed_in_place_keeping_the_newest_lines(self):
        path = os.path.join(self.logs, "beat_thief.log")
        with open(path, "w") as f:
            for i in range(400000):
                f.write("line %d of the log\n" % i)
        writer = open(path, "a")                        # a running app keeps appending to the same file
        feedback.trim_logs(self.logs, limit=1_000_000, keep=200_000)
        writer.write("after trim\n"); writer.close()
        data = open(path).read()
        self.assertLess(len(data), 260_000)
        self.assertTrue(data.startswith("line ")); self.assertIn("line 399999 of the log\nafter trim\n", data)

    def test_a_note_the_sheet_rejects_is_dropped_not_retried_forever(self):
        feedback.send("a", "t", False, "v", url="u", state=self.state, post=lambda p, u: False)   # offline: kept
        self.assertEqual(feedback.pending(self.state), 1)
        r = feedback.send("b", "t", False, "v", url="u", state=self.state, post=lambda p, u: feedback.REJECTED)
        self.assertFalse(r["ok"]); self.assertEqual(feedback.pending(self.state), 0)

    def test_an_invisible_only_note_is_refused_up_front(self):
        # JavaScript's trim() strips U+FEFF and the sheet then refused the note; Python's strip() kept it.
        r = feedback.send("\ufeff \u200b", "t", False, "v", url="u", state=self.state, post=self.post_ok)
        self.assertFalse(r["ok"]); self.assertEqual(self.sent, [])


class ApiT(unittest.TestCase):
    def test_hidden_until_a_url_is_set(self):
        old = feedback_config.URL
        try:
            feedback_config.URL = ""
            self.assertEqual(gui.Api().feedback_options(), {"enabled": False, "tools": [], "pending": 0})
        finally:
            feedback_config.URL = old

    def test_shipped_config_has_the_token_and_matching_script(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "feedback", "apps_script.gs")) as f:
            self.assertIn('"%s"' % feedback_config.TOKEN, f.read())


class FakeSheet:
    def __init__(self, values): self.values, self.updates = values, []
    def get_all_values(self): return self.values
    def update_cell(self, r, c, v): self.updates.append((r, c, v))


class SheetT(unittest.TestCase):
    def sheet(self):
        head = ["time", "id", "status", "tool", "version", "os", "note", "log"]
        return FakeSheet([head,
                          ["t1", "i", "new", "beat_thief", "abc", "Darwin", "crashes", ""],
                          ["t2", "i", "done", "ableton_loader", "abc", "Darwin", "old", ""],
                          ["t3", "i", "", "movie_maker", "abc", "Darwin", "blank status counts as new", ""]])

    def test_lists_only_new_by_default(self):
        self.assertEqual([n for n, _ in feedback_sheet.rows(self.sheet())], [2, 4])
        self.assertEqual([n for n, _ in feedback_sheet.rows(self.sheet(), True)], [2, 3, 4])

    def test_done_and_note_write_the_right_cells(self):
        s = self.sheet()
        feedback_sheet.main(["done", "2", "4"], sheet=s)
        self.assertEqual(s.updates, [(2, 3, "done"), (4, 3, "done")])
        s = self.sheet()
        feedback_sheet.main(["note", "2", "fixed"], sheet=s)
        self.assertEqual(s.updates, [(2, 9, "fixed"), (2, 3, "done")])


if __name__ == "__main__":
    unittest.main()
