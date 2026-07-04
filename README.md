# The Barbell — Command Center

Concentrated capital allocation. One anchor, one engine, no filler.
This folder is the single source of truth for the strategy: what we hold, why we hold it, and the rules we execute by.

**Snapshot date: 2026-07-04** (update this whenever positions or prices change)

## Current State

| Leg | Ticker | Role | Held | Target | Progress | Px (07/04) | Value |
|---|---|---|---:|---:|---:|---:|---:|
| Anchor | RCR | Quarterly cash vault | 7,817 | 10,000 | 78.2% | ₱7.30 | ₱57,064 |
| Engine | ALTER | Concentrated growth | 124,585 | 500,000 | 24.9% | ₱0.79 | ₱98,422 |
| | | | | | | **Total** | **₱155,486** |

Allocation today: **63% engine / 37% anchor**. At full targets (current prices) it becomes ~84/16 — that is the designed shape of the barbell, not drift.

## The Loop (self-funding flywheel)

```
RCR pays ₱0.11/sh per quarter
  → 7,817 sh × ₱0.11 = ₱859.87 gross → ₱773.88 net of 10% withholding
  → pooled with fresh capital until the clip clears ₱8,000
  → buy ALTER in board lots while price < book value (₱0.91)
  → repeat every quarter until 500,000 shares
```

The dividend loop alone buys ~3,900 ALTER shares/year at ₱0.79. The loop is the flywheel; fresh capital is the fuel. See `playbook.md` §7 for the ammo schedule.

## Files

| File | What it is |
|---|---|
| `thesis.md` | The master thesis and operating rules — the charter. Change it rarely, deliberately. |
| `playbook.md` | Advisor's working assessment: valuation math, catalyst calendar, risk tripwires, execution plan. Refresh quarterly. |
| `ledger.csv` | Every position and transaction. Update after each buy and each dividend. |
| `tools/loop.py` | Buy calculator: checks the ₱8,000 rule, computes fees, board lots, and effective drag before you place an order. |

## Update ritual (quarterly, ~15 minutes)

1. Log the RCR dividend in `ledger.csv` when it lands (ex-dates ~Feb / May / Aug / Nov).
2. Run `python3 tools/loop.py --cash <pooled amount> --alter-price <last>` before any buy.
3. Log the buy in `ledger.csv`; update the snapshot table above.
4. Walk the tripwires in `playbook.md` §6. If none fired, do nothing else. Patience is the position.
