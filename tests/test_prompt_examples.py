import json
import os

from agents.prompts import PromptStore


def load_prompts(path=None):
    path = path or os.path.join(os.path.dirname(__file__), "..", "prompts.json")
    path = os.path.abspath(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_prompt_examples_contain_declared_variables():
    data = load_prompts(os.path.join(os.path.dirname(__file__), "..", "prompts.json"))
    prompts = data.get("prompts", [])
    for p in prompts:
        vars_decl = set(p.get("variables", []))
        example = p.get("example", {})
        missing = vars_decl - set(example.keys())
        assert not missing, f"Prompt {p.get('id')} example missing variables: {missing}"


def test_prompt_examples_render_with_promptstore():
    # Non-strict rendering should succeed for examples
    ps = PromptStore()
    data = load_prompts(os.path.join(os.path.dirname(__file__), "..", "prompts.json"))
    for p in data.get("prompts", []):
        pid = p.get("id")
        example = p.get("example", {})
        # Ensure render doesn't raise
        out = ps.render(pid, example)
        assert isinstance(out, str)
