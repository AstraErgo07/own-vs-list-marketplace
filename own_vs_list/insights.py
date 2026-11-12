"""Factual observations from the model at a given set of assumptions."""
from __future__ import annotations

from collections import Counter

import pandas as pd

try:
    from .calc import (BRING_IN_HOUSE, KEEP_3P, RECOMMENDATIONS, TEST_3P_FIRST, Assumptions,
                       evaluate_portfolio, hurdle_sensitivity)
except ImportError:
    from calc import (BRING_IN_HOUSE, KEEP_3P, RECOMMENDATIONS, TEST_3P_FIRST, Assumptions,
                      evaluate_portfolio, hurdle_sensitivity)


def gbp(x, dp=2):
    return f"-£{abs(x):,.{dp}f}" if x < 0 else f"£{x:,.{dp}f}"


def _counts(res: pd.DataFrame) -> dict:
    return {r: int((res["recommendation"] == r).sum()) for r in RECOMMENDATIONS}


def disagreement(res: pd.DataFrame, a: Assumptions) -> pd.DataFrame:
    """Products where contribution per unit and return on stock disagree on the 1P case."""
    m = res["contrib_1p_unit"] > res["net_3p_unit"]
    r = res["return_on_capital"] > a.hurdle_rate
    out = res[(m != r)].copy()
    out["disagreement"] = [
        "1P wins on contribution, return on stock is below the hurdle" if mi and not ri
        else "return on stock clears the hurdle, 3P is worth more per unit"
        for mi, ri in zip(m[out.index], r[out.index])
    ]
    return out


def insights(listings: pd.DataFrame, a: Assumptions | None = None) -> list[str]:
    """Factual bullets at the given assumptions (defaults if none).

    Every bullet starts from engine output and is worded as a finding in this
    sample under these assumptions, not as a business result.
    """
    a = a or Assumptions()
    res = evaluate_portfolio(listings, a)
    n_list = len(listings)
    n_3p = int((listings.listing_type == "3P").sum())
    n_1p = int((listings.listing_type == "1P").sum())
    c = _counts(res)
    bullets = [
        f"In this sample, under these assumptions, {n_list} example products ({n_3p} seller listings, "
        f"{n_1p} own-brand substitutes) give: {BRING_IN_HOUSE} {c[BRING_IN_HOUSE]}, "
        f"{TEST_3P_FIRST} {c[TEST_3P_FIRST]}, {KEEP_3P} {c[KEEP_3P]}. These are model results on "
        f"made-up products, not a forecast of revenue."
    ]

    # Price-point pattern: cheaper stay 3P because fulfilment eats contribution
    inh = res[res["recommendation"] == BRING_IN_HOUSE]
    keep = res[res["recommendation"] == KEEP_3P]
    if len(keep) and (keep["contrib_1p_unit"] < 0).any():
        neg = keep[keep["contrib_1p_unit"] < 0]
        ful = float(keep["fulfilment_cost"].iloc[0])
        cheap = gbp(neg["price"].min()) if len(neg) == 1 else f"{gbp(neg['price'].min())} to {gbp(neg['price'].max())}"
        ex = neg.sort_values("contrib_1p_unit").iloc[0]
        bullets.append(
            f"In this sample, under these assumptions, the cheaper accessories stay 3P. "
            f"{len(neg)} listings priced {cheap} have negative 1P contribution after a "
            f"{gbp(ful)} pick, pack and delivery cost. Example: {ex['title']} at {gbp(ex['price'])} "
            f"would make {gbp(ex['contrib_1p_unit'])} a unit if stocked, against a net 3P value of "
            f"{gbp(ex['net_3p_unit'])}."
        )
    if len(inh):
        dear = (gbp(inh["price"].iloc[0]) if len(inh) == 1 or inh["price"].min() == inh["price"].max()
                else f"{gbp(inh['price'].min())} to {gbp(inh['price'].max())}")
        roc = inh["return_on_capital"]
        names = ", ".join(inh.sort_values("price")["title"].tolist())
        bullets.append(
            f"In this sample, under these assumptions, {len(inh)} dearer everyday lines "
            f"({dear}: {names}) come out as Bring in-house. 1P contribution per unit is higher "
            f"and return on stock is between {roc.min():.0%} and {roc.max():.0%}."
        )

    # Near threshold
    near = res[res["rule"] == "near_threshold"]
    for _, ex in near.iterrows():
        bullets.append(
            f"In this sample, under these assumptions, {ex['title']} is Test as 3P first because "
            f"the two contribution figures are too close to call: {gbp(ex['contrib_1p_unit'])} 1P "
            f"against {gbp(ex['net_3p_unit'])} net 3P, which is within the "
            f"{a.near_threshold_band:.0%} band."
        )

    # Volatility
    vol = res[res["rule"] == "volatile_demand"]
    if not vol.empty:
        names = ", ".join(vol["title"].tolist())
        cvs = " and ".join(f"{r['weekly_units_cv']:.0%}" for _, r in vol.iterrows())
        bullets.append(
            f"In this sample, under these assumptions, {len(vol)} seasonal or gift lines "
            f"({names}) are Test as 3P first solely because weekly demand is treated as swinging "
            f"by {cvs}, above the {a.volatility_cv_threshold:.0%} limit. They would otherwise pass "
            f"both money tests; the money tests do not get a say."
        )

    # Disagreement
    d = disagreement(res, a)
    unit_lose_roc_win = d[d["disagreement"].str.startswith("return on stock")]
    unit_win_roc_lose = d[d["disagreement"].str.startswith("1P wins")]
    if unit_win_roc_lose.empty:
        bullets.append(
            f"In this sample, under these assumptions, no listing wins on contribution per unit "
            f"and then fails the {a.hurdle_rate:.0%} return-on-stock hurdle."
        )
    else:
        bullets.append(
            f"In this sample, under these assumptions, {len(unit_win_roc_lose)} listings win on "
            f"contribution per unit but fail the {a.hurdle_rate:.0%} return-on-stock hurdle, so "
            f"they are not recommended in-house."
        )
    if not unit_lose_roc_win.empty:
        ex = unit_lose_roc_win.sort_values("return_on_capital", ascending=False).iloc[0]
        titles = ", ".join(
            f"{r['title']} ({r['return_on_capital']:.0%})"
            for _, r in unit_lose_roc_win.sort_values("return_on_capital", ascending=False).iterrows()
        )
        bullets.append(
            f"Contribution per unit and return on stock do disagree in this sample. "
            f"{len(unit_lose_roc_win)} listings clear the {a.hurdle_rate:.0%} hurdle on return on "
            f"stock but 3P is still worth more per unit, so they stay 3P (both tests must pass): "
            f"{titles}. Example: {ex['title']} makes {gbp(ex['contrib_1p_unit'])} 1P contribution "
            f"a unit and {ex['return_on_capital']:.0%} return on stock, but net 3P is "
            f"{gbp(ex['net_3p_unit'])}."
        )

    # Hurdle fragility
    hs, _, _ = hurdle_sensitivity(listings, a, hurdles=(0.25, 0.50, 1.00, 1.50, 2.00))
    first_flip = hs[hs["flipped_vs_current"] > 0]
    h25 = int(hs[hs.hurdle == 0.25].flipped_vs_current.iloc[0])
    h50 = int(hs[hs.hurdle == 0.50].flipped_vs_current.iloc[0])
    h100 = int(hs[hs.hurdle == 1.00].flipped_vs_current.iloc[0])
    if h25 == 0 and h50 == 0 and h100 == 0:
        msg = (
            f"In this sample, under these assumptions, raising the hurdle from {a.hurdle_rate:.0%} "
            f"to 50% or 100% flips no recommendations. Every listing that wins on contribution per "
            f"unit already clears 100% return on stock, so the {a.hurdle_rate:.0%} bar is not what "
            f"decides these cases."
        )
        if not first_flip.empty:
            row = first_flip.iloc[0]
            h200 = hs[hs.hurdle == 2.00]
            msg += (
                f" The bar starts to matter higher up: at {row['hurdle']:.0%} there are "
                f"{int(row['flipped_vs_current'])} flips, and at 200% there are "
                f"{int(h200.flipped_vs_current.iloc[0])} (Bring in-house falls to "
                f"{int(h200[BRING_IN_HOUSE].iloc[0])})."
            )
        bullets.append(msg)

    return bullets
