"""PromptStore helper for loading and rendering prompts from prompts.json

Provides a tiny API to get prompt templates by id and render them with a
variables dict. The prompts.json resides at the project root next to README
and other project files.
"""

import json
import os
from typing import Any, Dict, Optional, List

from jinja2 import Environment, StrictUndefined, Undefined

DEFAULT_PROMPTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "prompts.json"
)


def _make_env(strict: bool = False) -> Environment:
    if strict:
        return Environment(undefined=StrictUndefined, keep_trailing_newline=True)
    return Environment(undefined=Undefined, keep_trailing_newline=True)


class PromptStore:
    def __init__(
        self,
        path: Optional[str] = None,
        strict: Optional[bool] = None,
        validate_schema: Optional[bool] = None,
    ):
        self.path = path or DEFAULT_PROMPTS_PATH
        # strict mode can be controlled by PROMPTS_STRICT env var or constructor arg
        if strict is None:
            strict = os.environ.get("PROMPTS_STRICT", "0") not in (
                "0",
                "",
                "false",
                "False",
            )
        self.strict = bool(strict)
        self.env = _make_env(self.strict)
        # schema validation flag controlled by PROMPTS_VALIDATE_SCHEMA env var or constructor arg
        if validate_schema is None:
            validate_schema_env = os.environ.get("PROMPTS_VALIDATE_SCHEMA", "0")
            self.validate_schema = validate_schema_env not in (
                "0",
                "",
                "false",
                "False",
            )
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

    def list_prompts(self) -> List[str]:
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
        # template.render may be Any; coerce to str for the typed API
        return str(template.render(**(variables or {})))

    def _validate_prompts(self) -> None:
        """Run lightweight schema validations on loaded prompts.

        Checks performed:
        - Each prompt's example contains all declared variables.
                - Common variable types are validated (max_results, depth_of_search -> int;
                    persona -> str; filters -> str|dict).
        - Example can be rendered by Jinja2 (non-strict rendering).
        Raises ValueError on validation failures.
        """
        for p in self._prompt_list:
            pid = p.get("id")
            # basic id/type checks
            if not pid or not isinstance(pid, str):
                raise ValueError(f"Prompt has invalid or missing id: {pid}")

            # prompt_template must be present and a string
            tpl_val = p.get("prompt_template")
            if not tpl_val or not isinstance(tpl_val, str):
                raise ValueError(f"Prompt {pid} missing or invalid prompt_template")
            vars_decl = p.get("variables", [])
            if not isinstance(vars_decl, list) or not all(
                isinstance(x, str) for x in vars_decl
            ):
                raise ValueError(f"Prompt {pid} variables must be a list of strings")
            vars_decl = set(vars_decl)
            example = p.get("example", {}) or {}
            missing = vars_decl - set(example.keys())
            if missing:
                raise ValueError(f"Prompt {pid} example missing variables: {missing}")

            # tags if present must be list of strings
            tags = p.get("tags", [])
            if tags is not None and (
                not isinstance(tags, list) or not all(isinstance(t, str) for t in tags)
            ):
                raise ValueError(f"Prompt {pid} tags must be a list of strings")

            # type checks for common fields
            if "persona" in vars_decl:
                val = example.get("persona")
                if val is not None and not isinstance(val, str):
                    raise ValueError(f"Prompt {pid} example persona must be a string")

            for int_field in ("max_results", "depth_of_search"):
                if int_field in vars_decl:
                    v = example.get(int_field)
                    if v is not None and not isinstance(v, int):
                        raise ValueError(
                            f"Prompt {pid} example {int_field} must be an integer"
                        )

            if "filters" in vars_decl:
                fval = example.get("filters")
                if fval is not None and not isinstance(fval, (str, dict)):
                    raise ValueError(
                        f"Prompt {pid} example filters must be a string or object"
                    )

            # ensure the template renders with the example (non-strict)
            try:
                env = _make_env(strict=False)
                tpl = env.from_string(p.get("prompt_template", ""))
                tpl.render(**example)
            except Exception as e:
                raise ValueError(f"Prompt {pid} example failed to render: {e}")


def set_default_promptstore(
    path: Optional[str] = None,
    strict: Optional[bool] = None,
    validate_schema: Optional[bool] = None,
) -> "PromptStore":
    """Set and return the module-level default PromptStore instance.

    Call this to programmatically override the default `ps` used by modules.
    """
    global ps
    ps = PromptStore(path=path, strict=strict, validate_schema=validate_schema)
    return ps


# create module-level default using environment variables unless overridden programmatically
ps = set_default_promptstore()
