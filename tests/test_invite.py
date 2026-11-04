from types import SimpleNamespace

from studio import invite, registry


def tools():
    return registry.load_tools(root="/nonexistent")


def test_gh_args_for_owner_repo_and_user():
    a = invite.gh_args("https://github.com/stefanturk/movie_maker.git", "some-friend")
    assert a == ["gh", "api", "-X", "PUT", "repos/stefanturk/movie_maker/collaborators/some-friend",
                 "-f", "permission=pull"]


def test_bad_usernames_rejected():
    for bad in ("", "a b", "x/../y", "-lead", "trail-", "a;rm", "a" * 40):
        assert invite.gh_args("https://github.com/o/r.git", bad) is None


def test_dry_run_covers_only_private_tools_and_calls_nothing():
    def boom(_):
        raise AssertionError("must not run")
    res = invite.invite("friend", tools=tools(), runner=boom)
    assert sorted(r["id"] for r in res) == ["ableton_loader", "movie_maker"]
    assert all(r["ok"] and not r["sent"] for r in res)


def test_send_uses_runner_and_reports_failure():
    calls = []
    def runner(a):
        calls.append(a)
        return SimpleNamespace(returncode=1 if "ableton_loader" in a[4] else 0, stderr="Not Found")
    res = {r["id"]: r for r in invite.invite("friend", ["ableton_loader", "movie_maker"], send=True,
                                              tools=tools(), runner=runner)}
    assert len(calls) == 2
    assert res["movie_maker"]["sent"] and not res["ableton_loader"]["ok"]
    assert res["ableton_loader"]["message"] == "Not Found"


def test_filter_by_tool_id():
    res = invite.invite("friend", ["movie_maker"], tools=tools())
    assert [r["id"] for r in res] == ["movie_maker"]
