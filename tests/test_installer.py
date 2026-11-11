"""The Install button: clone, packages, build, and taking a half install back out."""
import json
import os
import subprocess
import sys
import time

from studio import gui, installer, registry, updater

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]


def _remote(base, name):
    p = os.path.join(base, name)
    os.makedirs(p)
    open(os.path.join(p, "requirements.txt"), "w").write("")
    subprocess.run(["git", "init", "-q", "-b", "main", p], check=True)
    subprocess.run(GIT + ["-C", p, "add", "-A"], check=True)
    subprocess.run(GIT + ["-C", p, "commit", "-qm", "init"], check=True)
    return p


def _registry(tmp_path, **extra):
    reg = tmp_path / "r.json"
    entry = {"id": "bt", "name": "Beat Thief", "repo": "https://github.com/x/bt.git", "folder": "bt",
             "build": ["./make_app.sh"], "app": "BT.app", "platforms": ["mac", "windows"], "windows_run": ["gui.py"]}
    entry.update(extra)
    reg.write_text(json.dumps({"tools": [entry, {"id": "mm", "name": "Movie Maker", "repo": "x", "folder": "mm",
                                                 "build": ["b"], "app": "MM.app", "platforms": ["mac"]}]}))
    return str(reg)


def _tool(tmp_path, root, **extra):
    return registry.load_tools(_registry(tmp_path, **extra), str(root))[0]


def ok(t):
    return True, ""


def test_clone_then_refresh_then_build(tmp_path, monkeypatch):
    base = tmp_path / "remote"; _remote(str(base), "bt")
    monkeypatch.setenv("STEEZY_REPO_BASE", str(base))
    root = tmp_path / "tools"
    t = _tool(tmp_path, root)
    assert t.state == registry.NOT_INSTALLED
    seen = []
    r = installer.install_tool(t, refresh=lambda t: (seen.append("refresh"), (True, ""))[1],
                               build=lambda t: (seen.append("build"), (True, ""))[1])
    assert r.status == installer.INSTALLED, r.message
    assert seen == ["refresh", "build"]
    assert (root / "bt" / ".git").is_dir()
    assert _tool(tmp_path, root).state == registry.READY


def test_wrong_os_never_clones(tmp_path):
    monkey = []
    sys_platform = sys.platform
    try:
        sys.platform = "win32"
        t = registry.load_tools(_registry(tmp_path), str(tmp_path / "tools"))[1]
    finally:
        sys.platform = sys_platform
    assert t.state == registry.UNSUPPORTED and "Mac only" in t.message
    r = installer.install_tool(t, clone=lambda t: monkey.append(1) or (True, ""))
    assert r.status == installer.UNSUPPORTED and monkey == []


def test_private_clone_failure_says_ask_stefan(tmp_path):
    t = _tool(tmp_path, tmp_path / "tools", private=True)
    r = installer.install_tool(t, clone=lambda t: (False, "403"))
    assert r.status == installer.INSTALL_FAILED and "Ask Stefan" in r.message


def test_public_clone_failure_says_check_internet(tmp_path):
    t = _tool(tmp_path, tmp_path / "tools")
    r = installer.install_tool(t, clone=lambda t: (False, "could not resolve host"))
    assert r.status == installer.INSTALL_FAILED and "internet" in r.message


def test_package_failure_takes_the_clone_back_out(tmp_path, monkeypatch):
    base = tmp_path / "remote"; _remote(str(base), "bt")
    monkeypatch.setenv("STEEZY_REPO_BASE", str(base))
    root = tmp_path / "tools"
    t = _tool(tmp_path, root)
    r = installer.install_tool(t, refresh=lambda t: (False, "no wheel for torch"), build=ok)
    assert r.status == installer.INSTALL_FAILED and "Press Install" in r.message and "torch" in r.message
    assert not (root / "bt").exists()
    assert _tool(tmp_path, root).state == registry.NOT_INSTALLED


def test_build_failure_takes_the_clone_back_out(tmp_path, monkeypatch):
    base = tmp_path / "remote"; _remote(str(base), "bt")
    monkeypatch.setenv("STEEZY_REPO_BASE", str(base))
    root = tmp_path / "tools"
    r = installer.install_tool(_tool(tmp_path, root), refresh=ok, build=lambda t: (False, "xcodebuild"))
    assert r.status == installer.INSTALL_FAILED and not (root / "bt").exists()


def test_already_installed_is_left_alone(tmp_path):
    root = tmp_path / "tools"; (root / "bt" / ".git").mkdir(parents=True)
    r = installer.install_tool(_tool(tmp_path, root), clone=lambda t: (_ for _ in ()).throw(AssertionError))
    assert r.status == installer.INSTALLED


# ---- the registry fields Windows needs, and the refresh that uses them

def _fake_engine(tmp_path, monkeypatch):
    py = tmp_path / "py"; py.write_text("#!/bin/sh\n"); py.chmod(0o755)
    monkeypatch.setenv("STEEZY_PYTHON", str(py))


def test_windows_refresh_installs_every_listed_file_then_editable(tmp_path, monkeypatch):
    root = tmp_path / "tools"; d = root / "bt"; d.mkdir(parents=True)
    (d / "requirements.txt").write_text(""); (d / "requirements-splitter.txt").write_text("")
    _fake_engine(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "platform", "win32")
    t = _tool(tmp_path, root, windows_requirements=["requirements.txt", "requirements-splitter.txt", "missing.txt"],
              windows_pip_editable=True)
    calls = []
    monkeypatch.setattr(updater, "_run", lambda cmd, cwd, timeout=0, env=None: (calls.append(cmd[3:]), (0, ""))[1])
    assert updater.default_refresh(t)[0]
    tails = [c[-2:] for c in calls]
    assert tails == [["-r", "requirements.txt"], ["-r", "requirements-splitter.txt"], ["-e", "."]]


def test_mac_refresh_installs_every_requirements_file_but_not_editable(tmp_path, monkeypatch):
    root = tmp_path / "tools"; d = root / "bt"; d.mkdir(parents=True)
    (d / "requirements.txt").write_text(""); (d / "requirements-splitter.txt").write_text("")
    _fake_engine(tmp_path, monkeypatch)
    t = _tool(tmp_path, root, windows_requirements=["requirements.txt", "requirements-splitter.txt"],
              windows_pip_editable=True)
    calls = []
    monkeypatch.setattr(updater, "_run", lambda cmd, cwd, timeout=0, env=None: (calls.append(cmd), (0, ""))[1])
    updater.default_refresh(t)
    assert [c[-2:] for c in calls] == [["-r", "requirements.txt"], ["-r", "requirements-splitter.txt"]]


def test_refresh_failure_is_reported(tmp_path, monkeypatch):
    root = tmp_path / "tools"; (root / "bt").mkdir(parents=True); (root / "bt" / "requirements.txt").write_text("")
    _fake_engine(tmp_path, monkeypatch)
    monkeypatch.setattr(updater, "_run", lambda cmd, cwd, timeout=0, env=None: (1, "ERROR: no matching distribution"))
    assert updater.default_refresh(_tool(tmp_path, root)) == (False, "ERROR: no matching distribution")


def test_windows_build_makes_the_start_menu_shortcut(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("STEEZY_SKIP_SHORTCUTS")
    root = tmp_path / "tools"; (root / "bt").mkdir(parents=True)
    (root / "bt" / "icon.ico").write_bytes(b"\0\0\1\0")
    calls = []
    monkeypatch.setattr(updater, "_run", lambda cmd, cwd, timeout=0, env=None: (calls.append((cmd, env)), (0, ""))[1])
    assert updater.default_build(_tool(tmp_path, root)) == (True, "nothing to build on Windows")
    cmd, env = calls[0]
    assert cmd[0] == "powershell" and "CreateShortcut" in cmd[-1] and "IconLocation" in cmd[-1]
    assert env["SZ_NAME"] == "Beat Thief" and env["SZ_TARGET"].endswith("pythonw.exe") and env["SZ_ARGS"] == "gui.py"
    assert env["SZ_ICON"].endswith("icon.ico")


def test_shipped_registry_gives_windows_tools_their_packages():
    tools = {t.id: t for t in registry.load_tools(root="/nonexistent")}
    assert tools["beat_thief"].windows_requirements == ["requirements.txt", "requirements-splitter.txt"]
    assert tools["session_sync"].windows_pip_editable


# ---- the Api the page calls

def _wait(api):
    for _ in range(200):
        s = api.update_status()
        if not s["running"]:
            return s
        time.sleep(0.05)
    raise AssertionError("never finished")


def test_api_install_runs_in_background_and_tile_becomes_ready(tmp_path, monkeypatch):
    base = tmp_path / "remote"; _remote(str(base), "bt")
    monkeypatch.setenv("STEEZY_REPO_BASE", str(base))
    api = gui.Api(_registry(tmp_path), str(tmp_path / "tools"))
    tiles = {t["id"]: t for t in api.list_tools()}
    assert tiles["bt"]["installable"] and tiles["mm"]["installable"]       # both have a Mac version
    api._install_kw = {"refresh": ok, "build": ok}
    assert api.install_tool("bt")["started"]
    s = _wait(api)
    assert s["results"][0]["status"] == installer.INSTALLED and s["installing"] is None
    bt = api.list_tools()[0]
    assert bt["usable"] and not bt["installable"]


def test_api_mac_only_tool_is_not_installable_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    tiles = {t["id"]: t for t in gui.Api(_registry(tmp_path), str(tmp_path / "tools")).list_tools()}
    assert tiles["bt"]["installable"] and not tiles["mm"]["installable"]
    assert tiles["mm"]["state"] == "unsupported"


def test_api_install_waits_for_a_running_update(tmp_path):
    api = gui.Api(_registry(tmp_path), str(tmp_path / "tools"))
    api._running = True
    r = api.install_tool("bt")
    assert not r["started"] and "Wait" in r["message"]


def test_api_install_of_unknown_tool(tmp_path):
    api = gui.Api(_registry(tmp_path), str(tmp_path / "tools"))
    assert not api.install_tool("nope")["started"]


def test_api_install_crash_never_leaves_it_spinning(tmp_path):
    api = gui.Api(_registry(tmp_path), str(tmp_path / "tools"))
    api._install_kw = {"clone": lambda t: 1 / 0}
    api.install_tool("bt")
    s = _wait(api)
    assert s["results"][0]["status"] == installer.INSTALL_FAILED and "Unexpected" in s["results"][0]["message"]


# ---- the shared pin set

def test_refresh_passes_the_engines_constraints_and_syncs_them_from_the_studio_clone(tmp_path, monkeypatch):
    root = tmp_path / "tools"; d = root / "bt"; d.mkdir(parents=True); (d / "requirements.txt").write_text("")
    _fake_engine(tmp_path, monkeypatch)
    eng = tmp_path / "engine"; monkeypatch.setenv("STEEZY_ENGINE_DIR", str(eng))
    studio = tmp_path / "studio"; (studio / ".git").mkdir(parents=True); (studio / "constraints.txt").write_text("numpy==1.26.4\n")
    monkeypatch.setattr(registry, "studio_path", lambda: str(studio))
    calls = []
    monkeypatch.setattr(updater, "_run", lambda cmd, cwd, timeout=0, env=None: (calls.append(cmd), (0, ""))[1])
    assert updater.default_refresh(_tool(tmp_path, root))[0]
    assert ["-c", str(eng / "constraints.txt")] == calls[0][calls[0].index("-c"):calls[0].index("-c") + 2]
    assert (eng / "constraints.txt").read_text() == "numpy==1.26.4\n"
    (studio / "constraints.txt").write_text("numpy==1.26.4\nscipy==1.13.1\n")     # a changed pin reaches the engine
    updater.default_refresh(_tool(tmp_path, root))
    assert "scipy" in (eng / "constraints.txt").read_text()


def test_refresh_without_any_constraints_file_adds_no_flag(tmp_path, monkeypatch):
    root = tmp_path / "tools"; d = root / "bt"; d.mkdir(parents=True); (d / "requirements.txt").write_text("")
    _fake_engine(tmp_path, monkeypatch)
    monkeypatch.setenv("STEEZY_ENGINE_DIR", str(tmp_path / "engine"))
    monkeypatch.setattr(registry, "studio_path", lambda: None)
    calls = []
    monkeypatch.setattr(updater, "_run", lambda cmd, cwd, timeout=0, env=None: (calls.append(cmd), (0, ""))[1])
    assert updater.default_refresh(_tool(tmp_path, root))[0]
    assert "-c" not in calls[0]


def test_packages_are_stale_until_recorded_and_again_when_requirements_change(tmp_path, monkeypatch):
    root = tmp_path / "tools"; d = root / "bt"; d.mkdir(parents=True)
    (d / "requirements.txt").write_text("a\n")
    _fake_engine(tmp_path, monkeypatch)
    t = _tool(tmp_path, root)
    assert updater._packages_stale(t)          # never recorded (installs from before tracking)
    updater._record_packages(t)
    assert not updater._packages_stale(t)
    (d / "requirements.txt").write_text("a\nb\n")
    assert updater._packages_stale(t)          # a requirement was added


def test_phases_are_reported_while_installing(tmp_path, monkeypatch):
    root = tmp_path / "tools"; root.mkdir()
    _fake_engine(tmp_path, monkeypatch)
    seen = []
    monkeypatch.setattr(updater, "phase_hook", seen.append)
    t = _tool(tmp_path, root)
    t.state = registry.NOT_INSTALLED
    def clone(tool):
        os.makedirs(os.path.join(tool.path, ".git")); return True, ""
    installer.install_tool(t, clone=clone, refresh=lambda x: (True, ""), build=lambda x: (True, ""))
    assert seen == ["Downloading", updater.PHASE_PACKAGES, "Building the app"]


def test_apps_go_in_the_main_applications_folder_when_writable(monkeypatch):
    from studio import platform_paths
    monkeypatch.delenv("STEEZY_APPS_DIR", raising=False)
    monkeypatch.setattr(platform_paths.os, "access", lambda p, m: True)
    assert platform_paths.apps_dir() == "/Applications"
    monkeypatch.setattr(platform_paths.os, "access", lambda p, m: False)
    assert platform_paths.apps_dir() == os.path.expanduser("~/Applications")
    monkeypatch.setenv("STEEZY_APPS_DIR", "/x")
    assert platform_paths.apps_dir() == "/x"


def test_build_passes_the_apps_folder_and_removes_the_old_home_copy(tmp_path, monkeypatch):
    home, apps = tmp_path / "home", tmp_path / "apps"
    (home / "Applications" / "BT.app").mkdir(parents=True)
    root = tmp_path / "tools"; (root / "bt").mkdir(parents=True)
    (root / "bt" / "make_app.sh").write_text('#!/bin/bash\nmkdir -p "$1/BT.app"\n')
    os.chmod(root / "bt" / "make_app.sh", 0o755)
    monkeypatch.setenv("HOME", str(home)); monkeypatch.setenv("STEEZY_APPS_DIR", str(apps))
    monkeypatch.setattr(updater.platform_paths, "is_windows", lambda: False)
    t = _tool(tmp_path, str(root))
    assert updater.default_build(t)[0]
    assert (apps / "BT.app").is_dir() and not (home / "Applications" / "BT.app").exists()
