import json
import os

import pytest

from agents.prompts import PromptStore


def test_validate_prompts_env_var_passes(monkeypatch):
    # Enable schema validation via env var
    monkeypatch.setenv("PROMPTS_VALIDATE_SCHEMA", "1")
    # Should not raise when loading the real prompts.json
    ps = PromptStore()
    # Basic smoke: list prompts
    ids = ps.list_prompts()
    assert isinstance(ids, list)


def test_validate_prompts_fails_for_bad_example(tmp_path, monkeypatch):
    # Create a bad prompts file where example is missing declared variables
    bad = {
        "schema_version": "1.0",
        "prompts": [
            {
                "id": "bad-001",
                "prompt_template": "Hi {{name}}",
                "variables": ["name", "age"],
                "example": {"name": "Alice"}
            }
        ]
    }
    pfile = tmp_path / "bad_prompts.json"
    pfile.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setenv("PROMPTS_VALIDATE_SCHEMA", "1")
    # Constructing PromptStore with path should raise ValueError due to missing example var
    with pytest.raises(ValueError):
        PromptStore(path=str(pfile))


def test_constructor_flag_overrides_env_var(monkeypatch, tmp_path):
    # Case A: env var true, constructor False -> validation disabled
    monkeypatch.setenv("PROMPTS_VALIDATE_SCHEMA", "1")
    ps = PromptStore(validate_schema=False)
    assert ps.validate_schema is False

    # Case B: env var false, constructor True -> validation enabled
    monkeypatch.setenv("PROMPTS_VALIDATE_SCHEMA", "0")
    ps2 = PromptStore(validate_schema=True)
    assert ps2.validate_schema is True
