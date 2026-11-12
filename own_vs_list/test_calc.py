"""Unit tests for the Own vs List engine. Run: python3 -m unittest  (from this folder)."""
from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from calc import (
    BRING_IN_HOUSE, KEEP_3P, TEST_3P_FIRST, Assumptions, contribution_1p, contribution_3p,
    decide, default_benchmarks, estimate_fields, estimate_weekly_units, evaluate_portfolio,
    ex_vat, holding_cost, hurdle_sensitivity, load_listings, net_3p_benefit, return_on_capital,
    substitute_prices, unit_contribution_1p,
)
from insights import insights
from workings import own_vs_list_workings

DATA = Path(__file__).resolve().parent / "listings.csv"
# Hand-check at the old 20% blended holding rate, so the arithmetic is easy to follow.
OLD_HOLDING = 0.20


class TestCalc(unittest.TestCase):
    def setUp(self):
        self.listings = load_listings(DATA)
        self.a = Assumptions()
        self.res = evaluate_portfolio(self.listings, self.a)

    def test_1_ex_vat_and_1p_contribution(self):
        # £24.99 shelf, 20% VAT: 24.99 / 1.20 = 20.825
        net = ex_vat(24.99, 0.20)
        self.assertAlmostEqual(net, 24.99 / 1.20, places=6)
        b = default_benchmarks()["electronics accessories"]
        e = estimate_fields(24.99, b, 0.20)
        self.assertAlmostEqual(e["cogs"], net * 0.50, places=6)
        self.assertEqual(e["fulfilment_cost"], 3.50)
        hold = holding_cost(e["cogs"], e["stock_cover_days"], 0.08)
        # physical only: cogs * 0.08 * 80 / 365
        self.assertAlmostEqual(hold, e["cogs"] * 0.08 * 80 / 365, places=6)
        c1p = contribution_1p(net, e["cogs"], 3.50, 0.10, 0.08, hold)
        expected = net - e["cogs"] - 3.50 - net * 0.10 - net * 0.08 - hold
        self.assertAlmostEqual(c1p, expected, places=6)

    def test_2_3p_and_cannibalisation_floor(self):
        # commission 12% of £24.99 minus £0.50
        c3p = contribution_3p(24.99, 0.12, 0.50)
        self.assertAlmostEqual(c3p, 24.99 * 0.12 - 0.50, places=6)
        # substitute contribution negative: cannibalisation floored at 0
        self.assertAlmostEqual(net_3p_benefit(c3p, 0.25, -1.68), c3p, places=6)
        # positive substitute: 3P less diversion * substitute
        self.assertAlmostEqual(net_3p_benefit(c3p, 0.25, 4.00), c3p - 0.25 * 4.00, places=6)

    def test_3_hand_check_at_blended_holding(self):
        """A full decision at holding_rate=0.20, so a known arithmetic path still holds."""
        a = Assumptions(holding_rate=OLD_HOLDING)
        b = a.benchmarks["electronics accessories"]
        price = 24.99
        net = ex_vat(price, a.vat_rate)
        e = estimate_fields(price, b, a.vat_rate)
        hold = holding_cost(e["cogs"], e["stock_cover_days"], OLD_HOLDING)
        c1p = contribution_1p(net, e["cogs"], e["fulfilment_cost"], e["return_rate"], e["markdown_rate"], hold)
        # Independent arithmetic
        self.assertAlmostEqual(hold, e["cogs"] * 0.20 * 80 / 365, places=6)
        self.assertAlmostEqual(c1p, net - e["cogs"] - 3.50 - net * 0.18 - hold, places=6)

    def test_4_physical_holding_not_double_counted(self):
        """Contribution uses only the physical holding rate; cost of capital is the hurdle alone."""
        b = default_benchmarks()["electronics accessories"]
        price = 24.99
        net = ex_vat(price, 0.20)
        e = estimate_fields(price, b, 0.20)
        c_phys = contribution_1p(net, e["cogs"], 3.50, 0.10, 0.08,
                                 holding_cost(e["cogs"], 80, 0.08))
        c_old = contribution_1p(net, e["cogs"], 3.50, 0.10, 0.08,
                                holding_cost(e["cogs"], 80, 0.20))
        self.assertGreater(c_phys, c_old)
        # Default engine uses 8%
        row = self.res[self.res["sku"] == "ACC-3P-02"].iloc[0]
        self.assertAlmostEqual(row["holding_cost_unit"],
                               row["cogs"] * 0.08 * row["stock_cover_days"] / 365, places=6)
        # Return on stock uses that (higher) contribution, and is tested against the hurdle separately
        roc = return_on_capital(row["contrib_1p_unit"], row["cogs"], row["weekly_units"],
                                row["stock_cover_days"])
        self.assertAlmostEqual(roc, row["return_on_capital"], places=6)
        self.assertGreater(roc, self.a.hurdle_rate)
        self.assertEqual(row["recommendation"], BRING_IN_HOUSE)

    def test_5_decision_rules_and_hurdle_sensitivity(self):
        # Volatility first
        rec, rule = decide(5.0, 2.0, 1.5, 0.60, self.a)
        self.assertEqual((rec, rule), (TEST_3P_FIRST, "volatile_demand"))
        # Near threshold on contribution (within 10%)
        rec, rule = decide(1.68, 1.61, 0.92, 0.30, self.a)
        self.assertEqual((rec, rule), (TEST_3P_FIRST, "near_threshold"))
        # 1P wins both
        rec, rule = decide(5.0, 2.0, 1.5, 0.30, self.a)
        self.assertEqual((rec, rule), (BRING_IN_HOUSE, "1p_wins"))
        # 3P wins contribution, ROC clears: Keep 3P
        rec, rule = decide(0.39, 1.30, 0.28, 0.30, self.a)
        self.assertEqual((rec, rule), (KEEP_3P, "3p_wins_margin"))
        # ROC below hurdle, contribution wins
        rec, rule = decide(5.0, 2.0, 0.10, 0.30, self.a)
        self.assertEqual((rec, rule), (KEEP_3P, "roc_below_hurdle"))

        counts = self.res["recommendation"].value_counts().to_dict()
        self.assertEqual(counts.get(BRING_IN_HOUSE, 0), 5)
        self.assertEqual(counts.get(TEST_3P_FIRST, 0), 3)
        self.assertEqual(counts.get(KEEP_3P, 0), 10)

        hs, flipped, _ = hurdle_sensitivity(self.listings, self.a, hurdles=(0.25, 0.50, 1.00, 1.50, 2.00))
        for h in (0.25, 0.50, 1.00):
            self.assertEqual(int(hs[hs.hurdle == h].flipped_vs_current.iloc[0]), 0)
        self.assertGreater(int(hs[hs.hurdle == 1.50].flipped_vs_current.iloc[0]), 0)
        self.assertIn("ACC-3P-10", self.res[self.res.rule == "volatile_demand"]["sku"].tolist())
        self.assertIn("ACC-3P-05", self.res[self.res.rule == "near_threshold"]["sku"].tolist())

    def test_6_insights_match_the_engine(self):
        bullets = insights(self.listings, self.a)
        text = " ".join(bullets)
        self.assertTrue(all(b.startswith("In this sample, under these assumptions")
                            or b.startswith("Contribution per unit and return on stock")
                            for b in bullets))
        self.assertIn("Bring in-house 5", text)
        self.assertIn("Test as 3P first 3", text)
        self.assertIn("Keep 3P 10", text)
        self.assertIn("10000mAh Power Bank", text)
        self.assertIn("flips no recommendations", text)
        # no em or en dashes
        self.assertNotIn("\u2014", text)
        self.assertNotIn("\u2013", text)

    def test_7_zero_and_missing_data(self):
        self.assertEqual(estimate_weekly_units(0, default_benchmarks()["electronics accessories"]), 0.5)
        rec, rule = decide(0, 0, 0, 0, self.a)
        # 0 contribution vs 0, ROC 0 vs 25% hurdle: both fail, and 0 vs 25% is not
        # inside the 10% band, so Keep 3P on both tests.
        self.assertEqual((rec, rule), (KEEP_3P, "3p_wins_margin_and_roc"))
        # empty 3P frame: evaluate_portfolio should return an empty ranked frame, not crash
        only_1p = self.listings[self.listings.listing_type == "1P"]
        out = evaluate_portfolio(only_1p, self.a)
        self.assertTrue(out.empty or list(out.columns))

    def test_8_substitutes_are_by_subcategory(self):
        subs = substitute_prices(self.listings)
        self.assertAlmostEqual(subs["charger"], 12.99, places=2)
        self.assertAlmostEqual(subs["cable"], 6.99, places=2)
        self.assertAlmostEqual(subs["earbuds"], 24.99, places=2)
        row = self.res[self.res["sku"] == "ACC-3P-02"].iloc[0]
        self.assertAlmostEqual(row["substitute_1p_price"], 12.99, places=2)

    def test_9_plain_workings_match_the_engine(self):
        row = self.res.iloc[0].to_dict()
        steps = own_vs_list_workings(row, self.a)
        results = {s["step"]: s["result"] for s in steps}
        self.assertIn("= 1P contribution per unit", results)
        self.assertIn("= 3P value per unit", results)
        # contribution figure in the workings equals the engine, formatted
        from workings import _gbp
        self.assertEqual(results["= 1P contribution per unit"], _gbp(row["contrib_1p_unit"]))
        self.assertEqual(results["= 3P value per unit"], _gbp(row["net_3p_unit"]))
        self.assertEqual(results["Decision"], row["recommendation"])


if __name__ == "__main__":
    unittest.main()
