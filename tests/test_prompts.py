import json
import os
import pytest
from jinja2.exceptions import UndefinedError
from agents.prompts import PromptStore, ps


def test_list_prompts():
    ids = ps.list_prompts()
    assert isinstance(ids, list)
    assert "pr-007" in ids


def test_render_pr_007_contains_query():
    s = ps.render("pr-007", {"persona": "YT Expert", "topic_or_person": "climate" , "max_results": 3, "depth_of_search": 1, "filters": ""})
    assert "climate" in s or "climate" in s.lower()


def test_missing_prompt_raises():
    p = PromptStore()
    try:
        p.render("__not_a_prompt__", {})
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_strict_mode_raises_on_missing_variable():
    # strict=True should make Jinja2 raise on undefined variables
    p = PromptStore(strict=True)
    # pr-007 expects variables like topic_or_person; omit it to trigger UndefinedError
    with pytest.raises(UndefinedError):
        p.render("pr-007", {"persona": "YT Expert", "max_results": 3})


def test_env_var_strict_mode_raises_on_missing_variable(monkeypatch):
    # Set environment variable to enable strict mode and ensure PromptStore reads it
    monkeypatch.setenv("PROMPTS_STRICT", "1")
    p = PromptStore()
    with pytest.raises(UndefinedError):
        p.render("pr-007", {"persona": "YT Expert", "max_results": 3})


@pytest.mark.parametrize("val", ["0", "", "false", "False"]) 
def test_env_var_falsy_values_do_not_enable_strict(monkeypatch, val):
    # These values should be treated as falsy and not enable strict mode
    monkeypatch.setenv("PROMPTS_STRICT", val)
    p = PromptStore()
    # Should not raise even though topic_or_person is missing
    out = p.render("pr-007", {"persona": "YT Expert", "max_results": 3})
    assert isinstance(out, str)


def test_env_var_deletion_restores_default(monkeypatch):
    # When PROMPTS_STRICT is set then removed, new PromptStore instances should reflect that
    monkeypatch.setenv("PROMPTS_STRICT", "1")
    p_strict = PromptStore()
    with pytest.raises(UndefinedError):
        p_strict.render("pr-007", {"persona": "YT Expert", "max_results": 3})

    # delete the env var and verify default (non-strict) behavior
    monkeypatch.delenv("PROMPTS_STRICT", raising=False)
    p_default = PromptStore()
    out = p_default.render("pr-007", {"persona": "YT Expert", "max_results": 3})
    assert isinstance(out, str)
