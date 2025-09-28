"""Validate prompts.json files using PromptStore's validation logic.

Usage:
  python -m scripts.validate_prompts [--paths PATH [PATH ...]] [--strict] [--no-validate] [--autofix] [--report-json FILE]

Exit code 0 on success, non-zero on validation error.
"""
import argparse
import json
import sys
from typing import List
from pathlib import Path

from agents.prompts import PromptStore


def _autofix_file(path: Path) -> bool:
    """Attempt simple autofixes on a prompts.json file.

    Returns True if file was modified.
    Current fixes:
    - Coerce numeric strings for example fields 'max_results' and 'depth_of_search' into integers when safe.
    - If 'filters' in example is a JSON object encoded as a string, parse it.
    """
    changed = False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False

    prompts = data.get("prompts", [])
    for p in prompts:
        example = p.get("example")
        if not isinstance(example, dict):
            continue
        for int_field in ("max_results", "depth_of_search"):
            if int_field in example:
                v = example[int_field]
                if isinstance(v, str) and v.isdigit():
                    example[int_field] = int(v)
                    changed = True
        if "filters" in example:
            fv = example["filters"]
            if isinstance(fv, str):
                s = fv.strip()
                if s.startswith("{") and s.endswith("}"):
                    try:
                        example["filters"] = json.loads(s)
                        changed = True
                    except Exception:
                        pass

    if changed:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changed


def validate_prompts(paths: List[str], strict: bool = False, validate: bool = True, autofix: bool = False):
    results = []
    for p in paths:
        path = Path(p) if p else Path("prompts.json")
        if not path.exists():
            results.append({"path": str(path), "ok": False, "error": "file not found"})
            continue

        if autofix:
            try:
                _autofix_file(path)
            except Exception as e:
                results.append({"path": str(path), "ok": False, "error": f"autofix failed: {e}"})
                continue

        try:
            PromptStore(path=str(path), strict=strict, validate_schema=validate)
            results.append({"path": str(path), "ok": True})
        except Exception as e:
            results.append({"path": str(path), "ok": False, "error": str(e)})

    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate prompts.json files")
    parser.add_argument("--paths", nargs="*", help="Paths to prompts.json files (defaults to prompts.json in repo root)")
    parser.add_argument("--strict", action="store_true", help="Use strict Jinja rendering for validation")
    parser.add_argument("--no-validate", dest="validate", action="store_false", help="Don't run schema validation")
    parser.add_argument("--autofix", action="store_true", help="Attempt safe autofixes before validation")
    parser.add_argument("--report-json", help="Write a JSON report of validation results to this file")
    args = parser.parse_args(argv)

    paths = args.paths or ["prompts.json"]
    results = validate_prompts(paths=paths, strict=args.strict, validate=args.validate, autofix=args.autofix)

    if args.report_json:
        try:
            Path(args.report_json).write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Failed to write report: {e}", file=sys.stderr)

    # non-zero exit if any failed
    failed = [r for r in results if not r.get("ok")]
    if failed:
        for f in failed:
            print(f"Validation failed for {f.get('path')}: {f.get('error')}", file=sys.stderr)
        sys.exit(2)

    print("Validation succeeded for all files")


if __name__ == "__main__":
    main()
