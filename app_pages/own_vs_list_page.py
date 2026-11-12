"""
Own stock vs marketplace listing. Numbers: own_vs_list/calc.py.
You accept or override every recommendation. There is no chatbot.
"""
from __future__ import annotations

import sys
import traceback
from dataclasses import replace
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.decisions import load_decisions, now, save_decision  # noqa: E402
from common.text import VERSION  # noqa: E402
from own_vs_list.calc import (  # noqa: E402
    CATEGORY, ESTIMATED_FIELDS, RECOMMENDATIONS, Assumptions, default_benchmarks,
    evaluate_portfolio, hurdle_sensitivity, load_listings, sensitivity, substitute_prices,
)
from own_vs_list.insights import insights  # noqa: E402
from own_vs_list.workings import (  # noqa: E402
    HOLDING_SPLIT_TEXT, HURDLE_TEXT, decision_rules, decision_sentence, own_vs_list_workings,
)

DATA = ROOT / "own_vs_list" / "listings.csv"
LOG = ROOT / "own_vs_list" / "decisions.csv"
LOG_COLS = ["timestamp", "sku", "title", "category", "sold_by", "model_recommendation", "final_decision",
            "action", "reason", "assumptions"]


def sidebar() -> Assumptions:
    d = Assumptions()
    sb = st.sidebar
    sb.header("Assumptions")
    sb.caption("🟢 = published  ·  🟠 = assumption or model estimate  ·  ⚙️ = policy")
    hurdle = sb.slider("🟠 Minimum yearly return on money tied up in stock (hurdle)", 0.0, 3.0, d.hurdle_rate, 0.01, format="%.2f")
    sb.caption("Assumption. Firms set their own bar (cost of capital plus a cushion). 25% is my starting point, not a published standard. See the hurdle note on the page.")
    holding = sb.slider("🟠 Physical holding rate (storage, insurance and shrink, % of stock cost a year)", 0.0, 0.5, d.holding_rate, 0.01, format="%.2f")
    sb.caption("Assumption. Cost of capital is not in this figure; it is tested only by the hurdle. See the method note on the page.")
    mkt = sb.slider("⚙️ Marketplace cost per 3P unit (£)", 0.0, 3.0, d.marketplace_cost_per_unit, 0.05)
    vat = sb.slider("🟢 VAT rate (shelf prices include it)", 0.0, 0.25, d.vat_rate, 0.01, format="%.2f")
    sb.caption("Published: UK standard VAT. The example prices include it.")
    comm = sb.slider("🟠 Commission (share of the shelf price)", 0.0, 0.25, d.commission_rate, 0.01, format="%.2f")
    sb.caption("Assumption: a typical marketplace take-rate, not a published fee from a named platform.")
    div = sb.slider("🟠 Diversion rate", 0.0, 1.0, d.diversion_rate, 0.05)
    sb.caption("Share of seller sales that would otherwise buy the marketplace's own-brand substitute.")
    sb.subheader("🟠 Category benchmarks (assumptions)")
    b = default_benchmarks()[CATEGORY]
    with sb.expander(CATEGORY.capitalize()):
        bench = replace(
            b,
            cogs_pct=st.slider("Landed cost, % of ex-VAT price (includes freight and duty)", 0.1, 0.9, b.cogs_pct, 0.01, key="b_cogs"),
            fulfilment_cost=st.slider("Fulfilment £/unit", 0.0, 20.0, b.fulfilment_cost, 0.25, key="b_ful"),
            return_rate=st.slider("Return rate", 0.0, 0.3, b.return_rate, 0.01, key="b_ret"),
            markdown_rate=st.slider("Markdown rate", 0.0, 0.4, b.markdown_rate, 0.01, key="b_md"),
            stock_cover_days=st.slider("Stock cover (days). Longer if goods ship across a border.", 7, 180, int(b.stock_cover_days), 1, key="b_cov"),
            ref_weekly_units=st.slider(f"Weekly units at £{b.ref_price:.0f}", 0.5, 100.0, float(b.ref_weekly_units), 0.5, key="b_u"),
            elasticity=st.slider("How fast units fall as price rises (1 = units halve when price doubles)", 0.0, 3.0, b.elasticity, 0.1, key="b_el"),
            weekly_units_cv=st.slider("Default week-to-week demand swing (share of average)", 0.0, 1.5, b.weekly_units_cv, 0.05, key="b_cv"),
        )
    with sb.expander("Test-first triggers (policy)"):
        vol = st.slider("Test first if weekly demand swings by more than (share of average)", 0.0, 2.0, d.volatility_cv_threshold, 0.05)
        band = st.slider("Too close to call if within (share)", 0.0, 0.5, d.near_threshold_band, 0.01, format="%.2f")
    return Assumptions(
        holding_rate=holding, vat_rate=vat, hurdle_rate=hurdle, marketplace_cost_per_unit=mkt,
        diversion_rate=div, volatility_cv_threshold=vol, near_threshold_band=band,
        commission_rate=comm, benchmarks={CATEGORY: bench},
    )


def table(res: pd.DataFrame) -> pd.DataFrame:
    units = res["weekly_units"] * 52
    return pd.DataFrame({
        "Rank": res["rank"], "SKU": res["sku"], "Product": res["title"].str.slice(0, 50),
        "Subcategory": res["subcategory"], "Seller": res["sold_by"],
        "🟠 Est. units/year": units.round(0),
        "🟢 Avg selling price per unit (£)": res["price"].round(2),
        "🟠 Est. GMV/year (£)": res["gmv_annual"].round(0),
        "🟠 1P contribution £/unit": res["contrib_1p_unit"].round(2),
        "🟠 3P value £/unit": res["net_3p_unit"].round(2),
        "🟠 1P advantage £/yr": res["advantage_1p_annual"].round(0),
        "🟠 Return on stock money %": (res["return_on_capital"] * 100).round(0),
        "Recommendation": res["recommendation"],
    })


a = sidebar()
try:
    listings = load_listings(DATA)
    res = evaluate_portfolio(listings, a)
    subs = substitute_prices(listings)
except Exception:
    st.error("Something went wrong loading or calculating the data. Details:")
    st.code(traceback.format_exc())
    st.caption(f"Own vs List {VERSION}")
    st.stop()

st.title("Own stock vs marketplace listing")
st.caption(f"Own vs List {VERSION}")
st.markdown(
    "Should a marketplace buy and stock a product itself (1P), leave it to a seller (3P), or test "
    "it on the marketplace first? This is a decision-support prototype on made-up example products "
    "in one category: consumer electronics accessories. The calculations are plain Python rules. "
    "You make the call. It tests the method; it is not a forecast."
)
st.info(
    f"Made-up sample: {len(listings)} example products "
    f"({int((listings.listing_type == '3P').sum())} seller listings, "
    f"{int((listings.listing_type == '1P').sum())} own-brand substitutes). "
    "Prices and names are invented. Estimated (🟠): " + ", ".join(ESTIMATED_FIELDS) +
    ". Published: UK standard VAT at 20%. Commission, costs, volumes and the hurdle are assumptions "
    "you can edit in the sidebar.",
    icon="ℹ️",
)

counts = res["recommendation"].value_counts()
for col, rec in zip(st.columns(3), RECOMMENDATIONS):
    col.metric(rec, int(counts.get(rec, 0)))

st.subheader("Insights from this sample")
st.caption(
    "These observations are taken from the model at the default assumptions, not from the sliders. "
    "Every claim is worded as a finding in this sample under those assumptions, not as a business result."
)
default_a = Assumptions()
for bullet in insights(listings, default_a):
    st.markdown(f"- {bullet}")
with st.expander("How holding cost and the hurdle are split (method)"):
    st.markdown(HOLDING_SPLIT_TEXT)
with st.expander("Why the hurdle is 25%, and what a typical bar looks like"):
    st.markdown(HURDLE_TEXT)

st.subheader("Ranked seller (3P) products")
st.caption(
    "GMV = units × average selling price (the shelf price). In this sample, at the default price "
    "curve (elasticity 1), every listing gets the same estimated GMV, so GMV is not a useful ranking. "
    "The table is ranked by 1P advantage a year = (1P contribution per unit − 3P value per unit) × units a year. "
    "Click a row to see its workings."
)
with st.expander("How these numbers are worked out"):
    st.markdown("Decision rules, in order:")
    for r in decision_rules(a):
        st.markdown(f"- {r}")
    st.markdown(
        "Worked example: the top-ranked product with the current sliders. Pick any product further down "
        "the page to see its own workings."
    )
    top = res.iloc[0].to_dict()
    st.markdown(f"{top['sku']}: {top['title']}")
    st.table(pd.DataFrame(own_vs_list_workings(top, a)).rename(columns=str.capitalize).set_index("Step"))
event = st.dataframe(
    table(res), hide_index=True, width="stretch", on_select="rerun",
    selection_mode="single-row", key="ovl_table",
    column_config={
        "🟠 Return on stock money %": st.column_config.NumberColumn(format="%d%%"),
        "🟠 Est. GMV/year (£)": st.column_config.NumberColumn(format="£%d"),
    },
)

st.subheader("Sensitivity: how many recommendations flip?")
summ, flipped, _ = sensitivity(listings, a)
st.caption(
    "Diversion is the share of seller buyers who would otherwise buy the own-brand item. "
    "COGS rows move the landed-cost estimate by ±10 points. Cost is the biggest unknown without supplier data."
)
st.dataframe(
    summ.rename(columns={"scenario": "Scenario", "flipped_vs_current": "Flipped vs current"}),
    hide_index=True, width="stretch",
)
st.markdown("**If only the return-on-stock hurdle changes**")
st.caption(
    "25%, 50% and 100% are illustration points, not industry standards. 150% and 200% are included "
    "because in this sample the lower bars often do not change the answer. Compared with the hurdle "
    "currently set in the sidebar."
)
hsumm, hflipped, _ = hurdle_sensitivity(listings, a, hurdles=(0.25, 0.50, 1.00, 1.50, 2.00))
st.dataframe(
    hsumm.drop(columns=["hurdle"]).rename(
        columns={"scenario": "Scenario", "flipped_vs_current": "Flipped vs current"}),
    hide_index=True, width="stretch",
)
with st.expander("Which products flip?"):
    for k, items in {**flipped, **hflipped}.items():
        st.markdown(f"**{k}:** " + (", ".join(items) if items else "no changes"))

st.subheader("Product detail and your decision")
skus = res["sku"].tolist()
rows = event.selection.rows if event is not None and hasattr(event, "selection") else []
picked = skus[rows[0]] if rows else None
if picked and st.session_state.get("_ovl_last") != picked:
    st.session_state["ovl_pick"] = picked
st.session_state["_ovl_last"] = picked
names = dict(zip(res["sku"], res["title"]))
sku = st.selectbox("Product", skus, format_func=lambda s: f"{s}: {names[s]}", key="ovl_pick")
c = res[res["sku"] == sku].iloc[0].to_dict()

left, right = st.columns([3, 2])
with left:
    st.markdown(f"**Calculated recommendation:** {c['recommendation']}")
    st.markdown("**Why:**  \n" + decision_sentence(c, a))
    st.markdown(
        f"**The two money tests:** 1P contribution {c['contrib_1p_unit']:+.2f} a unit vs net 3P "
        f"{c['net_3p_unit']:+.2f}; return on stock {c['return_on_capital']:.0%} vs a "
        f"{c['hurdle_rate']:.0%} hurdle. Demand swing {c['weekly_units_cv']:.0%}."
    )
with right:
    st.markdown("**Workings, step by step**")
    st.table(pd.DataFrame(own_vs_list_workings(c, a)).rename(columns=str.capitalize).set_index("Step"))

with st.container(border=True):
    st.markdown(f"**Your decision for {sku}**. The model recommends *{c['recommendation']}*")
    reason = st.text_area("Reason (required to override)", key=f"ovl_reason_{sku}")
    alt = st.selectbox(
        "If overriding, your decision",
        [r for r in RECOMMENDATIONS if r != c["recommendation"]],
        key=f"ovl_alt_{sku}",
    )
    b1, b2 = st.columns(2)
    base = {
        "timestamp": now(), "sku": sku, "title": c["title"], "category": c["category"],
        "sold_by": c["sold_by"], "model_recommendation": c["recommendation"],
        "reason": reason.strip(), "assumptions": a.to_json(),
    }
    if b1.button("✅ Accept recommendation", key=f"ovl_acc_{sku}", width="stretch"):
        save_decision(dict(base, final_decision=c["recommendation"], action="accept"), LOG, LOG_COLS)
        st.success(f"Saved: accepted '{c['recommendation']}' for {sku}.")
    if b2.button("✏️ Override", key=f"ovl_ovr_{sku}", width="stretch"):
        if not reason.strip():
            st.error("Please give a reason for the override.")
        else:
            save_decision(dict(base, final_decision=alt, action="override"), LOG, LOG_COLS)
            st.success(f"Saved: overrode to '{alt}' for {sku}.")

with st.expander("Own-brand (1P) listings used as substitutes"):
    st.caption("Median price per subcategory = the 1P substitute in the cannibalisation calculation.")
    st.write({k: f"£{v:.2f}" for k, v in subs.items()})
    st.dataframe(
        listings[listings.listing_type == "1P"][["sku", "subcategory", "title", "price"]],
        hide_index=True, width="stretch",
    )

with st.expander("Data sources and assumptions (short version; full page in the menu)"):
    st.markdown("""
- **Made-up sample:** 28 example products in consumer electronics accessories. Prices, titles and seller labels are invented. Nothing here was collected from a live marketplace.
- **Published:** UK standard VAT at 20%. Shelf prices include it. 1P revenue is price / 1.20.
- **Assumption:** commission of 12% of the shelf price (a typical marketplace take-rate, not a published fee from a named platform); landed cost of goods 50% of the ex-VAT price, including freight and duty; fulfilment £3.50; returns 10%; markdowns 8%; 80 days of stock (longer cover for goods that ship across a border); 40 weekly units at a £15 reference price; 30% default demand swing (two gift and travel lines are set higher); diversion 25%; marketplace cost 50p a 3P sale; physical holding 8%; return-on-stock hurdle 25%.
- **Split:** contribution only takes off physical holding (storage, insurance and shrink). Cost of capital is tested only by the hurdle.
- **Model estimate:** weekly units from the price curve; 1P contribution, net 3P value and return on stock from the formulas on this page.
""")

st.subheader("Decision log (own_vs_list/decisions.csv)")
st.caption("On Streamlit Community Cloud this log does not persist across sessions. Download it if you want to keep it.")
log = load_decisions(LOG, LOG_COLS)
if log.empty:
    st.caption("No decisions saved yet.")
else:
    st.dataframe(log.drop(columns=["assumptions"]).iloc[::-1], hide_index=True, width="stretch")
    st.download_button(
        "Download decision log as CSV",
        data=log.to_csv(index=False),
        file_name="decision_log.csv",
        mime="text/csv",
    )
