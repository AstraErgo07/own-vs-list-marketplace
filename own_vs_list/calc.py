"""
own_vs_list/calc.py - Own stock vs marketplace listing. Pure functions, no AI.

A decision-support engine for a general merchandise marketplace that both
holds its own stock (1P) and hosts third-party seller listings (3P). Some
stock is assumed to ship across a border, which is reflected in labelled
assumptions (stock cover and cost of goods).

Every input is labelled Published, Observed in sample, Assumption or Model estimate.

The sample products are made-up examples. They are not listings from a live site.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace

import pandas as pd

CATEGORY = "electronics accessories"
BRING_IN_HOUSE, KEEP_3P, TEST_3P_FIRST = "Bring in-house", "Keep 3P", "Test as 3P first"
RECOMMENDATIONS = [BRING_IN_HOUSE, TEST_3P_FIRST, KEEP_3P]
EPSILON = 0.01

# Assumption: a typical marketplace take-rate on the shelf price the customer pays.
# Not a published fee from a named platform.
COMMISSION_ASSUMPTION = 0.12

ESTIMATED_FIELDS = ["cogs", "fulfilment_cost", "return_rate", "markdown_rate",
                    "stock_cover_days", "weekly_units", "weekly_units_cv"]
SAMPLE_FIELDS = ["price", "sold_by", "listing_type", "category", "subcategory", "commission_rate"]


@dataclass
class Benchmark:
    """Assumptions for the category. Every value is editable in the app sidebar."""
    cogs_pct: float            # landed cost (including freight and duty) as share of ex-VAT price
    fulfilment_cost: float     # £ per unit pick, pack, deliver (1P)
    return_rate: float         # share of sales value refunded
    markdown_rate: float       # share of sales value lost to markdowns / clearance
    stock_cover_days: float    # days of stock held if 1P (longer when goods ship across a border)
    ref_weekly_units: float    # weekly units at the reference price
    ref_price: float           # reference price for the units curve
    elasticity: float          # units scale with (ref_price / price) ** elasticity
    weekly_units_cv: float     # default demand volatility (coefficient of variation)


def default_benchmarks() -> dict:
    return {
        # All of these are Assumptions (judgement for imported consumer electronics
        # accessories sold to UK customers). They are not measured from a live catalogue.
        CATEGORY: Benchmark(
            cogs_pct=0.50,
            fulfilment_cost=3.50,
            return_rate=0.10,
            markdown_rate=0.08,
            stock_cover_days=80,   # longer cover for cross-border lead times
            ref_weekly_units=40,
            ref_price=15.0,
            elasticity=1.0,
            weekly_units_cv=0.30,
        ),
    }


@dataclass
class Assumptions:
    holding_rate: float = 0.08                  # physical storage, insurance and shrink only, % of cost a year
                                                # (Assumption). Cost of capital is not in this figure;
                                                # it is tested only by hurdle_rate on return on stock.
    vat_rate: float = 0.20                      # Published: UK standard VAT; shelf prices include it
    hurdle_rate: float = 0.25                   # minimum return on stock to go 1P (Assumption)
    marketplace_cost_per_unit: float = 0.50     # cost to serve one 3P sale (£), Assumption
    diversion_rate: float = 0.25                # share of 3P sales that would have bought the own-brand
                                                # substitute, Assumption
    volatility_cv_threshold: float = 0.50
    near_threshold_band: float = 0.10
    gmv_flag_quantile: float = 0.75
    commission_rate: float = COMMISSION_ASSUMPTION
    benchmarks: dict = field(default_factory=default_benchmarks)

    def with_diversion(self, rate):
        return replace(self, diversion_rate=rate)

    def with_cogs_shift(self, pts):
        b = {c: replace(v, cogs_pct=min(max(v.cogs_pct + pts, 0.05), 0.95))
             for c, v in self.benchmarks.items()}
        return replace(self, benchmarks=b)

    def with_hurdle(self, rate):
        return replace(self, hurdle_rate=rate)

    def to_json(self):
        d = asdict(self)
        return json.dumps(d, sort_keys=True, default=str)


def holding_cost(cogs, stock_cover_days, holding_rate):
    """Physical holding cost per unit: cogs x physical holding rate x days of stock / 365.

    holding_rate here is storage, insurance and shrink only. Cost of capital is not
    subtracted from contribution; it is tested only by comparing return on stock
    with the hurdle. That avoids counting the cost of money twice.
    """
    return cogs * holding_rate * stock_cover_days / 365.0


def contribution_1p(price, cogs, fulfilment_cost, return_rate, markdown_rate, holding):
    """= price - cogs - fulfilment - price x return_rate - price x markdown_rate - holding"""
    return price - cogs - fulfilment_cost - price * return_rate - price * markdown_rate - holding


def contribution_3p(price, commission_rate, marketplace_cost_per_unit):
    """= price x commission_rate - marketplace cost per unit"""
    return price * commission_rate - marketplace_cost_per_unit


def average_inventory_value(cogs, weekly_units, stock_cover_days):
    """= cogs x weekly_units x stock_cover_days / 7"""
    return cogs * weekly_units * (stock_cover_days / 7.0)


def return_on_capital(c1p, cogs, weekly_units, stock_cover_days):
    """annual 1P contribution (52 weeks) / average inventory value"""
    inv = average_inventory_value(cogs, weekly_units, stock_cover_days)
    return (c1p * weekly_units * 52) / inv if inv > 0 else 0.0


def net_3p_benefit(c3p, diversion_rate, lost_1p_contribution):
    """= 3P contribution - diversion_rate x lost 1P contribution on the substitute (floored at 0)"""
    return c3p - diversion_rate * max(lost_1p_contribution, 0.0)


def decide(c1p, net3p, roc, cv, a: Assumptions):
    """Volatility first; near a threshold, test first; 1P only if it beats net 3P
    AND return on stock beats the hurdle; otherwise Keep 3P."""
    band = a.near_threshold_band
    if cv > a.volatility_cv_threshold:
        return TEST_3P_FIRST, "volatile_demand"
    m_pass, r_pass = c1p > net3p, roc > a.hurdle_rate
    near_m = abs(c1p - net3p) <= band * max(abs(net3p), EPSILON)
    near_r = abs(roc - a.hurdle_rate) <= band * max(abs(a.hurdle_rate), EPSILON)
    if m_pass and r_pass:
        near = near_m or near_r
    elif r_pass:
        near = near_m
    elif m_pass:
        near = near_r
    else:
        near = near_m and near_r
    if near:
        return TEST_3P_FIRST, "near_threshold"
    if m_pass and r_pass:
        return BRING_IN_HOUSE, "1p_wins"
    if not m_pass and not r_pass:
        return KEEP_3P, "3p_wins_margin_and_roc"
    return KEEP_3P, "3p_wins_margin" if not m_pass else "roc_below_hurdle"


def estimate_weekly_units(price, b: Benchmark):
    """Model estimate: ref_weekly_units x (ref_price / price) ** elasticity, clamped to 0.5-200."""
    if price <= 0:
        return 0.5
    return min(max(b.ref_weekly_units * (b.ref_price / price) ** b.elasticity, 0.5), 200.0)


def ex_vat(price, vat_rate):
    """Shelf price includes VAT; 1P revenue is price / (1 + VAT)."""
    return price / (1.0 + vat_rate)


def estimate_fields(price, b: Benchmark, vat_rate: float = 0.20, cv_override=None) -> dict:
    """Assumptions and model estimates for one listing from its example price and the category benchmark."""
    e = {
        "cogs": ex_vat(price, vat_rate) * b.cogs_pct,
        "fulfilment_cost": b.fulfilment_cost,
        "return_rate": b.return_rate,
        "markdown_rate": b.markdown_rate,
        "stock_cover_days": b.stock_cover_days,
        "weekly_units": estimate_weekly_units(price, b),
        "weekly_units_cv": b.weekly_units_cv,
    }
    if cv_override is not None and not (isinstance(cv_override, float) and pd.isna(cv_override)):
        try:
            if str(cv_override).strip() != "":
                e["weekly_units_cv"] = float(cv_override)
        except (TypeError, ValueError):
            pass
    return e


def substitute_prices(listings: pd.DataFrame) -> dict:
    """Median shelf price of own-brand (1P) items in the same subcategory."""
    one_p = listings[listings["listing_type"] == "1P"]
    if one_p.empty or "subcategory" not in one_p.columns:
        return {}
    return one_p.groupby("subcategory")["price"].median().to_dict()


def unit_contribution_1p(price, b: Benchmark, holding_rate, vat_rate):
    e = estimate_fields(price, b, vat_rate)
    hold = holding_cost(e["cogs"], e["stock_cover_days"], holding_rate)
    return contribution_1p(ex_vat(price, vat_rate), e["cogs"], e["fulfilment_cost"],
                           e["return_rate"], e["markdown_rate"], hold)


def evaluate_product(row, a: Assumptions, subs: dict) -> dict:
    cat = row["category"]
    b = a.benchmarks[cat]
    price = float(row["price"])
    cv_override = row.get("weekly_units_cv")
    e = estimate_fields(price, b, a.vat_rate, cv_override=cv_override)
    net = ex_vat(price, a.vat_rate)
    hold = holding_cost(e["cogs"], e["stock_cover_days"], a.holding_rate)
    c1p = contribution_1p(net, e["cogs"], e["fulfilment_cost"], e["return_rate"], e["markdown_rate"], hold)
    rate = a.commission_rate
    # Commission is a % of the total the customer pays (VAT-inclusive). The seller, not the
    # marketplace, is assumed to owe the VAT on the goods.
    c3p = contribution_3p(price, rate, a.marketplace_cost_per_unit)
    subcat = row.get("subcategory")
    sub_price = subs.get(subcat)
    sub_c1p = unit_contribution_1p(sub_price, b, a.holding_rate, a.vat_rate) if sub_price else c1p
    div = a.diversion_rate
    net3p = net_3p_benefit(c3p, div, sub_c1p)
    roc = return_on_capital(c1p, e["cogs"], e["weekly_units"], e["stock_cover_days"])
    rec, rule = decide(c1p, net3p, roc, e["weekly_units_cv"], a)
    wu = e["weekly_units"]
    return {
        "sku": row["sku"], "category": cat, "subcategory": subcat, "title": row["title"],
        "sold_by": row["sold_by"],
        "price": price, "price_ex_vat": net, "commission_rate": rate, **e, "holding_cost_unit": hold,
        "substitute_1p_price": sub_price, "substitute_1p_contrib": sub_c1p,
        "gmv_annual": price * wu * 52,
        "contrib_1p_unit": c1p, "contrib_3p_unit": c3p, "diversion_rate": div, "net_3p_unit": net3p,
        "advantage_1p_unit": c1p - net3p, "advantage_1p_annual": (c1p - net3p) * wu * 52,
        "commission_annual": c3p * wu * 52,
        "avg_inventory_value": average_inventory_value(e["cogs"], wu, e["stock_cover_days"]),
        "return_on_capital": roc, "hurdle_rate": a.hurdle_rate,
        "recommendation": rec, "rule": rule,
        "estimated_fields": ";".join(ESTIMATED_FIELDS),
    }


def evaluate_portfolio(listings: pd.DataFrame, a: Assumptions) -> pd.DataFrame:
    """Evaluate every 3P listing; 1P listings are only used as substitutes.
    Ranked by annual 1P advantage (biggest case for bringing in-house first)."""
    subs = substitute_prices(listings)
    cands = listings[listings["listing_type"] == "3P"]
    if cands.empty:
        return pd.DataFrame()
    out = pd.DataFrame([evaluate_product(r, a, subs) for r in cands.to_dict("records")])
    out = out.sort_values("advantage_1p_annual", ascending=False).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out


def gmv_vs_contribution_flags(results, a: Assumptions):
    """GMV in the top quartile but not recommended for in-house."""
    cut = results["gmv_annual"].quantile(a.gmv_flag_quantile)
    m = (results["gmv_annual"] >= cut) & (results["recommendation"] != BRING_IN_HOUSE)
    return results[m].sort_values("gmv_annual", ascending=False)


def sensitivity(listings, a: Assumptions, rates=(0.10, 0.25, 0.50), cogs_shifts=(-0.10, 0.10)):
    base = evaluate_portfolio(listings, a).set_index("sku")["recommendation"]
    scenarios = [(f"Diversion {r:.0%}", a.with_diversion(r)) for r in rates]
    scenarios += [(f"COGS estimate {s:+.0%} pts", a.with_cogs_shift(s)) for s in cogs_shifts]
    rows, flipped = [], {}
    for name, sc in scenarios:
        recs = evaluate_portfolio(listings, sc).set_index("sku")["recommendation"].reindex(base.index)
        ch = recs[recs != base]
        flipped[name] = [f"{k}: {base[k]} -> {recs[k]}" for k in ch.index]
        row = {"scenario": name}
        row.update({rec: int((recs == rec).sum()) for rec in RECOMMENDATIONS})
        row["flipped_vs_current"] = len(ch)
        rows.append(row)
    return pd.DataFrame(rows), flipped, base


def hurdle_sensitivity(listings, a: Assumptions, hurdles=(0.25, 0.50, 1.00)):
    """How recommendations change when only the return-on-stock hurdle moves.

    Default hurdles are 25%, 50% and 100%. These are not industry standards;
    they show how sensitive the answer is to a bar the firm would set itself.
    """
    base = evaluate_portfolio(listings, a).set_index("sku")["recommendation"]
    rows, flipped = [], {}
    for h in hurdles:
        name = f"Hurdle {h:.0%}"
        recs = evaluate_portfolio(listings, a.with_hurdle(h)).set_index("sku")["recommendation"].reindex(base.index)
        ch = recs[recs != base]
        flipped[name] = [f"{k}: {base[k]} -> {recs[k]}" for k in ch.index]
        row = {"scenario": name, "hurdle": h}
        row.update({rec: int((recs == rec).sum()) for rec in RECOMMENDATIONS})
        row["flipped_vs_current"] = len(ch)
        rows.append(row)
    return pd.DataFrame(rows), flipped, base


def load_listings(path) -> pd.DataFrame:
    return pd.read_csv(path)
