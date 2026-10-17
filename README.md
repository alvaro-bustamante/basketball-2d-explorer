# Basketball 2D Explorer

Compare **any two basketball metrics** for teams or players, and see **how much of
each difference is real** thanks to Bayesian uncertainty ellipses.

Built with Streamlit · Data: official EuroLeague/EuroCup API, or your own CSV (ACB, NBA, any league).

## Why

Most dashboards plot raw numbers. But a player shooting 8/10 from three is not an 80%
shooter, and two teams one point apart in offensive rating may be indistinguishable.
This app shows both the observed value and an **adjusted estimate with its uncertainty**,
so you can tell signal from noise before making a decision.

## Features

- Teams or players, any metric on either axis: ratings, pace, Four Factors, shooting splits,
  usage, assist rate, per-game and per-40 production.
- **Observed vs Bayes-adjusted** values, with an optional arrow showing the shrinkage.
- **Credible ellipses** (50 / 68 / 95%): overlapping ellipses mean the data cannot yet
  separate those two entities.
- League medians, reversible axes ("better" always up/right), highlights, filters.
- Table with 95% credible intervals and CSV export.
- Sources: EuroLeague and EuroCup official API, your own CSV templates, or demo data.

## Method

Empirical-Bayes models with a league-estimated prior:

| Metric type | Model | Uncertainty input |
|---|---|---|
| Rates from counts (3P%, eFG%, TOV%, USG%, AST%…) | Beta-Binomial | makes / attempts (or events / opportunities) |
| Ratings and per-game stats | Normal-Normal | approximate standard error (e.g. SD ≈ 1.1 points per possession) |

The prior mean and the true between-entity spread are estimated by the method of moments
(observed variance minus the variance expected from sampling noise, with a floor of 20% of
the observed variance to avoid complete pooling). Ellipses assume independent errors on
both axes and use the closed-form 2-D Gaussian radius `sqrt(-2 ln(1 - level))`.

**Validation (simulation, 400 leagues × 250 players):** the 95% intervals for 3P% contained
the true value **95.1%** of the time, and the adjusted estimate cut the error versus raw 3P%
from **4.3 to 1.5 percentage points**.

Next step: a full hierarchical model in PyMC (correlated metrics, player age and role as
covariates) with the same inputs and outputs (`explorer/bayes.py`).

## Run it locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Project structure

```
app.py                 Streamlit interface
explorer/api.py        EuroLeague/EuroCup API client and column normalization
explorer/sources.py    API, CSV templates and demo data
explorer/metrics.py    metric registry: formulas and uncertainty inputs
explorer/bayes.py      empirical-Bayes shrinkage and ellipses
explorer/teams.py      team colors
explorer/demo.py       fictional demo data
```

## Data notes

EuroLeague data comes from the league's public API and is used for non-commercial analysis.
No private or club data is included in this repository.

## Author

**Álvaro Bustamante-Sánchez, PhD** · Associate Professor and Head of the Applied Technology
& Research Lab, Universidad Europea de Madrid ·
[LinkedIn](https://www.linkedin.com/in/alvaro-bustamante-163b5655) ·
[Google Scholar](https://scholar.google.com/citations?user=e_gK-2YAAAAJ)

MIT License.
