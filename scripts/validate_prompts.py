"""Validate prompts.json files using PromptStore's validation logic.

Usage:
  python scripts/validate_prompts.py [--path PATH] [--strict] [--validate]

Exit code 0 on success, non-zero on validation error.
"""
import argparse
import sys

from agents.prompts import PromptStore


def validate_prompts(path: str = None, strict: bool = False, validate: bool = True) -> None:
    ps = PromptStore(path=path, strict=strict, validate_schema=validate)
    # If construction succeeded, validation passed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a prompts.json file")
    parser.add_argument("--path", help="Path to prompts.json (default: prompts.json in project root)")
    parser.add_argument("--strict", action="store_true", help="Use strict Jinja rendering for validation")
    parser.add_argument("--no-validate", dest="validate", action="store_false", help="Don't run schema validation")
    args = parser.parse_args(argv)
    try:
        validate_prompts(path=args.path, strict=args.strict, validate=args.validate)
    except Exception as e:
        print(f"Validation failed: {e}", file=sys.stderr)
        sys.exit(2)
    print("Validation succeeded")


if __name__ == "__main__":
    main()
