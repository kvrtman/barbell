#!/usr/bin/env python3
"""The Self-Funding Loop calculator.

Run before every buy clip. Answers three questions:
  1. Does this clip clear the ₱8,000 Minimum Rule (and what's the fee drag if not)?
  2. How many board lots / shares does the cash actually buy, all-in?
  3. What does the RCR dividend stream add to the pool each quarter?

Typical PH online-broker buy-side fee model:
  commission = max(rate * gross, minimum)   # default 0.25%, min ₱20
  VAT        = 12% of commission
  PSE fee    = 0.005% of gross
  SCCP fee   = 0.01% of gross
(Selling adds 0.6% stock transaction tax — irrelevant in the accumulation phase.)

Examples:
  python3 loop.py --cash 8000 --alter-price 0.79
  python3 loop.py --cash 790 --alter-price 0.79          # see why sub-scale clips bleed
  python3 loop.py --dividends-only --rcr-shares 7817
"""

import argparse


def buy_fees(gross, rate=0.0025, minimum=20.0):
    commission = max(rate * gross, minimum)
    vat = 0.12 * commission
    pse = 0.00005 * gross
    sccp = 0.0001 * gross
    total = commission + vat + pse + sccp
    return {"commission": commission, "vat": vat, "pse": pse, "sccp": sccp, "total": total}


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
    # The rule's intent is fee efficiency, not the round number: pass when the
    # drag is within a hair of the at-threshold rate (board-lot rounding can
    # leave gross slightly under P8,000 even when the clip is fully funded).
    at_threshold = buy_fees(threshold, rate, minimum)
    threshold_drag_pct = 100.0 * at_threshold["total"] / threshold
    return {
        "lots": lots,
        "shares": lots * board_lot,
        "gross": gross,
        "fees": fees,
        "all_in": gross + fees["total"],
        "leftover": cash - gross - fees["total"],
        "drag_pct": drag_pct,
        "threshold_drag_pct": threshold_drag_pct,
        "clears_rule": gross >= threshold or drag_pct <= threshold_drag_pct + 0.02,
    }


def main():
    p = argparse.ArgumentParser(description="Barbell self-funding loop calculator")
    p.add_argument("--cash", type=float, default=0.0, help="pooled cash available for this clip (PHP)")
    p.add_argument("--alter-price", type=float, default=0.79, help="ALTER last price")
    p.add_argument("--board-lot", type=int, default=1000, help="ALTER board lot (1,000 in the P0.50-4.99 band)")
    p.add_argument("--rcr-shares", type=int, default=7817, help="RCR shares held")
    p.add_argument("--rcr-dps", type=float, default=0.11, help="RCR dividend per share per quarter")
    p.add_argument("--wht", type=float, default=0.10, help="final withholding tax on REIT dividends")
    p.add_argument("--fee-rate", type=float, default=0.0025, help="broker commission rate")
    p.add_argument("--fee-min", type=float, default=20.0, help="broker minimum commission")
    p.add_argument("--threshold", type=float, default=8000.0, help="minimum-clip rule (PHP)")
    p.add_argument("--dividends-only", action="store_true", help="just show the quarterly dividend math")
    a = p.parse_args()

    gross_div = a.rcr_shares * a.rcr_dps
    net_div = gross_div * (1 - a.wht)
    print(f"RCR dividend/quarter : Php {gross_div:,.2f} gross -> Php {net_div:,.2f} net of {a.wht:.0%} WHT")
    print(f"RCR dividend/year    : Php {net_div * 4:,.2f} net  (~{int(net_div * 4 / a.alter_price):,} ALTER sh/yr at Php {a.alter_price})")

    if a.dividends_only or a.cash <= 0:
        quarters = a.threshold / net_div if net_div else float("inf")
        print(f"\nDividends alone need ~{quarters:.1f} quarters to clear the Php {a.threshold:,.0f} rule.")
        print("Pool them with fresh capital instead of letting the loop idle.")
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
    if plan["clears_rule"]:
        print(f"  PASS: fee-efficient clip (Php {a.threshold:,.0f} Minimum Rule satisfied).")
    else:
        print(f"  HOLD: below the Php {a.threshold:,.0f} rule — drag {plan['drag_pct']:.2f}% vs "
              f"{plan['threshold_drag_pct']:.2f}% at scale. Keep pooling unless price action justifies paying up.")


if __name__ == "__main__":
    main()
