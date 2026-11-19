"""Run: python3 -m unittest discover -s tests   (from the repo root)"""
import csv, sys, unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tieout import load, roll_forward, run


class HandChecked(unittest.TestCase):
    """Balances re-derived by hand from the terms, independent of the roll-forward code."""

    def setUp(self):
        self.comps = roll_forward(*load(ROOT / "data"))

    def bal(self, lp):
        return sum(self.comps[lp].values())

    def test_lp10_first_close(self):
        c = Decimal(1500000)
        calls = c * Decimal("0.45")                       # 20% + 15% + 10%
        fees = c * Decimal("0.005") * 3                   # 0.5% a quarter
        offset = Decimal(30000) * c / Decimal(50000000)   # Q3, all 12 LPs admitted
        exp = 60000 * c / Decimal(40000000) + (45000 + 40000) * c / Decimal(50000000)
        gain = (Decimal(1200000) - 300000) * c / Decimal(50000000)
        catch_up = Decimal(10000000) * Decimal("0.20")    # LP11 + LP12 catch-up on the Jan 15 call
        interest = catch_up * Decimal("0.08") * 120 / 365 * c / Decimal(40000000)  # Jan 15 to May 15 = 120 days
        expected = calls - fees + offset - exp + gain + interest
        self.assertLessEqual(abs(self.bal("LP10") - expected), Decimal("0.05"))

    def test_lp12_later_close(self):
        c = Decimal(4000000)
        calls = c * Decimal("0.45")
        fees = c * Decimal("0.005") * 3                   # Q1 catch-up + Q2 + Q3
        offset = Decimal(30000) * c / Decimal(50000000)
        exp = (45000 + 40000) * c / Decimal(50000000)     # not admitted for Q1 expenses
        gain = (Decimal(1200000) - 300000) * c / Decimal(50000000)
        expected = calls - fees + offset - exp + gain     # equalization interest paid outside the account
        self.assertLessEqual(abs(self.bal("LP12") - expected), Decimal("0.05"))

    def test_interest_paid_equals_interest_credited(self):
        credited = sum(v for lp in self.comps.values() for k, v in lp.items() if k.startswith("equalization"))
        self.assertLessEqual(abs(credited - Decimal(2000000) * Decimal("0.08") * 120 / 365), Decimal("0.10"))


class AnswerKey(unittest.TestCase):
    def test_every_seeded_break_found_and_named(self):
        _, _, rows = run(ROOT / "data", ROOT / "data" / "prior_admin_statements_2026-09-30.csv", Decimal(1))
        got = {r[0]: r for r in rows}
        with open(ROOT / "data" / "answer_key.csv") as f:
            for k in csv.DictReader(f):
                self.assertEqual(got[k["lp_id"]][4], k["expected_result"], k["lp_id"])
                if k["seeded_cause"]:
                    self.assertTrue(any(k["seeded_cause"] in w for w in got[k["lp_id"]][5]), k["lp_id"])


if __name__ == "__main__":
    unittest.main()
