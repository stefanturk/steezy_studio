from studio import registry, share


def tools():
    return registry.load_tools(root="/nonexistent")


def test_whole_studio_mac_command_has_no_tool_args():
    c = share.mac_command()
    assert c.startswith('bash -c "$(curl -fsSL https://raw.githubusercontent.com/stefanturk/steezy_studio/main/install.sh)"')
    assert " _ " not in c


def test_single_and_multi_tool_mac_command():
    assert share.mac_command(["beat_thief"]).endswith('install.sh)" _ beat_thief')
    assert share.mac_command(["a", "b"]).endswith(" _ a b")


def test_windows_command():
    assert share.windows_command().endswith("install.ps1)))")
    assert share.windows_command(["session_sync"]).endswith("))) session_sync")


def test_options_cover_every_registry_tool_and_mark_private():
    opts = share.share_options(tools())
    by_id = {r["id"]: r for r in opts["tools"]}
    assert set(by_id) == {"beat_thief", "ableton_loader", "session_sync", "movie_maker"}
    assert by_id["ableton_loader"]["private"] and by_id["movie_maker"]["private"]
    assert not by_id["beat_thief"]["private"] and not by_id["session_sync"]["private"]
    assert "windows" not in by_id["movie_maker"]["commands"]
    assert "beat_thief" in by_id["beat_thief"]["commands"]["mac"]


def test_broken_entries_are_left_out():
    t = registry.load_tools(registry_path="/nope.json")
    assert share.share_options(t)["tools"] == []
