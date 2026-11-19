"""Capital account tie-out checker.

Rolls every LP's capital account forward from the fund terms, the LP register, and
the fund's events, compares each balance with the statement the prior administrator
issued, and flags any account off by more than the tolerance ($1 by default) with
the component that most likely explains the gap.

All data in data/ is SYNTHETIC. Usage:
    python3 tieout.py                      # uses data/ and writes report.md
    python3 tieout.py --statements other.csv --tolerance 1
"""
import argparse, csv, json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
CENT = Decimal("0.01")


def d(x):
    return Decimal(str(x))


def day(s):
    return date.fromisoformat(s)


def money(x):
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def load(data_dir):
    terms = json.loads((data_dir / "fund_terms.json").read_text())
    lps = []
    with open(data_dir / "lp_register.csv") as f:
        for r in csv.DictReader(f):
            lps.append({"id": r["lp_id"], "commitment": d(r["commitment"]), "close": day(r["close_date"])})
    with open(data_dir / "fund_events.csv") as f:
        events = list(csv.DictReader(f))
    return terms, lps, events


def admitted(lps, on):
    return [lp for lp in lps if lp["close"] <= on]


def share(lp, group):
    return lp["commitment"] / sum(x["commitment"] for x in group)


def roll_forward(terms, lps, events):
    """Return {lp_id: {component: signed amount}}; the balance is the sum of the components."""
    comp = {lp["id"]: {} for lp in lps}

    def add(lp_id, key, amt):
        comp[lp_id][key] = comp[lp_id].get(key, Decimal(0)) + amt

    fee_q = d(terms["management_fee_annual_rate"]) / 4
    eq_rate = d(terms["equalization_interest_annual_rate"])
    offset_pct = d(terms["fee_offset_pct"])
    calls = []  # (date, pct) of calls already made
    fee_quarters = []  # quarter ends whose fee has been charged

    for e in events:
        when, kind, q = day(e["date"]), e["event"], e["quarter_end"]
        if kind == "capital_call":
            pct = d(e["value"])
            for lp in admitted(lps, when):
                add(lp["id"], f"call {e['date']}", lp["commitment"] * pct)
            calls.append((when, pct))
        elif kind == "management_fee":
            for lp in admitted(lps, day(q)):
                add(lp["id"], f"management fee {q}", -lp["commitment"] * fee_q)
            fee_quarters.append(q)
        elif kind == "fee_offset":
            group = admitted(lps, day(q))
            for lp in group:
                add(lp["id"], f"fee offset {q}", d(e["value"]) * offset_pct * share(lp, group))
        elif kind in ("fund_expenses", "unrealized_gain"):
            group = admitted(lps, day(q))
            sign = -1 if kind == "fund_expenses" else 1
            label = "expenses" if kind == "fund_expenses" else "unrealized gain/loss"
            for lp in group:
                add(lp["id"], f"{label} {q}", sign * d(e["value"]) * share(lp, group))
        elif kind == "later_close":
            new = [lp for lp in lps if lp["close"] == when]
            earlier = [lp for lp in lps if lp["close"] < when]
            interest_total = Decimal(0)
            for lp in new:
                for call_date, pct in calls:
                    catch_up = lp["commitment"] * pct
                    add(lp["id"], f"catch-up call {call_date.isoformat()}", catch_up)
                    # Equalization interest is paid on top of the commitment, so it never enters the payer's account.
                    interest_total += catch_up * eq_rate * (when - call_date).days / 365
                for fq in fee_quarters:
                    add(lp["id"], f"catch-up management fee {fq}", -lp["commitment"] * fee_q)
            for lp in earlier:
                add(lp["id"], f"equalization interest {e['date']}", interest_total * share(lp, earlier))
    return {k: {c: money(v) for c, v in comps.items()} for k, comps in comp.items()}


def diagnose(diff, components, tol):
    """Name the components whose omission or double count explains the difference."""
    hits = []
    for name, amt in components.items():
        if amt == 0:
            continue
        if abs(diff + amt) <= tol:
            hits.append(f"{name} missing from the statement ({money(amt):+,.2f})")
        elif abs(diff - amt) <= tol:
            hits.append(f"{name} counted twice ({money(amt):+,.2f})")
    return hits or ["no single component explains it; review the account by hand"]


def run(data_dir, statements_path, tol):
    terms, lps, events = load(data_dir)
    comps = roll_forward(terms, lps, events)
    stmt = {}
    with open(statements_path) as f:
        for r in csv.DictReader(f):
            stmt[r["lp_id"]] = d(r["ending_capital"])
    rows = []
    for lp in lps:
        expected = sum(comps[lp["id"]].values())
        actual = stmt.get(lp["id"])
        if actual is None:
            rows.append((lp["id"], expected, None, None, "BREAK", ["LP missing from the statement file"]))
            continue
        diff = actual - expected
        if abs(diff) <= tol:
            rows.append((lp["id"], expected, actual, diff, "TIES", []))
        else:
            rows.append((lp["id"], expected, actual, diff, "BREAK", diagnose(diff, comps[lp["id"]], tol)))
    return terms, comps, rows


def report(terms, rows, tol, statements_name):
    breaks = [r for r in rows if r[4] == "BREAK"]
    out = [f"# Capital account tie-out: {terms['fund']}", "",
           f"Statements checked: `{statements_name}`. Tolerance: ${tol}. "
           f"{len(rows) - len(breaks)} of {len(rows)} accounts tie; {len(breaks)} break.", "",
           "| LP | Rolled forward | Statement | Difference | Result | Likely cause |",
           "|---|---:|---:|---:|---|---|"]
    for lp, exp, act, diff, res, why in rows:
        a = "" if act is None else f"{act:,.2f}"
        df = "" if diff is None else f"{diff:+,.2f}"
        out.append(f"| {lp} | {exp:,.2f} | {a} | {df} | {res} | {'; '.join(why)} |")
    out += ["", "All data is synthetic. Nothing here comes from a real fund or administrator."]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--statements", default=str(HERE / "data" / "prior_admin_statements_2026-09-30.csv"))
    ap.add_argument("--tolerance", default="1")
    ap.add_argument("--out", default=str(HERE / "report.md"))
    a = ap.parse_args()
    tol = d(a.tolerance)
    terms, _, rows = run(Path(a.data), a.statements, tol)
    text = report(terms, rows, tol, Path(a.statements).name)
    Path(a.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
