"""Score and dedupe a CSV of leads.

    python cli.py examples/leads.csv
    python cli.py examples/leads.csv --min-band warm --out scored.csv
"""
from __future__ import annotations

import argparse
import csv
import sys

from leadscorer import dedupe, parse, score_lead

BAND_ORDER = {"cold": 0, "warm": 1, "hot": 2}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score, dedupe and rank leads.")
    ap.add_argument("csv_path")
    ap.add_argument("--min-band", default="cold", choices=["cold", "warm", "hot"])
    ap.add_argument("--out", help="write results to CSV instead of stdout")
    ap.add_argument("--no-dedupe", action="store_true")
    args = ap.parse_args(argv)

    with open(args.csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    scored = [score_lead(parse(r)) for r in rows]
    removed = 0
    if not args.no_dedupe:
        result = dedupe(scored)
        scored, removed = result.kept, result.removed

    floor = BAND_ORDER[args.min_band]
    scored = [s for s in scored if BAND_ORDER[s.band] >= floor]
    scored.sort(key=lambda s: s.score, reverse=True)

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["score", "band", "email", "company", "title", "why"])
            for s in scored:
                w.writerow([s.score, s.band, s.lead.email or "", s.lead.company or "",
                            s.lead.title or "",
                            "; ".join(f"{n}{v:+d}" for n, v in s.reasons)])
        print(f"{len(scored)} leads -> {args.out}  ({removed} duplicates merged)")
        return 0

    print(f"{len(rows)} in, {removed} duplicates merged, "
          f"{len(scored)} at {args.min_band}+\n")
    for s in scored:
        print(f"  {s.lead.email or s.lead.company:<34} {s.explain()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
