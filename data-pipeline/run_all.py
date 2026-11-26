"""Rebuild every data file the API reads.  Usage:  python run_all.py [--refresh] [--skip-probe]

Order matters: admissions rows are matched to the program names that
build_programs.py writes.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_admissions  # noqa: E402
import build_programs  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download sources instead of using cache/")
    ap.add_argument("--skip-probe", action="store_true", help="don't contact OUInfo")
    args = ap.parse_args()

    print("1/2 Program profiles")
    _, stats = build_programs.build(skip_probe=args.skip_probe)
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("2/2 Admissions")
    rows, astats = build_admissions.build(refresh=args.refresh)
    build_admissions.summarize(rows, astats)
    print("Done. Now run the API tests:  cd ../frontend && python -m pytest tests -q")
