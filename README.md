# The Barbell — Command Center

Concentrated capital allocation. One anchor, one engine, no filler.
This folder is the single source of truth for the strategy: what we hold, why we hold it, and the rules we execute by.

**Snapshot date: 2026-07-09** (ALTER at 07-09 close, RCR at 07-08 close — update whenever positions or prices change)

## Current State

| Leg | Ticker | Role | Held | Target | Progress | Px (07/09) | Value |
|---|---|---|---:|---:|---:|---:|---:|
| Anchor | RCR | Quarterly cash vault | 7,817 | 10,000 | 78.2% | ₱7.28 | ₱56,908 |
| Engine | ALTER | Concentrated growth | 124,585 | 500,000 | 24.9% | ₱0.76 | ₱94,685 |
| | | | | | | **Total** | **₱151,593** |

Allocation today: **62% engine / 38% anchor**. At full targets (current prices) it becomes ~84/16 — that is the designed shape of the barbell, not drift.

## The Loop (self-funding flywheel)

```
RCR pays ₱0.11/sh per quarter
  → 7,817 sh × ₱0.11 = ₱859.87 gross → ₱773.88 net of 10% withholding
  → pooled with fresh capital into fee-efficient clips
    (₱8,000 preferred · ₱2,500 hard floor · never idle >1 month — thesis rule 2)
  → buy ALTER in board lots while price < book value (₱0.91)
  → repeat every quarter until 500,000 shares
```

The dividend loop alone buys ~4,073 ALTER shares/year at ₱0.76. The loop is the flywheel; fresh capital is the fuel — and the audit (playbook §9) says the pace decides whether you reach the target inside the re-rate window. See the dashboard's accumulation race.

## Files

| File | What it is |
|---|---|
| `thesis.md` | The master thesis and operating rules — the charter. Change it rarely, deliberately. |
| `playbook.md` | Advisor's working assessment: valuation math, catalyst calendar, risk tripwires, execution plan, §9 red-team audit. Refresh quarterly. |
| `ledger.csv` | Every position and transaction. Update after each buy and each dividend. |
| `dashboard.html` | Visual state: tiles, target progress, audited exit scenarios, the accumulation race, the fee curve. Regenerated, never hand-edited. |
| `tools/dashboard.py` | Generates `dashboard.html` from the ledger + current prices (stdlib only). |
| `tools/loop.py` | Pre-trade gatekeeper: ladder zone, fee tier (PASS / OK / HOLD), board lots, peso drag — run before every order. |

## Update ritual (quarterly, ~15 minutes)

1. Log the RCR dividend in `ledger.csv` when it lands (ex-dates ~Feb / May / Aug / Nov).
2. Run `python3 tools/loop.py --cash <pooled amount> --alter-price <last>` before any buy.
3. Log the buy in `ledger.csv`; regenerate the visuals:
   `python3 tools/dashboard.py --alter-price <last> --rcr-price <last> --asof <YYYY-MM-DD>`
4. Refresh the snapshot table above; walk the tripwires in `playbook.md` §6. If none fired, do nothing else. Patience is the position.
