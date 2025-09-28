"""scripts package initializer so the validate_prompts module can be run with
`python -m scripts.validate_prompts`.

Expose the main validator symbol so linters and importers can reference it.
"""

from .validate_prompts import validate_prompts

__all__ = ["validate_prompts"]
