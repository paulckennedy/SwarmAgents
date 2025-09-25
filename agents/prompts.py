"""PromptStore helper for loading and rendering prompts from prompts.json

Provides a tiny API to get prompt templates by id and render them with a
variables dict. The prompts.json resides at the project root next to README
and other project files.
"""
from typing import Any, Dict, Optional
import json
import os

from jinja2 import Environment, StrictUndefined, Undefined


DEFAULT_PROMPTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts.json")


def _make_env(strict: bool = False):
    if strict:
        return Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    return Environment(undefined=Undefined, keep_trailing_newline=True)


class PromptStore:
    def __init__(self, path: Optional[str] = None, strict: Optional[bool] = None):
        self.path = path or DEFAULT_PROMPTS_PATH
        # strict mode can be controlled by PROMPTS_STRICT env var or constructor arg
        if strict is None:
            strict = os.environ.get("PROMPTS_STRICT", "0") not in ("0", "", "false", "False")
        self.strict = bool(strict)
        self.env = _make_env(self.strict)
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"prompts": []}
        self._prompts = {p.get("id"): p for p in data.get("prompts", [])}

    def list_prompts(self):
        return list(self._prompts.keys())

    def get(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        return self._prompts.get(prompt_id)

    def render(self, prompt_id: str, variables: Dict[str, Any]) -> str:
        p = self.get(prompt_id)
        if not p:
            raise KeyError(f"prompt {prompt_id} not found")
        tpl = p.get("prompt_template", "")
        template = self.env.from_string(tpl)
        # Jinja will raise in strict mode if variables are missing
        return template.render(**(variables or {}))


ps = PromptStore()
