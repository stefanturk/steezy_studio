"""Updates run code on every friend's computer, unasked, at launch. So before pulling, the Studio checks that
the new commit is signed by a key in allowed_signers (Stefan's), read from the copy of the Studio that is
already running (so a pushed change to that list must itself be signed). An unsigned or stranger-signed
commit is left on GitHub and reported; the tool keeps the version it has."""
import os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from studio import registry, updater as U

pytestmark = pytest.mark.skipif(not shutil.which("ssh-keygen"), reason="needs ssh-keygen")


def git(path, *a, key=None):
    sign = ["-c", "gpg.format=ssh", "-c", "user.signingkey=%s" % key, "-c", "commit.gpgsign=true"] if key \
        else ["-c", "commit.gpgsign=false"]
    return subprocess.run(["git", "-C", path, "-c", "user.email=t@t", "-c", "user.name=t", *sign, *a],
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.delenv("STEEZY_SKIP_SIGNATURE_CHECK", raising=False)
    keys = {}
    for who in ("stefan", "stranger"):
        k = tmp_path / who
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-q", "-f", str(k)], check=True)
        keys[who] = str(k)
    signers = tmp_path / "allowed_signers"
    signers.write_text('stefan namespaces="git" %s\n' % " ".join(open(keys["stefan"] + ".pub").read().split()[:2]))
    monkeypatch.setattr(U, "signers_file", lambda: str(signers))
    bare = tmp_path / "t.git"; subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    seed = tmp_path / "seed"; subprocess.run(["git", "clone", "-q", str(bare), str(seed)], check=True, capture_output=True)
    (seed / "f").write_text("1"); git(str(seed), "add", "."); git(str(seed), "commit", "-q", "-m", "one")
    git(str(seed), "push", "-q", "origin", "HEAD:main")
    folder = tmp_path / "tools" / "t"
    subprocess.run(["git", "clone", "-q", str(bare), str(folder)], check=True, capture_output=True)
    tool = registry.Tool(id="t", name="T", repo=str(bare), folder="t", path=str(folder), build=["x"], app="x.app",
                         platforms=["mac"])
    builds = []

    def push(key=None):
        git(str(seed), "commit", "-q", "--allow-empty", "-m", "new", key=key); git(str(seed), "push", "-q", "origin", "HEAD:main")

    def update():
        return U.update_tool(tool, refresh=lambda t: (True, ""), build=lambda t: (builds.append(1), (True, ""))[1])
    return keys, push, update, tool, builds


def head(tool):
    return git(tool.path, "rev-parse", "HEAD")


def test_an_update_signed_by_stefan_is_installed(world):
    keys, push, update, tool, builds = world
    push(keys["stefan"])
    r = update()
    assert r.status == U.UPDATED, r.message
    assert builds == [1]


def test_an_unsigned_update_is_left_on_github(world):
    keys, push, update, tool, builds = world
    before = head(tool); push()
    r = update()
    assert r.status == U.UNSIGNED and "signed" in r.message
    assert head(tool) == before and builds == []


def test_an_update_signed_by_someone_else_is_left_on_github(world):
    keys, push, update, tool, builds = world
    before = head(tool); push(keys["stranger"])
    r = update()
    assert r.status == U.UNSIGNED
    assert head(tool) == before and builds == []


def test_only_the_newest_commit_needs_the_signature(world):
    # It vouches for everything under it; older unsigned history (from before signing) is fine.
    keys, push, update, tool, builds = world
    push(); push(keys["stefan"])
    assert update().status == U.UPDATED


def test_without_a_trusted_list_nothing_is_pulled(world, monkeypatch):
    keys, push, update, tool, builds = world
    monkeypatch.setattr(U, "signers_file", lambda: None)
    before = head(tool); push(keys["stefan"])
    assert update().status == U.UNSIGNED and head(tool) == before


def test_the_shipped_list_holds_one_ssh_key_for_git():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lines = [l for l in open(os.path.join(here, "allowed_signers")).read().splitlines() if l.strip() and not l.startswith("#")]
    assert lines and all('namespaces="git" ssh-' in l for l in lines)
    assert "allowed_signers" in open(os.path.join(here, "make_app.sh")).read()     # it goes into the app


def test_the_running_copy_s_list_is_the_one_used():
    p = U.signers_file()
    assert p and os.path.isfile(p)
    assert os.path.dirname(os.path.abspath(p)) == os.path.dirname(os.path.dirname(os.path.abspath(U.__file__)))
