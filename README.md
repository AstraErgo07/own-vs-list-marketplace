# Own stock vs marketplace listing (1P vs 3P)

A decision-support prototype for a question many marketplaces face: should we
buy and stock a product ourselves (1P), leave it to a seller (3P), or test it
on the marketplace first?

It looks at one category, consumer electronics accessories, using made-up
example products. The calculations are plain Python rules. A person accepts or
overrides every recommendation. There is no chatbot.

This tests the method. It is not a forecast, and it is not a description of any
live marketplace.

Made by Ami Sata.

## What it compares

For each seller listing:

1. **Contribution per unit, own stock vs marketplace.** Own stock is the price
   without VAT, minus landed cost of goods (including freight and duty),
   delivery, returns, markdowns and the physical cost of holding stock.
   Marketplace value is commission on the shelf price, minus a cost to serve,
   minus the contribution lost when a buyer would otherwise have bought the
   own-brand substitute.
2. **Return on the stock you would hold.** A year's 1P contribution divided by
   the average value of stock. It has to beat a hurdle. The default hurdle is
   25%, which is an assumption: firms set their own bar (cost of capital plus a
   cushion for risk). It is editable, and a sensitivity table shows what
   happens at 50%, 100%, 150% and 200%.
3. **Demand volatility.** If weekly sales are assumed to swing by more than
   50% of the average, the answer is "test as 3P first", whatever the other
   two say. If either money test lands within 10% of its threshold, the answer
   is "test first" too.

The cost of capital is not subtracted from contribution. It is tested only by
the hurdle. That avoids counting the cost of money twice. The method page and
an expander in the app explain the split.

Every input is labelled Published, Observed in sample, Assumption or Model
estimate.

## The sample

28 invented products: 18 seller listings and 10 own-brand substitutes.
Nothing was collected from a live site. Costs, volumes and the hurdle are
labelled assumptions that you can edit.

The Insights section reports only what the model shows at the default
assumptions, worded as findings in this sample under those assumptions.

## Run it locally

Python 3.12 or newer. From the repo root:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Tests

From the `own_vs_list` folder:

```
python3 -m unittest
```

From the repo root:

```
python3 smoke_test_app.py
```

## Deploy on Streamlit Community Cloud

- Repository: this repo
- Branch: `main`
- Main file: `streamlit_app.py`
- Python version: 3.12 (Advanced settings)

This repository is not deployed from here. After you deploy it, the live link
is yours to share.

## Requirements

- `streamlit==1.67.0`
- `pandas==3.1.1`

## Licence of the idea

Independent portfolio project. Made by Ami Sata.
