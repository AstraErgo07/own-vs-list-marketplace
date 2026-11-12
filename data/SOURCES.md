# Data and method

Own stock vs marketplace listing (1P vs 3P) is a decision-support prototype. It uses
made-up example products. It is a test of the method, not a forecast and not a
description of any live marketplace.

## The sample

28 invented products in one category, consumer electronics accessories (chargers,
cables, power banks, cases, earbuds, a hub, a tracker, a charging pad, a car charger,
a screen protector):

- 18 listed by example sellers (3P), labelled Example Seller A to F.
- 10 own-brand substitutes (1P), used only to estimate sales the marketplace would
  lose if a buyer picked the seller's item instead.

Prices, titles and seller labels are invented. Nothing in this repository was
collected from a live marketplace website. There is no source URL, and no page was
read automatically or by hand from a retailer's catalogue.

## Labels on every input

- **Published.** UK standard VAT at 20%. The example shelf prices include it. 1P
  revenue is price / 1.20. VAT is a published UK rate, not a measured figure from
  a marketplace.
- **Observed in sample.** The example prices, titles, seller labels, listing type
  and subcategory. These are invented observations, not a live catalogue.
- **Assumption.** Commission (12% of the shelf price: a typical marketplace
  take-rate, not a published fee from a named platform); landed cost of goods
  (50% of the ex-VAT price, including freight and duty); fulfilment £3.50 a unit;
  returns 10%; markdowns 8%; 80 days of stock, to reflect longer lead times when
  goods ship across a border; 40 weekly units at a £15 reference price, with
  elasticity 1; default weekly demand swing 30% (two gift and travel lines are
  set at 60% and 55%); diversion 25%; marketplace cost 50p a 3P sale; physical
  holding 8% of stock cost a year; return-on-stock hurdle 25%. Every one of these
  is editable in the sidebar.
- **Model estimate.** Weekly units from the price curve; 1P contribution, net 3P
  value, return on stock, and the recommendation itself.

## How the decision is made

In this order:

1. If weekly demand swings by more than 50% of the average, test as 3P first.
2. If 1P and 3P contribution are within 10% of each other, or return on stock is
   within 10% of the hurdle, test as 3P first.
3. If 1P makes more contribution per unit than net 3P, and return on stock beats
   the 25% hurdle, bring it in-house.
4. Otherwise keep it with the seller (3P).

Contribution per unit, own stock, is the ex-VAT price minus landed cost of goods,
fulfilment, returns, markdowns and physical holding. Net 3P is commission on the
shelf price, minus 50p cost to serve, minus diversion times the own-brand
substitute's 1P contribution (floored at zero). Return on stock is a year's 1P
contribution divided by average stock value (cost of goods × weekly units × days
of cover / 7).

The substitute is the median own-brand shelf price in the same subcategory
(charger, cable, power bank, and so on), not a single median for the whole
category. That keeps a cheap cable from being compared with a dear hub.

## Holding cost and the hurdle

Contribution only takes off the physical cost of holding stock (warehouse space,
insurance and shrink). The default is 8% of the cost of the goods for the days
they sit in stock. The cost of capital is not in that line. It is tested only by
the hurdle on return on stock. That stops the cost of money being counted twice.

The 8% and the 25% are both assumptions. Firms set their own hurdle, usually
their cost of capital plus a cushion for risk. There is a related retail
measure, GMROI (gross margin return on inventory investment). A Shopify article
updated on 18 July 2026, which I opened on 12 November 2026, calculated GMROI
from public filings: Best Buy 1.82, Home Depot 2.23, Ulta Beauty 2.36,
Abercrombie & Fitch 6.08. Shopify gives no single target. Source:
https://www.shopify.com/blog/gmroi

GMROI uses gross profit (sales less cost of goods only). This tool uses
contribution after fulfilment, returns, markdowns and physical holding. The
figures are not directly comparable, and no published GMROI number is used as
the hurdle.

## Limitations

- Every cost, volume, diversion rate and the hurdle is my judgement, not a
  measured figure from a marketplace.
- Weekly units come from a price curve with elasticity 1, so every listing in
  this sample gets the same estimated annual GMV. GMV is not used to rank.
- Two gift and travel lines have a higher demand swing by design, to show the
  volatility rule. That swing is an assumption, not observed seasonality.
- The 80-day stock cover and the 50% landed-cost share are a simple way to
  reflect cross-border lead times and import costs. A real firm would use
  actual lead times, duty rates and freight.
- The decision log does not persist on Streamlit Community Cloud. Download it
  if you want to keep it.
- This is a thinking tool, not production software and not a forecast.
