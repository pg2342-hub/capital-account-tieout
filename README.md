# capital-account-tieout

**Demo page (sample output and eval results, no install):** https://pg2342-hub.github.io/capital-account-tieout/

A small checker for the first gate of a fund administrator switch: before the new books run live, every LP's capital account has to tie to the statement the prior administrator issued.

It rolls each LP's capital account forward from the fund terms, the LP register, and the fund's events (capital calls, management fees, fee offsets, expenses, unrealized gains and losses, and a later close with catch-up calls, catch-up fees, and equalization interest). It then compares each balance with the prior administrator's statement and flags every account off by more than $1, naming the component whose omission or double count explains the gap.

**All data is synthetic.** `data/` describes a made-up $50M venture fund with 12 LPs, ten admitted at a January 2026 first close and two at a May 2026 later close. It is not based on any real fund, LPA, or administrator's statements, and the terms are simplified (see `data/fund_terms.json`). A real LPA's fee basis, offset percentage, equalization rate, and allocation rules all have to be confirmed before a tie-out means anything.

## Run it

Python 3.9+, standard library only.

```
python3 make_example_statements.py   # writes the synthetic statements with seeded breaks + data/answer_key.csv
python3 tieout.py                    # writes report.md
python3 -m unittest discover -s tests -v
```

## What the demo shows

The synthetic statements carry five seeded breaks and one 40-cent rounding difference:

| LP | Seeded problem | Checker result |
|---|---|---|
| LP01 | +$0.40 rounding | Ties (under the $1 tolerance) |
| LP03 | Q3 board-fee offset not applied | Break of -$3,000.00, fee offset named |
| LP05 | Equalization interest from the later close never credited | Break of -$5,260.27, equalization interest named |
| LP08 | Q3 capital call wire received but not posted | Break of -$250,000.00, the July 15 call named |
| LP11 | Later-close LP not charged its Q1 catch-up fee | Break of +$30,000.00; the Q1 catch-up fee is named alongside the Q2 and Q3 fees, since all three are the same size, so a person picks between them |
| LP12 | Q2 write-up not allocated to a later-close LP | Break of -$96,000.00, the Q2 gain named |

Result: all 5 seeded breaks flagged with the right component among the named causes, and all 7 other accounts tie. `tests/test_tieout.py` also re-derives two balances (a first-close LP and a later-close LP) by hand from the terms, independent of the roll-forward code, and checks that equalization interest paid equals interest credited.

## Limits

- One fund, one later close, quarterly events only; no distributions, carried interest, or GP commitment.
- Later-close LPs bear no share of expenses booked before they joined (LP11 and LP12 carry none of the $60,000 Q1 expenses, though they pay the Q1 catch-up fee). Many fund agreements reallocate those early expenses to later-close investors; that rule would be set from the real LPA.
- Diagnosis looks for a single missing or double-counted component. Two errors in one account, or a wrong rate rather than a missing line, come back as "review the account by hand".
- When several components have the same size (LP11), it lists all of them rather than guessing.
