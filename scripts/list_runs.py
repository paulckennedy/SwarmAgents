#!/usr/bin/env python3
"""List and summarize saved run files under runs/.

Usage:
  python scripts/list_runs.py [--pattern job_* | last_job_* ]
"""
from __future__ import annotations
import os
import json
import glob
import argparse
from datetime import datetime

RUNS_DIR = os.path.join(os.getcwd(), "runs")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pattern", default="job_*", help="Glob pattern to list (default: job_*)")
    return p.parse_args()


def main():
    args = parse_args()
    pattern = os.path.join(RUNS_DIR, args.pattern + "*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        print("No run files found for pattern:", args.pattern)
        return
    for pth in files:
        try:
            with open(pth, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            rid = data.get('id')
            resp = data.get('response')
            count = len(resp) if isinstance(resp, list) else (1 if resp else 0)
            mtime = datetime.fromtimestamp(os.path.getmtime(pth)).isoformat()
            print(f"{os.path.basename(pth)} - id={rid} items={count} mtime={mtime}")
        except Exception as e:
            print("Failed to read", pth, e)


if __name__ == '__main__':
    main()
