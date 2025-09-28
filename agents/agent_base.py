"""Small agent base helper that centralizes prompt rendering for agents.

Agents can subclass AgentBase to call `self.render_prompt(prompt_id, variables)`
which uses the central `prompts.json` store. This keeps prompt usage uniform
across agents.
"""

from typing import Any, Dict, Optional

# module-level placeholder for the prompt store; real value imported below when available
ps: Any = None
try:
    from .prompts import ps
except Exception:
    ps = None


class AgentBase:
    def render_prompt(
        self, prompt_id: str, variables: Optional[Dict[str, Any]] = None
    ) -> str:
        vars = variables or {}
        if ps is None:
            # fallback to a simple join
            return f"[PROMPT {prompt_id}] " + str(vars)
        # ensure we return a str to satisfy type checkers
        return str(ps.render(prompt_id, vars))
