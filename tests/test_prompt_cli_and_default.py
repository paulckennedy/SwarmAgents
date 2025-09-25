import subprocess
import sys
import os

import pytest

from agents.prompts import set_default_promptstore, ps


def test_set_default_promptstore_overrides():
    old = ps
    new = set_default_promptstore(strict=True, validate_schema=False)
    assert new is not None
    assert new is not old


def test_validate_prompts_cli_success():
    # Run the CLI against the repository prompts.json
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # run as a module so imports resolve from repo root
    rc = subprocess.run([sys.executable, "-m", "scripts.validate_prompts"], cwd=repo_root)
    assert rc.returncode == 0
