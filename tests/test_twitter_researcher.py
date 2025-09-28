from agents.twitter_researcher import TwitterResearcher, RateLimitExceeded


def test_twitter_researcher_test_mode_returns_records():
    tr = TwitterResearcher()
    results = tr.search("__TEST__")
    assert isinstance(results, list)
    assert len(results) == 1
    rec = results[0]
    assert rec.get("id") == "12345"
    assert rec.get("url", "").startswith("https://twitter.com/")
    assert rec.get("text") == "This is a test tweet"


def test_twitter_researcher_rate_limit_exception():
    tr = TwitterResearcher()
    # simulate blocked state
    tr._state["blocked_until"] = 9999999999
    try:
        tr.search("anything")
        assert False, "expected RateLimitExceeded"
    except RateLimitExceeded as e:
        assert isinstance(e.retry_after, int)
