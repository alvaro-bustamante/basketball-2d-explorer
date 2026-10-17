"""Basketball 2D Explorer: compare any two metrics, with Bayesian uncertainty.

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from explorer import api, sources
from explorer.bayes import eb_beta_binomial, eb_normal, ellipse_path, ellipse_scale
from explorer.metrics import (PLAYER_METRICS, TEAM_METRICS, evaluate, player_totals,
                              team_totals)
from explorer.teams import chart_color

st.set_page_config(page_title="Basketball 2D Explorer", page_icon="🏀", layout="wide")

CURRENT_SEASON = 2026
SHRINK = {"prop": eb_beta_binomial, "normal": eb_normal}


def season_label(y: int) -> str:
    return f"{y}-{str(y + 1)[-2:]}"


@st.cache_data(ttl=3600, show_spinner="Loading official data…")
def load_api(code: str, season: int, phase: str | None):
    return sources.from_api(code, season, phase)


@st.cache_data
def load_demo():
    return sources.from_demo()


# --------------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("🏀 2D Explorer")
    source = st.radio("Data source", ["EuroLeague API", "EuroCup API", "Your CSV files", "Demo (fictional)"])
    if source.endswith("API"):
        season = st.selectbox("Season", list(range(CURRENT_SEASON, 2015, -1)), format_func=season_label)
        phase_name = st.selectbox("Phase", list(api.PHASES))
    elif source == "Your CSV files":
        st.caption("Any league (ACB, NBA, BCL…): fill in the templates and upload them.")
        st.download_button("Team template", sources.team_template(), "teams_template.csv", "text/csv")
        st.download_button("Player template", sources.player_template(), "players_template.csv", "text/csv")
        team_file = st.file_uploader("Team CSV", type="csv")
        player_file = st.file_uploader("Player CSV (optional)", type="csv")
    level = st.radio("Compare", ["Teams", "Players"], horizontal=True)

try:
    if source == "EuroLeague API":
        teams, opp, players = load_api("E", season, api.PHASES[phase_name])
        context = f"EuroLeague {season_label(season)}"
    elif source == "EuroCup API":
        teams, opp, players = load_api("U", season, api.PHASES[phase_name])
        context = f"EuroCup {season_label(season)}"
    elif source == "Your CSV files":
        if team_file is None:
            st.info("Upload a team CSV (download the template in the sidebar) to start.")
            st.stop()
        teams, opp, players = sources.from_csv(team_file, player_file)
        context = "Custom data"
    else:
        teams, opp, players = load_demo()
        context = "Demo data (fictional teams and players)"
except (api.EuroLeagueAPIError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

if teams is None or teams.empty:
    st.warning("No data for this selection yet. Try the previous season.")
    st.stop()

# ----------------------------------------------------------------- the frame
if level == "Teams":
    frame = team_totals(teams, opp)
    registry = TEAM_METRICS
    labels = frame.index.to_series()
    colors = [chart_color(c) for c in frame.index]
    hover_names = frame["name"]
else:
    if players is None or players.empty:
        st.warning("No player data for this source.")
        st.stop()
    frame = player_totals(players, teams)
    min_mpg = st.sidebar.slider("Min. minutes per game", 0, 30, 12)
    min_games = st.sidebar.slider("Min. games", 1, 40, 5)
    team_opts = sorted(frame["team_code"].unique())
    team_sel = st.sidebar.multiselect("Teams", team_opts, placeholder="All teams")
    frame = frame[(frame.min_pg >= min_mpg) & (frame.games >= min_games)]
    if team_sel:
        frame = frame[frame.team_code.isin(team_sel)]
    if len(frame) < 5:
        st.warning("Too few players with these filters.")
        st.stop()
    registry = PLAYER_METRICS
    labels = frame["name"].map(api.display_name)
    colors = [chart_color(c) for c in frame["team_code"]]
    hover_names = labels + " (" + frame["team_code"] + ")"

by_label = {m.label: m for m in registry}

# --------------------------------------------------------------- controls
st.title("Basketball 2D Explorer")
st.caption(f"{context} · season totals · uncertainty from an empirical-Bayes model")

c1, c2 = st.columns(2)
default_x, default_y = ("Offensive rating", "Defensive rating") if level == "Teams" else ("USG%", "TS%")
mx = by_label[c1.selectbox("X axis", list(by_label), index=list(by_label).index(default_x))]
my = by_label[c2.selectbox("Y axis", list(by_label), index=list(by_label).index(default_y))]
inv_x = c1.checkbox("Reverse X (better to the right)", value=mx.better == "low")
inv_y = c2.checkbox("Reverse Y (better at the top)", value=my.better == "low")

o1, o2, o3, o4 = st.columns(4)
estimate = o1.radio("Points show", ["Observed", "Bayes-adjusted"], horizontal=False)
level_ci = o2.select_slider("Uncertainty ellipses", options=["Off", "50%", "68%", "95%"], value="68%")
show_shift = o3.checkbox("Show shift observed → adjusted", value=False,
                         disabled=estimate == "Observed")
show_medians = o4.checkbox("League medians", value=True)
highlight = st.multiselect("Highlight", sorted(labels.unique()))
ellipses_for = "All" if level == "Teams" else st.radio(
    "Ellipses for", ["Highlighted only", "All"], horizontal=True)

# ------------------------------------------------------------------ compute
ex = evaluate(mx, frame, SHRINK)
ey = evaluate(my, frame, SHRINK)
col = "adjusted" if estimate == "Bayes-adjusted" else "observed"
x, y = ex[col], ey[col]
is_hl = labels.isin(highlight).to_numpy() if highlight else np.zeros(len(frame), bool)

# -------------------------------------------------------------------- figure
fig = go.Figure()
if level_ci != "Off":
    k = ellipse_scale(int(level_ci.rstrip("%")) / 100)
    for i in range(len(frame)):
        if ellipses_for == "Highlighted only" and not is_hl[i]:
            continue
        rx, ry = k * ex["sd"].iloc[i], k * ey["sd"].iloc[i]
        if not (np.isfinite(rx) and np.isfinite(ry)) or (rx == 0 and ry == 0):
            continue
        px_, py_ = ellipse_path(ex["adjusted"].iloc[i], ey["adjusted"].iloc[i], rx, ry)
        fig.add_trace(go.Scatter(x=px_, y=py_, mode="lines", fill="toself", hoverinfo="skip",
                                 line=dict(width=1, color=colors[i]), fillcolor=colors[i],
                                 opacity=0.18 if not is_hl[i] else 0.35, showlegend=False))
if show_shift and estimate == "Bayes-adjusted":
    for i in range(len(frame)):
        fig.add_trace(go.Scatter(x=[ex["observed"].iloc[i], ex["adjusted"].iloc[i]],
                                 y=[ey["observed"].iloc[i], ey["adjusted"].iloc[i]],
                                 mode="lines", line=dict(width=1, color="#888", dash="dot"),
                                 hoverinfo="skip", showlegend=False))
show_text = level == "Teams" or len(frame) <= 25
fig.add_trace(go.Scatter(
    x=x, y=y, mode="markers+text" if show_text else "markers",
    text=[lab if (show_text or h) else "" for lab, h in zip(labels, is_hl)],
    textposition="top center",
    marker=dict(size=[16 if h else 11 for h in is_hl], color=colors,
                line=dict(width=[2.5 if h else 1 for h in is_hl], color="#FFFFFF")),
    customdata=np.stack([ex["observed"], ex["adjusted"], ex["sd"],
                         ey["observed"], ey["adjusted"], ey["sd"]], axis=1),
    hovertext=hover_names,
    hovertemplate=("<b>%{hovertext}</b><br>"
                   f"{mx.label}: %{{customdata[0]:.1f}} (adj. %{{customdata[1]:.1f}} ± %{{customdata[2]:.1f}})<br>"
                   f"{my.label}: %{{customdata[3]:.1f}} (adj. %{{customdata[4]:.1f}} ± %{{customdata[5]:.1f}})"
                   "<extra></extra>"),
    showlegend=False))
if not show_text and highlight:
    sel = np.where(is_hl)[0]
    fig.add_trace(go.Scatter(x=x.iloc[sel], y=y.iloc[sel], mode="text", text=labels.iloc[sel],
                             textposition="top center", hoverinfo="skip", showlegend=False))
if show_medians:
    fig.add_vline(x=float(np.nanmedian(x)), line_dash="dot", line_color="#888")
    fig.add_hline(y=float(np.nanmedian(y)), line_dash="dot", line_color="#888")
fig.update_xaxes(title=mx.label, autorange="reversed" if inv_x else True)
fig.update_yaxes(title=my.label, autorange="reversed" if inv_y else True)
fig.update_layout(height=680, margin=dict(l=10, r=10, t=40, b=10),
                  title=f"{my.label} vs {mx.label}")
st.plotly_chart(fig)

# -------------------------------------------------------------------- table
z = 1.96
table = pd.DataFrame({
    "Name": labels.values,
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
    table.insert(1, "Team", frame["team_code"].values)
    table.insert(2, "MPG", frame["min_pg"].round(1).values)
st.dataframe(table, hide_index=True)
st.download_button("Download this view (CSV)", table.to_csv(index=False).encode(),
                   "explorer_view.csv", "text/csv")

with st.expander("Method: what the ellipses mean"):
    st.markdown(f"""
**Why adjust?** A player who shoots 8/10 from three has not proven he is an 80% shooter.
Small samples produce extreme values by chance. The app estimates each metric with an
**empirical-Bayes** model whose prior is the league itself:

* **Rates built from counts** (3P%, eFG%, TOV%, USG%…): Beta-Binomial model. The league
  average and the true spread between players are estimated from the data; each value is
  pulled towards the average in proportion to how few attempts it is based on.
* **Continuous metrics** (ratings, per-game stats): Normal-Normal model with an approximate
  standard error (e.g. ratings use an SD of {1.1} points per possession).

**Ellipses** show where the true value plausibly lies ({level_ci} credible region), assuming
the two metrics' errors are independent. **Overlapping ellipses = we cannot really tell
those two apart yet.**

{mx.label}: {mx.help or '—'}  ·  {my.label}: {my.help or '—'}
""")
st.caption("Built by Álvaro Bustamante-Sánchez, PhD · @dr.alvarobustamante")
