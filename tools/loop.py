#!/usr/bin/env python3
"""The Self-Funding Loop calculator — the gatekeeper at the buy button.

Run before every buy clip. Answers four questions:
  1. Where does the price sit on the thesis ladder (gift / standard / accretive / stop)?
  2. What is the fee drag on this clip, in percent and in pesos?
  3. Which tier is the clip — PASS (fee-efficient), OK (allowed for long-horizon
     accumulation under thesis rule 2 v2), or HOLD (below the P2,500 sanity floor)?
  4. What does the RCR dividend stream add to the pool each quarter?

Fee rule v2 (thesis rule 2, amended 2026-07-04): P8,000 is where the P20 minimum
commission stops binding (0.30% all-in). Below it is ALLOWED — entry fees are paid
once and amortize to noise on a 5-10yr horizon — down to a P2,500 hard floor
(~1% drag). Never hoard deployable cash >1 month below book to round up a clip.

Typical PH online-broker buy-side fee model:
  commission = max(rate * gross, minimum)   # default 0.25%, min P20
  VAT        = 12% of commission
  PSE fee    = 0.005% of gross
  SCCP fee   = 0.01% of gross
(Selling adds 0.6% stock transaction tax — irrelevant in the accumulation phase.)

Examples:
  python3 loop.py --cash 8000 --alter-price 0.78
  python3 loop.py --cash 3000 --alter-price 0.78      # OK tier: allowed, priced
  python3 loop.py --cash 1200 --alter-price 0.78      # HOLD: below the floor
  python3 loop.py --dividends-only
"""

import argparse

FLOOR = 2500.0  # hard floor: ~1% drag; below this the flat minimum fee is real leakage
BOOK = 0.91


def buy_fees(gross, rate=0.0025, minimum=20.0):
    commission = max(rate * gross, minimum)
    vat = 0.12 * commission
    pse = 0.00005 * gross
    sccp = 0.0001 * gross
    total = commission + vat + pse + sccp
    return {"commission": commission, "vat": vat, "pse": pse, "sccp": sccp, "total": total}


def ladder_zone(price):
    if price < 0.75:
        return "GIFT ZONE (<P0.75) — maximum aggression"
    if price < 0.85:
        return "standard accumulation (P0.75-0.85)"
    if price < BOOK:
        return "still below book (P0.85-0.91) — accretive"
    return f"AT/ABOVE BOOK P{BOOK} — ladder says STOP pre-COD; re-underwrite before buying"


def plan_buy(cash, price, board_lot, rate, minimum, threshold):
    # Max board lots such that gross + fees <= cash
    lots = int(cash // (price * board_lot))
    while lots > 0:
        gross = lots * board_lot * price
        fees = buy_fees(gross, rate, minimum)
        if gross + fees["total"] <= cash:
            break
        lots -= 1
    if lots == 0:
        return None
    gross = lots * board_lot * price
    fees = buy_fees(gross, rate, minimum)
    drag_pct = 100.0 * fees["total"] / gross
    at_threshold = buy_fees(threshold, rate, minimum)
    threshold_drag_pct = 100.0 * at_threshold["total"] / threshold
    # Peso cost of this clip's inefficiency vs the same gross at full-clip drag
    overpay = fees["total"] - gross * threshold_drag_pct / 100.0
    # Tier on drag, not on gross: board-lot rounding can pull gross slightly
    # under a round number without changing the economics.
    if gross >= threshold or drag_pct <= threshold_drag_pct + 0.02:
        tier = "PASS"
    elif drag_pct <= 1.0:  # ~the drag at the P2,500 floor
        tier = "OK"
    else:
        tier = "HOLD"
    return {
        "lots": lots,
        "shares": lots * board_lot,
        "gross": gross,
        "fees": fees,
        "all_in": gross + fees["total"],
        "leftover": cash - gross - fees["total"],
        "drag_pct": drag_pct,
        "threshold_drag_pct": threshold_drag_pct,
        "overpay": max(overpay, 0.0),
        "tier": tier,
    }


def main():
    p = argparse.ArgumentParser(description="Barbell self-funding loop calculator")
    p.add_argument("--cash", type=float, default=0.0, help="pooled cash available for this clip (PHP)")
    p.add_argument("--alter-price", type=float, default=0.78, help="ALTER last price")
    p.add_argument("--board-lot", type=int, default=1000, help="ALTER board lot (1,000 in the P0.50-4.99 band)")
    p.add_argument("--rcr-shares", type=int, default=7817, help="RCR shares held")
    p.add_argument("--rcr-dps", type=float, default=0.11, help="RCR dividend per share per quarter")
    p.add_argument("--wht", type=float, default=0.10, help="final withholding tax on REIT dividends")
    p.add_argument("--fee-rate", type=float, default=0.0025, help="broker commission rate")
    p.add_argument("--fee-min", type=float, default=20.0, help="broker minimum commission")
    p.add_argument("--threshold", type=float, default=8000.0, help="preferred full-clip size (PHP)")
    p.add_argument("--dividends-only", action="store_true", help="just show the quarterly dividend math")
    a = p.parse_args()

    gross_div = a.rcr_shares * a.rcr_dps
    net_div = gross_div * (1 - a.wht)
    print(f"RCR dividend/quarter : Php {gross_div:,.2f} gross -> Php {net_div:,.2f} net of {a.wht:.0%} WHT")
    print(f"RCR dividend/year    : Php {net_div * 4:,.2f} net  (~{int(net_div * 4 / a.alter_price):,} ALTER sh/yr at Php {a.alter_price})")
    print(f"Ladder zone          : {ladder_zone(a.alter_price)}")

    if a.dividends_only or a.cash <= 0:
        quarters = a.threshold / net_div if net_div else float("inf")
        print(f"\nDividends alone need ~{quarters:.1f} quarters to reach a Php {a.threshold:,.0f} full clip.")
        print(f"Pool them with fresh capital — and remember rule 2 v2: anything above Php {FLOOR:,.0f} is deployable.")
        return

    plan = plan_buy(a.cash, a.alter_price, a.board_lot, a.fee_rate, a.fee_min, a.threshold)
    print(f"\nClip: Php {a.cash:,.2f} at ALTER Php {a.alter_price} (board lot {a.board_lot:,})")
    if plan is None:
        print("  Cash does not cover a single board lot + fees. Keep pooling.")
        return

    f = plan["fees"]
    print(f"  Buy {plan['lots']} lot(s) = {plan['shares']:,} shares, gross Php {plan['gross']:,.2f}")
    print(f"  Fees: commission {f['commission']:,.2f} + VAT {f['vat']:,.2f} + PSE {f['pse']:,.2f} + SCCP {f['sccp']:,.2f} = Php {f['total']:,.2f}  ({plan['drag_pct']:.2f}% drag)")
    print(f"  All-in Php {plan['all_in']:,.2f}, leftover Php {plan['leftover']:,.2f} stays in the pool")
    if plan["tier"] == "PASS":
        print(f"  PASS: fee-efficient clip (~{plan['threshold_drag_pct']:.2f}% at-scale drag).")
    elif plan["tier"] == "OK":
        print(f"  OK: below the Php {a.threshold:,.0f} full clip but above the Php {FLOOR:,.0f} floor — allowed for "
              f"long-horizon accumulation. Inefficiency vs a full clip: Php {plan['overpay']:,.2f} (one-time).")
        print("     Prefer pooling to Php 8,000 when the price isn't running; never wait more than ~a month.")
    else:
        print(f"  HOLD: Php {plan['gross']:,.2f} is below the Php {FLOOR:,.0f} sanity floor — {plan['drag_pct']:.2f}% drag "
              f"is real leakage (Php {plan['overpay']:,.2f} torched vs a full clip). Keep pooling.")
    if a.alter_price >= BOOK:
        print(f"  WARNING: price >= book (P{BOOK}). The ladder says stop pre-COD — check playbook §6 tripwires first.")


if __name__ == "__main__":
    main()
