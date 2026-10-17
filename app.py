"""Basketball 2D Explorer: compare any two metrics, with Bayesian uncertainty.

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from explorer import api, sources
from explorer.annotate import leaders, leaders_html, quadrant_html, quadrant_labels
from explorer.bayes import eb_beta_binomial, eb_normal, ellipse_path, ellipse_scale
from explorer.metrics import (PLAYER_METRICS, TEAM_METRICS, evaluate, player_totals,
                              team_totals)
from explorer.teams import chart_color, short_name

# ─── PERSONAL EXPORT HOOK ─────────────────────────────────────────────────────
# Story / LinkedIn image export lives in personal/ (excluded from GitHub by
# .gitignore). Set to False (or delete personal/) to hide it. If the folder is
# missing, as in the public repository, the app simply skips this feature.
SOCIAL_EXPORT = True
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Basketball 2D Explorer", page_icon="🏀", layout="wide")

CURRENT_SEASON = 2026
SHRINK = {"prop": eb_beta_binomial, "normal": eb_normal}
SMALL = 10  # font size for all secondary text on the chart


def season_label(y: int) -> str:
    return f"{y}-{str(y + 1)[-2:]}"


@st.cache_data(ttl=3600, show_spinner="Loading official data…")
def load_api(code: str, season: int, phase: str | None):
    return sources.from_api(code, season, phase)


@st.cache_data(ttl=6 * 3600, show_spinner="Loading NBA data (stats.nba.com)…")
def load_nba(season: int, season_type: str):
    from explorer import nba
    return nba.load_season(season, season_type)


@st.cache_data
def load_demo():
    return sources.from_demo()


# ───────────────────────────────────────────────────────────────── sidebar: data
with st.sidebar:
    st.title("🏀 2D Explorer")
    source = st.radio("Data source", ["EuroLeague API", "EuroCup API", "NBA (stats.nba.com)",
                                      "Your CSV files", "Demo (fictional)"])
    league, game_length = "EUROLEAGUE", 40
    if source in ("EuroLeague API", "EuroCup API", "NBA (stats.nba.com)"):
        season = st.selectbox("Season", list(range(CURRENT_SEASON, 2015, -1)), format_func=season_label)
    if source in ("EuroLeague API", "EuroCup API"):
        phase_name = st.selectbox("Phase", list(api.PHASES))
    if source == "NBA (stats.nba.com)":
        league, game_length = "NBA", 48
        season_type = st.selectbox("Season type", ["Regular Season", "Playoffs"])
    if source == "Your CSV files":
        st.caption("Any league (ACB, NBA, BCL…): fill in the templates and upload them.")
        st.download_button("Team template", sources.team_template(), "teams_template.csv", "text/csv")
        st.download_button("Player template", sources.player_template(), "players_template.csv", "text/csv")
        team_file = st.file_uploader("Team CSV", type="csv")
        player_file = st.file_uploader("Player CSV (optional)", type="csv")
        league = st.selectbox("League (names and colors)", ["ACB", "NBA", "EUROLEAGUE", "CUSTOM"])
        game_length = 48 if league == "NBA" else 40
    if source == "EuroCup API":
        league = "EUROCUP"
    if source.startswith("Demo"):
        league = "DEMO"
    level = st.radio("Compare", ["Teams", "Players"], horizontal=True)

# ─────────────────────────────────────────────────────────────────── load data
try:
    if source == "EuroLeague API":
        teams, opp, players = load_api("E", season, api.PHASES[phase_name])
        context = f"EuroLeague {season_label(season)}"
    elif source == "EuroCup API":
        teams, opp, players = load_api("U", season, api.PHASES[phase_name])
        context = f"EuroCup {season_label(season)}"
    elif source == "NBA (stats.nba.com)":
        teams, opp, players = load_nba(season, season_type)
        context = f"NBA {season_label(season)} · {season_type}"
    elif source == "Your CSV files":
        if team_file is None:
            st.info("Upload a team CSV (download the template in the sidebar) to start.")
            st.stop()
        teams, opp, players = sources.from_csv(team_file, player_file)
        context = f"{league.title()} · custom data"
    else:
        teams, opp, players = load_demo()
        context = "Demo data (fictional teams and players)"
except Exception as exc:  # API errors, blocked NBA requests, malformed CSV
    st.error(str(exc))
    st.stop()

if teams is None or teams.empty:
    st.warning("No data for this selection yet. Try the previous season.")
    st.stop()

# ───────────────────────────────────────────────────────── build the frame
if level == "Teams":
    frame = team_totals(teams, opp, game_length=game_length)
    registry = TEAM_METRICS
    codes = frame.index.to_series()
    full_names = frame["name"].astype(str)
    short_names = pd.Series([short_name(c, n, league) for c, n in zip(codes, full_names)], index=frame.index)
    crest_urls = frame["crest_url"]
    colors = [chart_color(c, league) for c in codes]
else:
    if players is None or players.empty:
        st.warning("No player data for this source.")
        st.stop()
    frame = player_totals(players, teams)
    with st.sidebar:
        min_mpg = st.slider("Min. minutes per game", 0, 30, 12)
        min_games = st.slider("Min. games", 1, 40, 5)
        team_sel = st.multiselect("Teams", sorted(frame["team_code"].unique()), placeholder="All teams")
    frame = frame[(frame.min_pg >= min_mpg) & (frame.games >= min_games)]
    if team_sel:
        frame = frame[frame.team_code.isin(team_sel)]
    if len(frame) < 5:
        st.warning("Too few players with these filters.")
        st.stop()
    registry = PLAYER_METRICS
    full_names = frame["name"].map(lambda n: str(n).title() if "," not in str(n)
                                   else " ".join(reversed([p.strip().title() for p in str(n).split(",", 1)])))
    short_names = frame["name"].map(api.display_name)
    codes = frame["team_code"]
    crest_urls = pd.Series(None, index=frame.index)
    colors = [chart_color(c, league) for c in codes]

# Keep only metrics that have data in this source (e.g. no PIR in the NBA).
registry = [m for m in registry if np.isfinite(evaluate(m, frame, SHRINK)["observed"]).any()]
by_label = {m.label: m for m in registry}

# ──────────────────────────────────────────────────────── sidebar: display
with st.sidebar:
    st.divider()
    st.subheader("Display")
    if level == "Teams":
        label_mode = st.radio("Team labels", ["Short name", "Full name", "Code", "Crest", "None"])
    else:
        label_mode = st.radio("Player labels", ["Short name", "Full name", "None"])
    show_ellipses = st.toggle("Uncertainty ellipses", value=True)
    ci_level = st.select_slider("Credible level", options=["50%", "68%", "95%"], value="68%",
                                disabled=not show_ellipses)
    estimate = st.radio("Points show", ["Observed", "Bayes-adjusted"], horizontal=True)
    show_shift = st.checkbox("Arrow observed → adjusted", value=False, disabled=estimate == "Observed")
    show_medians = st.checkbox("League medians", value=True)
    show_quadrants = st.checkbox("Quadrant legend", value=True)
    show_leaders = st.checkbox("Top 3 / bottom 3", value=True)

labels = {"Short name": short_names, "Full name": full_names, "Code": codes,
          "Crest": short_names, "None": short_names}[label_mode]

# ───────────────────────────────────────────────────────────────── controls
st.title("Basketball 2D Explorer")
st.caption(f"{context} · season totals · uncertainty from an empirical-Bayes model")

c1, c2 = st.columns(2)
default_x, default_y = ("Offensive rating", "Defensive rating") if level == "Teams" else ("USG%", "TS%")
default_x = default_x if default_x in by_label else list(by_label)[0]
default_y = default_y if default_y in by_label else list(by_label)[1]
mx = by_label[c1.selectbox("X axis", list(by_label), index=list(by_label).index(default_x))]
my = by_label[c2.selectbox("Y axis", list(by_label), index=list(by_label).index(default_y))]
inv_x = c1.checkbox("Reverse X (better to the right)", value=mx.better == "low")
inv_y = c2.checkbox("Reverse Y (better at the top)", value=my.better == "low")
highlight = st.multiselect("Highlight", sorted(labels.unique()))

# ──────────────────────────────────────────────────────────────────── compute
ex = evaluate(mx, frame, SHRINK)
ey = evaluate(my, frame, SHRINK)
col = "adjusted" if estimate == "Bayes-adjusted" else "observed"
x, y = ex[col], ey[col]
is_hl = labels.isin(highlight).to_numpy() if highlight else np.zeros(len(frame), bool)
k = ellipse_scale(int(ci_level.rstrip("%")) / 100)
ellipse_all = level == "Teams" or not highlight
quads = quadrant_labels(mx, my, inv_x, inv_y)
board_names = labels if label_mode not in ("Crest", "None") else short_names
boards = [leaders(vals, board_names, m) for m, vals in ((mx, x), (my, y))] if show_leaders else []

# ───────────────────────────────────────────────────────────────────── figure
fig = go.Figure()
ellipses = []
if show_ellipses:
    for i in range(len(frame)):
        if not ellipse_all and not is_hl[i]:
            continue
        rx, ry = k * ex["sd"].iloc[i], k * ey["sd"].iloc[i]
        if not (np.isfinite(rx) and np.isfinite(ry)) or (rx == 0 and ry == 0):
            continue
        cx, cy = ex["adjusted"].iloc[i], ey["adjusted"].iloc[i]
        ellipses.append((cx, cy, rx, ry, colors[i]))
        px_, py_ = ellipse_path(cx, cy, rx, ry)
        fig.add_trace(go.Scatter(x=px_, y=py_, mode="lines", fill="toself", hoverinfo="skip",
                                 line=dict(width=1, color=colors[i]), fillcolor=colors[i],
                                 opacity=0.35 if is_hl[i] else 0.16, showlegend=False))
if show_shift and estimate == "Bayes-adjusted":
    for i in range(len(frame)):
        fig.add_annotation(x=ex["adjusted"].iloc[i], y=ey["adjusted"].iloc[i],
                           ax=ex["observed"].iloc[i], ay=ey["observed"].iloc[i],
                           xref="x", yref="y", axref="x", ayref="y", text="", showarrow=True,
                           arrowhead=2, arrowsize=0.8, arrowwidth=1, arrowcolor="#888")

use_crests = label_mode == "Crest" and crest_urls.notna().any()
show_text = label_mode not in ("None", "Crest") and (level == "Teams" or len(frame) <= 25)
text = [lab if (show_text or h) else "" for lab, h in zip(labels, is_hl)]
fig.add_trace(go.Scatter(
    x=x, y=y, mode="markers+text", text=text, textposition="top center",
    textfont=dict(size=11),
    marker=dict(size=[16 if h else 11 for h in is_hl], color=colors,
                opacity=0 if use_crests else 1,
                line=dict(width=[2.5 if h else 1 for h in is_hl], color="#FFFFFF")),
    customdata=np.stack([ex["observed"], ex["adjusted"], ex["sd"],
                         ey["observed"], ey["adjusted"], ey["sd"]], axis=1),
    hovertext=full_names, showlegend=False,
    hovertemplate=("<b>%{hovertext}</b><br>"
                   f"{mx.label}: %{{customdata[0]:.1f}} (adj. %{{customdata[1]:.1f}} ± %{{customdata[2]:.1f}})<br>"
                   f"{my.label}: %{{customdata[3]:.1f}} (adj. %{{customdata[4]:.1f}} ± %{{customdata[5]:.1f}})"
                   "<extra></extra>")))

if use_crests:
    xr = float(np.nanmax(x) - np.nanmin(x)) or 1.0
    yr = float(np.nanmax(y) - np.nanmin(y)) or 1.0
    for xi, yi, url, h in zip(x, y, crest_urls, is_hl):
        if isinstance(url, str) and url:
            s = 1.35 if h else 1.0
            fig.add_layout_image(source=url, x=xi, y=yi, xref="x", yref="y",
                                 sizex=0.07 * xr * s, sizey=0.07 * yr * s,
                                 xanchor="center", yanchor="middle", layer="above")

if show_medians:
    fig.add_vline(x=float(np.nanmedian(x)), line_dash="dot", line_color="#888")
    fig.add_hline(y=float(np.nanmedian(y)), line_dash="dot", line_color="#888")

if show_quadrants:
    for key, lines in quads.items():
        vert, horiz = key.split("_")
        fig.add_annotation(xref="paper", yref="paper", showarrow=False, align="left" if horiz == "left" else "right",
                           x=0.005 if horiz == "left" else 0.995, y=0.995 if vert == "top" else 0.005,
                           xanchor=horiz, yanchor=vert, text=quadrant_html(lines),
                           font=dict(size=SMALL), bgcolor="rgba(128,128,128,0.08)")

bottom_margin = 40
if boards:
    for j, board in enumerate(boards):
        fig.add_annotation(xref="paper", yref="paper", showarrow=False, align="left",
                           x=0, y=-0.11 - 0.075 * j, xanchor="left", yanchor="top",
                           text=leaders_html(board), font=dict(size=SMALL))
    bottom_margin = 150

fig.update_xaxes(title=mx.label, autorange="reversed" if inv_x else True)
fig.update_yaxes(title=my.label, autorange="reversed" if inv_y else True)
fig.update_layout(height=720, margin=dict(l=10, r=10, t=40, b=bottom_margin),
                  title=f"{my.label} vs {mx.label}")
st.plotly_chart(fig)

# ──────────────────────────────────────────────────────────────────────── table
z = 1.96
table = pd.DataFrame({
    "Name": full_names.values,
    f"{mx.label}": ex["observed"].round(1).values,
    f"{mx.label} adj.": ex["adjusted"].round(1).values,
    f"{mx.label} 95% CI": [f"{a - z * s:.1f} – {a + z * s:.1f}" if s > 0 else ""
                           for a, s in zip(ex["adjusted"], ex["sd"])],
    f"{my.label}": ey["observed"].round(1).values,
    f"{my.label} adj.": ey["adjusted"].round(1).values,
    f"{my.label} 95% CI": [f"{a - z * s:.1f} – {a + z * s:.1f}" if s > 0 else ""
                           for a, s in zip(ey["adjusted"], ey["sd"])],
})
if level == "Players":
    table.insert(1, "Team", codes.values)
    table.insert(2, "MPG", frame["min_pg"].round(1).values)
st.dataframe(table, hide_index=True)
st.download_button("Download this view (CSV)", table.to_csv(index=False).encode(),
                   "explorer_view.csv", "text/csv")

with st.expander("Method: what the ellipses mean"):
    st.markdown(f"""
**Why adjust?** A player who shoots 8/10 from three has not proven he is an 80% shooter.
Small samples produce extreme values by chance. The app estimates each metric with an
**empirical-Bayes** model whose prior is the league itself:

* **Rates built from counts** (3P%, eFG%, TOV%, USG%…): Beta-Binomial model.
* **Continuous metrics** (ratings, per-game stats): Normal-Normal model with an approximate
  standard error (ratings use an SD of 1.1 points per possession).

**Ellipses** show where the true value plausibly lies ({ci_level} credible region), assuming
independent errors on both axes. **Overlapping ellipses = the data cannot separate them yet.**

{mx.label}: {mx.help or '—'}  ·  {my.label}: {my.help or '—'}
""")
st.caption("Built by Álvaro Bustamante-Sánchez, PhD")

# ─── PERSONAL EXPORT (see hook at the top) ────────────────────────────────────
if SOCIAL_EXPORT:
    try:
        from personal.social_export import social_export_panel
    except ImportError:
        social_export_panel = None
    if social_export_panel is not None:
        social_export_panel({
            "title": f"{my.label} vs {mx.label}", "context": context, "level": level,
            "x_label": mx.label, "y_label": my.label, "inv_x": inv_x, "inv_y": inv_y,
            "x": np.asarray(x, float), "y": np.asarray(y, float),
            "labels": list(labels if label_mode != "None" else short_names),
            "show_labels": label_mode != "None", "highlight": list(is_hl),
            "colors": colors, "crest_urls": list(crest_urls) if label_mode == "Crest" else None,
            "ellipses": ellipses, "medians": (float(np.nanmedian(x)), float(np.nanmedian(y))) if show_medians else None,
            "quadrants": quads if show_quadrants else None, "leaders": boards,
            "estimate": estimate, "ci_level": ci_level if show_ellipses else None,
        })
