# Basketball 2D Explorer

Compare **any two basketball metrics** for teams or players, and see **how much of
each difference is real** thanks to Bayesian uncertainty ellipses.
Interface in **English and Spanish** (selector at the top of the sidebar).
**Men's and women's competitions** in the same app (Men / Women switch): EuroLeague, EuroCup, NBA, ACB,
Primera and Segunda FEB, Basketball Champions League, FIBA Europe Cup; WNBA, LF Endesa and EuroLeague Women.
FIBA competitions (and national-team events such as EuroBasket) are read from the public FIBA game pages
with a local script; their box scores are rebuilt from the play-by-play and checked against the final score.

Built with Streamlit · Data: official EuroLeague/EuroCup API, NBA (stats.nba.com), or your own files (ACB, Primera FEB, any league).

## Why

Most dashboards plot raw numbers. But a player shooting 8/10 from three is not an 80%
shooter, and two teams one point apart in offensive rating may be indistinguishable.
This app shows both the observed value and an **adjusted estimate with its uncertainty**,
so you can tell signal from noise before making a decision.

## Features

- Teams or players, any metric on either axis: ratings, pace, Four Factors, shooting splits,
  TS%, eFG%, PPS, FTA rate, ORB% / DRB% / TRB%, AST%, STL%, BLK%, TOV%, USG%, AST/TOV, Game Score,
  per-game and per-40 production.
- **Shape-of-play metrics**: ball movement (assisted share of made shots), HOB (hands on ball:
  share of the team's made shots a player scored or assisted), **shot diet entropy** (how evenly
  scoring chances are spread across 2-point, 3-point and free-throw trips, no shot coordinates
  needed) and **scoring balance entropy** (how evenly shots are spread across the roster). Both
  entropies are normalized to 0–1 and come with a Dirichlet posterior standard error.
- Names, codes, team crests or player photos as labels.
- Self-explanatory quadrant badges (▲ GOOD / ▼ BAD) and top-3 / bottom-3 boards for each axis.
- Automatic round label ("ROUND 12") from the games played.
- **Observed vs Bayes-adjusted** values, with an optional arrow showing the shrinkage.
- **Credible ellipses** (50 / 68 / 95%) for every team or player, or only the ones you choose:
  overlapping ellipses mean the data cannot yet separate those two entities.
- League medians, reversible axes ("better" always up/right), highlights, filters.
- Table with 95% credible intervals and CSV export.
- Sources: EuroLeague and EuroCup official API, NBA via `nba_api`, your own files, or demo data.

## Leagues without an API (ACB, Primera FEB…)

**From a warehouse.** The app reads ACB, FEB and FIBA competitions from the per-game tables of a
hoops-warehouse folder (`<comp>_<season>_team_games.csv` and
`_player_games.csv`). It looks for it next to this project (`../hoops-warehouse/data/warehouse`),
or in the folder given by the environment variable `HOOPS_WAREHOUSE` or by `warehouse_dir` in
`.streamlit/secrets.toml`. This app does not download anything from those leagues itself.

**From your own files.** `explorer/spanish.py` reads stats tables you save yourself or that a club provides:
an HTML page saved from the browser, Excel or CSV, with Spanish headers (PJ, MIN, PTS, T2, T3,
TL, RO, RD, AS, BR, BP, TAP, FC, VAL) or English ones. Two layouts:

1. **Season tables**: each team's own stats plus its opponents' stats ("rivales").
2. **Team game log**: one row per team and game with a game id; opponent stats are derived
   automatically.

Load them directly in the app ("Your files"), or convert them once:

```bash
python pipelines/import_spanish_stats.py --league acb --teams equipos.html --opponents rivales.html
python pipelines/import_spanish_stats.py --league primera-feb --gamelog partidos.xlsx
```

**Shot format.** Templates store shots as **made and missed** (`fg2m`, `fg2x`, `fg3m`, `fg3x`,
`ftm`, `ftx`): mutually exclusive events, as observational methodology requires. Attempts are
derived only where a metric needs them (TS%, eFG%, FTA rate). Files with attempts (`fg2a`…)
are still accepted.

**Photos.** Downloaded photos are kept in `data/cache/images/` (originals, never re-downloaded);
the face crop is computed when the app starts. If a crop is not right, save your own square crop as
`data/faces/<first-last>.png` (e.g. `data/faces/sergio-llull.png`): the app uses it as it is.

Optional columns `crest_url` and `photo_url` add crests and player photos. CSV files placed in
`data/` as `<name>_teams.csv` / `<name>_players.csv` appear in the app under
"Your files" > "Saved in data/ folder".


## Method

Empirical-Bayes models with a league-estimated prior:

| Metric type | Model | Uncertainty input |
|---|---|---|
| Rates from counts (3P%, eFG%, TOV%, USG%, AST%…) | Beta-Binomial | makes / attempts (or events / opportunities) |
| Shot diet / scoring balance entropy | Dirichlet-multinomial → Normal-Normal | posterior SD of the normalized entropy |
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
explorer/teams.py      team names and colors (EuroLeague, NBA, ACB by name)
explorer/annotate.py   quadrant badges, leaderboards, round label
explorer/spanish.py    importer for ACB / FEB tables and game logs
explorer/nba.py        NBA data through nba_api
pipelines/             command-line exports and imports
explorer/demo.py       fictional demo data
```

## Data notes

EuroLeague data comes from the league's public API and is used for non-commercial analysis.
NBA data comes from stats.nba.com through `nba_api` (works locally; often blocked from cloud
servers). No private or club data is included in this repository: keep your files in `data/`,
which is git-ignored.

## Author

**Álvaro Bustamante-Sánchez, PhD** · Head of the Applied Technology & Research Lab ·
[LinkedIn](https://www.linkedin.com/in/alvaro-bustamante-163b5655) ·
[Google Scholar](https://scholar.google.com/citations?user=e_gK-2YAAAAJ)

MIT License.
