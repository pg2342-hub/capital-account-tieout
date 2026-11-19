"""Writes the SYNTHETIC prior-administrator statements used in the demo, with known breaks seeded in.

The seeded breaks and the one sub-dollar rounding difference are listed in data/answer_key.csv,
so the checker's output can be graded. Rerun after changing data/ to regenerate.
"""
import csv
from decimal import Decimal
from pathlib import Path
from tieout import load, roll_forward

HERE = Path(__file__).resolve().parent
SEEDS = [  # lp, component left off the statement (None = rounding only), extra amount, what it represents
    ("LP01", None, Decimal("0.40"), "rounding difference under $1, should tie"),
    ("LP03", "fee offset 2026-09-30", 0, "Q3 board-fee offset not applied to this LP's management fee"),
    ("LP05", "equalization interest 2026-05-15", 0, "equalization interest from the later close never credited"),
    ("LP08", "call 2026-07-15", 0, "Q3 capital call wire received but not posted"),
    ("LP11", "catch-up management fee 2026-03-31", 0, "later-close LP not charged the Q1 catch-up fee"),
    ("LP12", "unrealized gain/loss 2026-06-30", 0, "Q2 write-up not allocated to a later-close LP"),
]

terms, lps, events = load(HERE / "data")
comps = roll_forward(terms, lps, events)
seeds = {s[0]: s for s in SEEDS}
with open(HERE / "data" / "prior_admin_statements_2026-09-30.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["lp_id", "ending_capital"])
    for lp in lps:
        bal = sum(comps[lp["id"]].values())
        if lp["id"] in seeds:
            _, key, extra, _ = seeds[lp["id"]]
            if key:
                bal -= comps[lp["id"]][key]
            bal += extra
        w.writerow([lp["id"], f"{bal:.2f}"])
with open(HERE / "data" / "answer_key.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["lp_id", "expected_result", "seeded_cause", "description"])
    for lp in lps:
        s = seeds.get(lp["id"])
        if s and s[1]:
            w.writerow([lp["id"], "BREAK", s[1], s[3]])
        elif s:
            w.writerow([lp["id"], "TIES", "", s[3]])
        else:
            w.writerow([lp["id"], "TIES", "", "clean"])
print("wrote data/prior_admin_statements_2026-09-30.csv and data/answer_key.csv")
