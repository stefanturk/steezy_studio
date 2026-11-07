"""Every test starts out "on a Mac" with an empty engine folder, whatever machine
runs it. Tests about Windows switch sys.platform themselves. Without this the
Windows CI runner sees Mac-only tools as unsupported, and a Mac with a real
Studio install leaks its own clone (studio_dir) into the tests."""
import sys

import pytest


@pytest.fixture(autouse=True)
def _pretend_mac_with_empty_engine(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("STEEZY_ENGINE_DIR", str(tmp_path / "_engine" / "engine"))
    monkeypatch.delenv("STEEZY_TOOLS_DIR", raising=False)
    monkeypatch.delenv("STEEZY_PYTHON", raising=False)
    monkeypatch.delenv("STEEZY_REPO_BASE", raising=False)
    monkeypatch.setenv("STEEZY_SKIP_SHORTCUTS", "1")
