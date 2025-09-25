"""Small agent base helper that centralizes prompt rendering for agents.

Agents can subclass AgentBase to call `self.render_prompt(prompt_id, variables)`
which uses the central `prompts.json` store. This keeps prompt usage uniform
across agents.
"""
from typing import Dict, Any, Optional
try:
    from .prompts import ps
except Exception:
    ps = None


class AgentBase:
    def render_prompt(self, prompt_id: str, variables: Optional[Dict[str, Any]] = None) -> str:
        vars = variables or {}
        if ps is None:
            # fallback to a simple join
            return f"[PROMPT {prompt_id}] " + str(vars)
        return ps.render(prompt_id, vars)
