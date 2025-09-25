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
    def __init__(self, path: Optional[str] = None, strict: Optional[bool] = None, validate_schema: Optional[bool] = None):
        self.path = path or DEFAULT_PROMPTS_PATH
        # strict mode can be controlled by PROMPTS_STRICT env var or constructor arg
        if strict is None:
            strict = os.environ.get("PROMPTS_STRICT", "0") not in ("0", "", "false", "False")
        self.strict = bool(strict)
        self.env = _make_env(self.strict)
        # schema validation flag controlled by PROMPTS_VALIDATE_SCHEMA env var or constructor arg
        if validate_schema is None:
            validate_schema_env = os.environ.get("PROMPTS_VALIDATE_SCHEMA", "0")
            self.validate_schema = validate_schema_env not in ("0", "", "false", "False")
        else:
            self.validate_schema = bool(validate_schema)
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"prompts": []}
        # keep list for validation and dict for fast lookup
        self._prompt_list = data.get("prompts", [])
        self._prompts = {p.get("id"): p for p in self._prompt_list}
        if self.validate_schema:
            self._validate_prompts()

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

    def _validate_prompts(self) -> None:
        """Run lightweight schema validations on loaded prompts.

        Checks performed:
        - Each prompt's example contains all declared variables.
        - Common variable types are validated (max_results, depth_of_search -> int; persona -> str; filters -> str|dict).
        - Example can be rendered by Jinja2 (non-strict rendering).
        Raises ValueError on validation failures.
        """
        for p in self._prompt_list:
            pid = p.get("id")
            vars_decl = set(p.get("variables", []))
            example = p.get("example", {}) or {}
            missing = vars_decl - set(example.keys())
            if missing:
                raise ValueError(f"Prompt {pid} example missing variables: {missing}")

            # type checks for common fields
            if "persona" in vars_decl:
                val = example.get("persona")
                if val is not None and not isinstance(val, str):
                    raise ValueError(f"Prompt {pid} example persona must be a string")

            for int_field in ("max_results", "depth_of_search"):
                if int_field in vars_decl:
                    v = example.get(int_field)
                    if v is not None and not isinstance(v, int):
                        raise ValueError(f"Prompt {pid} example {int_field} must be an integer")

            if "filters" in vars_decl:
                fval = example.get("filters")
                if fval is not None and not isinstance(fval, (str, dict)):
                    raise ValueError(f"Prompt {pid} example filters must be a string or object")

            # ensure the template renders with the example (non-strict)
            try:
                env = _make_env(strict=False)
                tpl = env.from_string(p.get("prompt_template", ""))
                tpl.render(**example)
            except Exception as e:
                raise ValueError(f"Prompt {pid} example failed to render: {e}")


ps = PromptStore()
