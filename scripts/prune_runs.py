#!/usr/bin/env python3
"""Prune old run snapshot files under runs/.

Usage:
  python scripts/prune_runs.py --days 30 [--dry-run]

Deletes snapshot files matching job_<id>_YYYYMMDDTHHMMSSZ.json older than N days.
"""
from __future__ import annotations

import argparse
import glob
import os
from datetime import datetime, timedelta, timezone

RUNS_DIR = os.path.join(os.getcwd(), "runs", "jobs")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--days",
        type=int,
        default=30,
        help="Remove snapshots older than this many days",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show files that would be removed but don't delete",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    pattern = os.path.join(RUNS_DIR, "job_*_*.json")
    removed = 0
    for path in glob.glob(pattern):
        try:
            # filename contains timestamp like ..._YYYYMMDDTHHMMSSZ.json
            base = os.path.basename(path)
            parts = base.rsplit("_", 2)
            if len(parts) < 2:
                continue
            ts_part = parts[-1].rsplit(".", 1)[0]
            # parse YYYYMMDDTHHMMSSZ
            dt = datetime.strptime(ts_part, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
            if dt < cutoff:
                if args.dry_run:
                    print("Would remove:", path)
                else:
                    os.remove(path)
                    print("Removed:", path)
                    removed += 1
        except Exception as e:
            print("Skipped", path, "due to", e)
    print(f"Done. Removed {removed} files.")


if __name__ == "__main__":
    main()
