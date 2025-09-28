#!/usr/bin/env python3
"""Render a prompt by id using the project's prompts.json.

Usage: python scripts/render_prompt.py <prompt_id> [variables.json]
"""
import json
import sys

from agents import ps


def main(argv):
    if len(argv) < 2:
        print("Usage: render_prompt.py <prompt_id> [variables.json]")
        return 2
    pid = argv[1]
    vars = {}
    if len(argv) >= 3:
        with open(argv[2], "r", encoding="utf-8") as f:
            vars = json.load(f)
    try:
        out = ps.render(pid, vars)
        print(out)
        return 0
    except KeyError as e:
        print(str(e))
        return 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
