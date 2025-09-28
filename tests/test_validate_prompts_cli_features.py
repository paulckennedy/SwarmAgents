import json
import os
import subprocess
import sys


def run_cli(args, cwd=None):
    repo_root = cwd or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return subprocess.run(
        [sys.executable, "-m", "scripts.validate_prompts"] + args, cwd=repo_root
    )


def test_autofix_coerces_numeric_strings(tmp_path):
    # Create a temporary prompts file with numeric strings
    p = tmp_path / "prompts.json"
    bad = {
        "schema_version": "1.0",
        "prompts": [
            {
                "id": "p1",
                "prompt_template": "Test {{topic}}",
                "variables": ["topic", "max_results"],
                "example": {"topic": "x", "max_results": "5"},
            }
        ],
    }
    p.write_text(json.dumps(bad), encoding="utf-8")
    # run autofix
    rc = run_cli(["--paths", str(p), "--autofix"])
    assert rc.returncode == 0
    # file should be updated with integer value
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["prompts"][0]["example"]["max_results"] == 5


def test_report_json_written(tmp_path):
    p = tmp_path / "prompts.json"
    good = {
        "schema_version": "1.0",
        "prompts": [
            {
                "id": "p2",
                "prompt_template": "Hi {{name}}",
                "variables": ["name"],
                "example": {"name": "Alice"},
            }
        ],
    }
    p.write_text(json.dumps(good), encoding="utf-8")
    report = tmp_path / "report.json"
    rc = run_cli(["--paths", str(p), "--report-json", str(report)])
    assert rc.returncode == 0
    assert report.exists()
    r = json.loads(report.read_text(encoding="utf-8"))
    assert isinstance(r, list)
