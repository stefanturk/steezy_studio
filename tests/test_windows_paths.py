import os
import sys

from studio import gui, platform_paths, registry, updater


def win(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("STEEZY_ENGINE_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/x/AppData/Local")


def test_engine_paths_on_windows(monkeypatch):
    win(monkeypatch)
    e = platform_paths.engine_dir()
    assert e.endswith(os.path.join("Steezy Studio", "engine"))
    assert platform_paths.python_in(e).endswith("python.exe")
    assert platform_paths.python_in(e, windowed=True).endswith("pythonw.exe")


def test_engine_paths_on_mac(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("STEEZY_ENGINE_DIR", raising=False)
    assert platform_paths.engine_dir().endswith("Library/Application Support/Steezy Studio/engine")
    assert platform_paths.python_in("/e").endswith("python/bin/python3")


def test_windows_build_is_a_noop(monkeypatch):
    win(monkeypatch)
    t = registry.load_tools(root="/nonexistent")[0]
    assert updater.default_build(t) == (True, "nothing to build on Windows")


def test_windows_app_is_the_source_folder_when_windows_run_is_set(monkeypatch):
    win(monkeypatch)
    t = registry.load_tools(root="/nonexistent")[0]
    t.windows_run = []
    assert gui.app_for(t) is None
    t.windows_run = ["-m", "thing"]
    assert gui.app_for(t) == t.path


def test_open_tool_on_windows_starts_pythonw(monkeypatch, tmp_path):
    win(monkeypatch)
    monkeypatch.setenv("STEEZY_ENGINE_DIR", str(tmp_path / "engine"))
    calls = []
    monkeypatch.setattr(gui.subprocess, "Popen", lambda argv, **kw: calls.append((argv, kw)))
    reg = tmp_path / "r.json"
    reg.write_text('{"tools":[{"id":"a","name":"A","repo":"x","folder":"a","build":["b"],"app":"A.app","platforms":["mac","windows"],"windows_run":["-m","a"]}]}')
    (tmp_path / "root" / "a" / ".git").mkdir(parents=True)
    api = gui.Api(str(reg), str(tmp_path / "root"))
    assert api.open_tool("a")["ok"]
    argv, kw = calls[0]
    assert argv[0].endswith("pythonw.exe") and argv[1:] == ["-m", "a"] and kw["cwd"].endswith("a")
