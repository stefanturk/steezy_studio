"""install.sh end to end in a scratch HOME, against local repos (no network)."""
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]


def _repo(path, files):
    os.makedirs(path)
    for name, body in files.items():
        p = os.path.join(path, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(body)
        os.chmod(p, 0o755)
    subprocess.run(["git", "init", "-q", "-b", "main", path], check=True)
    subprocess.run(GIT + ["-C", path, "add", "-A"], check=True)
    subprocess.run(GIT + ["-C", path, "commit", "-qm", "init"], check=True)


@pytest.fixture
def world(tmp_path):
    base = tmp_path / "remote"
    stub = '#!/bin/bash\necho built > "$PWD/.built"\n'
    _repo(str(base / "steezy_studio"), {
        "registry.json": open(os.path.join(ROOT, "registry.json")).read(),
        "engine/setup.sh": "#!/bin/bash\nexit 0\n", "make_app.sh": stub})
    for t in ("beat_thief", "session_sync"):          # ableton_loader / movie_maker deliberately absent
        _repo(str(base / t), {"make_app.sh": stub, "scripts/build_app.sh": stub})
    home = tmp_path / "home"
    home.mkdir()
    env = dict(os.environ, HOME=str(home), STEEZY_REPO_BASE=str(base), STEEZY_SKIP_ENGINE="1",
               STEEZY_NO_GH="1", STEEZY_ENGINE_DIR=str(home / "state" / "engine"),
               STEEZY_TOOLS_DIR=str(home / "tools"), STEEZY_INSTALL_DEST=str(home / "studio"))
    return home, env


def run(env, *args):
    return subprocess.run(["bash", os.path.join(ROOT, "install.sh"), *args], env=env,
                          capture_output=True, text=True, timeout=120)


def test_studio_only(world):
    home, env = world
    r = run(env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (home / "studio" / "registry.json").exists()
    assert not (home / "tools" / "beat_thief").exists()
    assert (home / "state" / "tools_dir").read_text().strip() == str(home / "tools")


def test_named_tools_install_and_private_missing_is_tolerated(world):
    home, env = world
    r = run(env, "beat_thief", "ableton_loader", "session_sync")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (home / "tools" / "beat_thief" / ".built").exists()
    assert (home / "tools" / "session_sync" / ".built").exists()
    assert not (home / "tools" / "ableton_loader").exists()
    assert "Ask Stefan to invite" in r.stdout and "Not installed: ableton_loader" in r.stdout


def test_second_run_updates_instead_of_failing(world):
    home, env = world
    run(env, "beat_thief")
    r = run(env, "beat_thief")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "updating" in r.stdout


def test_unknown_tool_is_reported_not_fatal(world):
    home, env = world
    r = run(env, "nope")
    assert r.returncode == 0 and "Unknown tool 'nope'" in r.stdout


def test_all_keyword(world):
    home, env = world
    r = run(env, "all")
    assert (home / "tools" / "beat_thief").exists() and (home / "tools" / "session_sync").exists()


def test_list():
    r = subprocess.run(["bash", os.path.join(ROOT, "install.sh"), "--list"], capture_output=True, text=True)
    assert "beat_thief" in r.stdout
