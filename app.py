"""Basketball 2D Explorer: compare any two metrics, with Bayesian uncertainty.

Run locally:   streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from explorer import api, sources, spanish
from explorer.annotate import BADGE_FONT, badge_fill, leaders, leaders_html
from explorer.i18n import LANGS, set_lang, smart_upper, t, th, tm
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
# Condensed sports font for the quadrant badges (falls back to system fonts).
st.markdown('<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700'
            '&display=swap" rel="stylesheet">', unsafe_allow_html=True)

CURRENT_SEASON = 2026
SHRINK = {"prop": eb_beta_binomial, "normal": eb_normal}
SMALL = 10  # font size for all secondary text on the chart
DATA_DIR = Path("data")
# Leagues without a public API: read from data/<prefix>_<season>_teams.csv (and _players.csv).
LOCAL_LEAGUES = {"Liga Endesa ACB": ("ACB", "acb"), "Primera FEB": ("PRIMERA FEB", "primerafeb")}


def season_label(y: int) -> str:
    return f"{y}-{str(y + 1)[-2:]}"


@st.cache_data(ttl=3600, show_spinner="Loading official data…")
def load_api(code: str, season: int, phase: str | None):
    return sources.from_api(code, season, phase)


@st.cache_data(ttl=6 * 3600, show_spinner="Loading NBA data (stats.nba.com)…")
def load_nba(season: int, season_type: str):
    from explorer import nba
    return nba.load_season(season, season_type)


@st.cache_data(show_spinner=False)
def prepared_images(urls: tuple, kind: str, version: int = 0) -> dict:
    """URL -> image ready to draw (data URI): photos cropped to the face, crests whole.
    Downloads are cached in data/cache/images/. Images that fail map to None."""
    from concurrent.futures import ThreadPoolExecutor
    from explorer.images import prepare
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(urls, pool.map(lambda u: prepare(u, kind), urls)))


@st.cache_data
def load_demo():
    return sources.from_demo()


# ───────────────────────────────────────────────────────────────── sidebar: data
with st.sidebar:
    set_lang(LANGS[st.selectbox("🌐 Language / Idioma", list(LANGS))])
    st.title("🏀 2D Explorer")
    SOURCES = {"src_el": "EuroLeague API", "src_ec": "EuroCup API", "src_nba": "NBA (stats.nba.com)",
               "src_acb": "Liga Endesa ACB", "src_feb": "Primera FEB", "src_files": "Your files (any league)",
               "src_demo": "Demo (fictional)"}
    source = SOURCES[st.radio(t("data_source"), list(SOURCES), format_func=t)]
    league, game_length = "EUROLEAGUE", 40
    if source in LOCAL_LEAGUES:
        league, prefix = LOCAL_LEAGUES[source]
        local_seasons = sorted({int(f.name.split("_")[-2]) for f in DATA_DIR.glob(f"{prefix}_*_teams.csv")
                                if f.name.split("_")[-2].isdigit()}, reverse=True) if DATA_DIR.exists() else []
        if local_seasons:
            season = st.selectbox(t("season"), local_seasons, format_func=season_label)
    if source in ("EuroLeague API", "EuroCup API", "NBA (stats.nba.com)"):
        season = st.selectbox(t("season"), list(range(CURRENT_SEASON, 2015, -1)), format_func=season_label)
    if source in ("EuroLeague API", "EuroCup API"):
        phase_name = st.selectbox(t("phase"), list(api.PHASES))
    if source == "NBA (stats.nba.com)":
        league, game_length = "NBA", 48
        season_type = st.selectbox(t("season_type"), ["Regular Season", "Playoffs"])
    if source.startswith("Your files"):
        league = st.selectbox(t("league_names"), ["ACB", "PRIMERA FEB", "NBA", "EUROLEAGUE", "CUSTOM"])
        game_length = 48 if league == "NBA" else 40
        data_dir = DATA_DIR
        saved = sorted(f.name[:-len("_teams.csv")] for f in data_dir.glob("*_teams.csv")) if data_dir.exists() else []
        FORMATS = {"ff_saved": "Saved in data/ folder", "ff_template": "App template (CSV)",
                   "ff_tables": "Season tables (Spanish or English)", "ff_log": "Team game log"}
        file_format = FORMATS[st.radio(t("file_format"), (["ff_saved"] if saved else [])
                                       + ["ff_template", "ff_tables", "ff_log"], format_func=t, help=t("ff_help"))]
        kinds = ["csv", "html", "htm", "xlsx", "xls"]
        if file_format == "Saved in data/ folder":
            dataset = st.selectbox(t("dataset"), saved, help=t("dataset_help"))
            team_file = data_dir / f"{dataset}_teams.csv"
            opp_file = None
        elif file_format == "App template (CSV)":
            st.caption(t("template_note"))
            st.download_button(t("team_template"), sources.team_template(), "teams_template.csv", "text/csv")
            st.download_button(t("player_template"), sources.player_template(), "players_template.csv", "text/csv")
            team_file = st.file_uploader(t("team_csv"), type="csv")
            opp_file = None
        elif file_format.startswith("Season tables"):
            team_file = st.file_uploader(t("team_own"), type=kinds)
            opp_file = st.file_uploader(t("team_opp"), type=kinds)
            values_kind = "Season totals" if st.radio(t("values_are"), ["averages", "totals"], horizontal=True,
                                                      format_func=t) == "totals" else "Per-game averages"
        else:
            team_file = st.file_uploader(t("game_log"), type=kinds)
            opp_file = None
        if file_format == "Saved in data/ folder":
            player_file = data_dir / f"{dataset}_players.csv"
            player_file = player_file if player_file.exists() else None
        else:
            player_file = st.file_uploader(t("player_stats"), type=kinds)
    if source == "EuroCup API":
        league = "EUROCUP"
    if source.startswith("Demo"):
        league = "DEMO"
    level = "Teams" if st.radio(t("compare"), ["teams", "players"], horizontal=True, format_func=t) == "teams" \
        else "Players"

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
    elif source in LOCAL_LEAGUES:
        if not local_seasons:
            how = (f"`python personal/scrape_league.py {prefix if prefix == 'acb' else 'feb'} --season 2026`"
                   if Path("personal/scrape_league.py").exists()
                   else "`python pipelines/import_spanish_stats.py` (see the README)")
            st.info(t("no_local", source=source, how=how))
            st.stop()
        players_path = DATA_DIR / f"{prefix}_{season}_players.csv"
        teams, opp, players = sources.from_csv(DATA_DIR / f"{prefix}_{season}_teams.csv",
                                               players_path if players_path.exists() else None)
        context = f"{source} {season_label(season)}"
    elif source.startswith("Your files"):
        if team_file is None or (file_format.startswith("Season tables") and opp_file is None):
            st.info(t("upload_first"))
            st.stop()
        if file_format in ("App template (CSV)", "Saved in data/ folder"):
            teams, opp, players = sources.from_csv(team_file, player_file)
        elif file_format.startswith("Season tables"):
            teams, opp, players = spanish.from_season_tables(
                team_file, opp_file, player_file,
                values="totals" if values_kind == "Season totals" else "averages")
        else:
            teams, opp, players = spanish.from_game_log(team_file, player_file)
        context = {"ACB": "Liga Endesa ACB", "PRIMERA FEB": "Primera FEB"}.get(league, league.title())
        if file_format == "Saved in data/ folder" and dataset.split("_")[-1].isdigit():
            context += f" {season_label(int(dataset.split('_')[-1]))}"
    else:
        teams, opp, players = load_demo()
        context = t("demo_context")
except Exception as exc:  # API errors, blocked NBA requests, malformed CSV
    st.error(str(exc))
    st.stop()

if teams is None or teams.empty:
    st.warning(t("no_data"))
    st.stop()

# Round reached in this competition: the most games played by any team.
games_played = int(np.nanmax(pd.to_numeric(teams["games"], errors="coerce")))
phase_code = api.PHASES.get(phase_name) if source in ("EuroLeague API", "EuroCup API") else None
playoffs = phase_code == "PO" or (source == "NBA (stats.nba.com)" and season_type == "Playoffs")
auto_round = ("" if not games_played else t("playoffs") if playoffs
              else f"{t('game_word') if league == 'NBA' else t('round_word')} {games_played}")

# ───────────────────────────────────────────────────────── build the frame
if level == "Teams":
    frame = team_totals(teams, opp, game_length=game_length, players=players)
    registry = TEAM_METRICS
    codes = frame.index.to_series()
    full_names = frame["name"].astype(str)
    short_names = pd.Series([short_name(c, n, league) for c, n in zip(codes, full_names)], index=frame.index)
    crest_urls = frame["crest_url"]
    photo_urls = pd.Series(None, index=frame.index)
    colors = [chart_color(c, league, n) for c, n in zip(codes, full_names)]
else:
    if players is None or players.empty:
        st.warning(t("no_players"))
        st.stop()
    frame = player_totals(players, teams, opp)
    max_games = max(int(np.nanmax(frame["games"])), 1)
    max_mpg = max(int(np.ceil(np.nanmax(frame["min_pg"]))), 1)
    with st.sidebar:
        min_mpg = st.slider(t("min_mpg"), 0, max_mpg, min(12, max_mpg))
        min_games = st.slider(t("min_games"), 1, max_games, min(5, max_games),
                              help=t("min_games_help", n=max_games))
        team_names = dict(zip(teams["team_code"], teams["team_name"]))
        team_sel = st.multiselect(t("teams_filter"), sorted(frame["team_code"].dropna().unique()),
                                  placeholder=t("all_teams"),
                                  format_func=lambda c: short_name(c, team_names.get(c, c), league))
    frame = frame[(frame.min_pg >= min_mpg) & (frame.games >= min_games)]
    if team_sel:
        frame = frame[frame.team_code.isin(team_sel)]
    if len(frame) < 5:
        st.warning(t("too_few"))
        st.stop()
    registry = PLAYER_METRICS
    full_names = frame["name"].map(lambda n: str(n).title() if "," not in str(n)
                                   else " ".join(reversed([p.strip().title() for p in str(n).split(",", 1)])))
    short_names = frame["name"].map(api.display_name)
    codes = frame["team_code"]
    crest_urls = frame["crest_url"]
    photo_urls = frame["photo_url"]
    team_full = codes.map(lambda c: team_names.get(c, c))
    colors = [chart_color(c, league, n) for c, n in zip(codes, team_full)]

# Keep only metrics that have data in this source (e.g. no PIR in the NBA).
registry = [m for m in registry if np.isfinite(evaluate(m, frame, SHRINK)["observed"]).any()]
by_label = {tm(m.label): m for m in registry}

# ──────────────────────────────────────────────────────── sidebar: display
with st.sidebar:
    st.divider()
    st.subheader(t("display"))
    LABELS = {"lab_short": "Short name", "lab_full": "Full name", "lab_code": "Code", "lab_crest": "Crest",
              "lab_photo": "Photo", "lab_team_crest": "Team crest", "lab_none": "None"}
    if level == "Teams":
        label_mode = LABELS[st.radio(t("labels_teams"), ["lab_short", "lab_full", "lab_code", "lab_crest", "lab_none"],
                                     format_func=t)]
    else:
        label_mode = LABELS[st.radio(t("labels_players"), ["lab_short", "lab_full", "lab_photo", "lab_team_crest",
                                                           "lab_none"], format_func=t, help=t("labels_help"))]
    ellipse_mode = {"ell_all": "All", "ell_choose": "Choose", "ell_none": "None"}[
        st.radio(t("ellipses"), ["ell_all", "ell_choose", "ell_none"], horizontal=True, format_func=t,
                 index=0 if level == "Teams" else 1, help=t("ellipses_help"))]
    show_ellipses = ellipse_mode != "None"
    ci_level = st.select_slider(t("cred_level"), options=["50%", "68%", "95%"], value="68%",
                                disabled=not show_ellipses)
    estimate = "Bayes-adjusted" if st.radio(t("points_show"), ["observed", "adjusted"], horizontal=True,
                                            format_func=t) == "adjusted" else "Observed"
    show_shift = st.checkbox(t("arrow"), value=False, disabled=estimate == "Observed")
    show_medians = st.checkbox(t("medians"), value=True)
    show_quadrants = st.checkbox(t("quadrants"), value=True)
    show_leaders = st.checkbox(t("leaders"), value=True)
    round_text = st.text_input(t("round_label"), auto_round, help=t("round_help"))

labels = {"Short name": short_names, "Full name": full_names, "Code": codes}.get(label_mode, short_names)
image_urls = {"Crest": crest_urls, "Team crest": crest_urls, "Photo": photo_urls}.get(label_mode)
image_kind = "photo" if label_mode == "Photo" else "crest"
use_images = image_urls is not None and image_urls.notna().any()
if use_images:      # download once, crop photos to the face; failures fall back to the dot
    from explorer.images import CROP_VERSION
    with st.spinner(t("img_prep")):
        ready = prepared_images(tuple(sorted({u for u in image_urls if isinstance(u, str) and u})), image_kind,
                                CROP_VERSION)
    image_urls = image_urls.map(lambda u: ready.get(u) if isinstance(u, str) else None)
    use_images = image_urls.notna().any()
    if not use_images:
        st.sidebar.caption(t("img_failed"))
if image_urls is not None and not use_images:
    st.sidebar.caption(t("img_none"))

# ───────────────────────────────────────────────────────────────── controls
st.title("Basketball 2D Explorer")
round_html = (f"<span style='font-family:{BADGE_FONT};font-weight:700;letter-spacing:.12em;"
              f"background:#FFB000;color:#111;padding:2px 10px;border-radius:12px;font-size:0.85rem'>"
              f"{round_text.upper()}</span> &nbsp;" if round_text else "")
st.markdown(f"{round_html}<span style='opacity:.7'>{t('caption', context=context)}</span>", unsafe_allow_html=True)

c1, c2 = st.columns(2)
default_x, default_y = ("Offensive rating", "Defensive rating") if level == "Teams" else ("USG%", "TS%")
default_x = tm(default_x) if tm(default_x) in by_label else list(by_label)[0]
default_y = tm(default_y) if tm(default_y) in by_label else list(by_label)[1]
mx = by_label[c1.selectbox(t("x_axis"), list(by_label), index=list(by_label).index(default_x))]
my = by_label[c2.selectbox(t("y_axis"), list(by_label), index=list(by_label).index(default_y))]
X_LABEL, Y_LABEL = tm(mx.label), tm(my.label)
inv_x = c1.checkbox(t("reverse_x"), value=mx.better == "low")
inv_y = c2.checkbox(t("reverse_y"), value=my.better == "low")
highlight = st.multiselect(t("highlight"), sorted(labels.unique()))
if ellipse_mode == "Choose":
    ellipse_for = st.multiselect(t("ellipses_for"), sorted(labels.unique()), default=highlight,
                                 placeholder=t("ellipses_for_ph"))
else:
    ellipse_for = []

# ──────────────────────────────────────────────────────────────────── compute
ex = evaluate(mx, frame, SHRINK)
ey = evaluate(my, frame, SHRINK)
col = "adjusted" if estimate == "Bayes-adjusted" else "observed"
x, y = ex[col], ey[col]
is_hl = labels.isin(highlight).to_numpy() if highlight else np.zeros(len(frame), bool)
k = ellipse_scale(int(ci_level.rstrip("%")) / 100)
want_ellipse = (labels.isin(ellipse_for).to_numpy() if ellipse_mode == "Choose"
                else np.full(len(frame), ellipse_mode == "All"))


def side_word(metric, high_side: bool):
    if metric.better is None:
        return ("▲", "#8A8F98", t("w_high")) if high_side else ("▼", "#8A8F98", t("w_low"))
    good = high_side if metric.better == "high" else not high_side
    return ("▲", "#2E9E44", t("w_good")) if good else ("▼", "#D64545", t("w_bad"))


quads = {}
for vert in ("top", "bottom"):
    for horiz in ("left", "right"):
        a1, c1_, w1 = side_word(mx, (horiz == "right") != inv_x)
        a2, c2_, w2 = side_word(my, (vert == "top") != inv_y)
        quads[f"{vert}_{horiz}"] = [(a1, c1_, f"{w1} {X_LABEL}"), (a2, c2_, f"{w2} {Y_LABEL}")]
TAGS = {"Best": t("tag_best"), "Worst": t("tag_worst"), "Highest": t("tag_highest"), "Lowest": t("tag_lowest")}
boards = []
if show_leaders:
    for m, vals in ((mx, x), (my, y)):
        fmt = "{:.2f}" if np.nanmax(np.abs(vals)) < 10 else "{:.1f}"
        b = leaders(vals, labels, m, fmt=fmt)
        if b:
            b["label"] = tm(b["label"])
            b["top_tag"], b["bottom_tag"] = TAGS[b["top_tag"]], TAGS[b["bottom_tag"]]
            boards.append(b)

# ───────────────────────────────────────────────────────────────────── figure
fig = go.Figure()
ellipses = []
if show_ellipses:
    for i in range(len(frame)):
        if not want_ellipse[i]:
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

show_text = label_mode != "None" and not use_images and (level == "Teams" or len(frame) <= 25)
text = [lab if (show_text or h) else "" for lab, h in zip(labels, is_hl)]
fig.add_trace(go.Scatter(
    x=x, y=y, mode="markers+text", text=text, textposition="top center",
    textfont=dict(size=11),
    marker=dict(size=[16 if h else 11 for h in is_hl], color=colors,
                opacity=[0 if use_images and isinstance(u, str) else 1
                         for u in (image_urls if use_images else [None] * len(frame))],
                line=dict(width=[2.5 if h else 1 for h in is_hl], color="#FFFFFF")),
    customdata=np.stack([ex["observed"], ex["adjusted"], ex["sd"],
                         ey["observed"], ey["adjusted"], ey["sd"]], axis=1),
    hovertext=full_names, showlegend=False,
    hovertemplate=("<b>%{hovertext}</b><br>"
                   f"{X_LABEL}: %{{customdata[0]:.2f}} ({t('adj')} %{{customdata[1]:.2f}} ± %{{customdata[2]:.2f}})<br>"
                   f"{Y_LABEL}: %{{customdata[3]:.2f}} ({t('adj')} %{{customdata[4]:.2f}} ± %{{customdata[5]:.2f}})"
                   "<extra></extra>")))

if use_images:
    xr = float(np.nanmax(x) - np.nanmin(x)) or 1.0
    yr = float(np.nanmax(y) - np.nanmin(y)) or 1.0
    size = 0.07 if level == "Teams" or len(frame) <= 30 else 0.045
    for xi, yi, url, h in zip(x, y, image_urls, is_hl):
        if isinstance(url, str) and url:
            s = 1.35 if h else 1.0
            fig.add_layout_image(source=url, x=xi, y=yi, xref="x", yref="y",
                                 sizex=size * xr * s, sizey=size * yr * s,
                                 xanchor="center", yanchor="middle", layer="above")

if show_medians:
    fig.add_vline(x=float(np.nanmedian(x)), line_dash="dot", line_color="#888")
    fig.add_hline(y=float(np.nanmedian(y)), line_dash="dot", line_color="#888")

if show_quadrants:
    # One small uppercase "badge" per line: ▲ GOOD OFFENSIVE RATING / ▼ BAD DEFENSIVE RATING
    for key, lines in quads.items():
        vert, horiz = key.split("_")
        ordered = lines if vert == "top" else list(reversed(lines))
        for j, (arrow, color, text) in enumerate(ordered):
            fig.add_annotation(xref="paper", yref="paper", showarrow=False,
                               x=0.006 if horiz == "left" else 0.994, y=0.994 if vert == "top" else 0.006,
                               xanchor=horiz, yanchor=vert, yshift=(-1 if vert == "top" else 1) * 24 * j,
                               text=f"<b>{arrow} {smart_upper(text)}</b>",
                               font=dict(size=SMALL + 1, color=color, family=BADGE_FONT),
                               bgcolor=badge_fill(color), bordercolor=color, borderwidth=1, borderpad=3)

bottom_margin = 40
if boards:
    for j, board in enumerate(boards):
        fig.add_annotation(xref="paper", yref="paper", showarrow=False, align="left",
                           x=0, y=-0.11 - 0.075 * j, xanchor="left", yanchor="top",
                           text=leaders_html(board), font=dict(size=SMALL))
    bottom_margin = 150

fig.update_xaxes(title=X_LABEL, autorange="reversed" if inv_x else True)
fig.update_yaxes(title=Y_LABEL, autorange="reversed" if inv_y else True)
fig.update_layout(height=720, margin=dict(l=10, r=10, t=40, b=bottom_margin),
                  title=(f"{round_text.upper()} · " if round_text else "") + f"{Y_LABEL} vs {X_LABEL}")
st.plotly_chart(fig)

# ──────────────────────────────────────────────────────────────────────── table
z = 1.96
table = pd.DataFrame({t("name"): full_names.values})
if level == "Players":
    table[t("team")] = codes.values
    table[t("mpg")] = frame["min_pg"].round(1).values
for lab, ev in ((X_LABEL, ex), (Y_LABEL, ey)):
    table[lab] = ev["observed"].round(2).values
    table[f"{lab} {t('adj')}"] = ev["adjusted"].round(2).values
    table[f"{lab} {t('ci95')}"] = [f"{a - z * s:.2f} – {a + z * s:.2f}" if s > 0 else ""
                                   for a, s in zip(ev["adjusted"], ev["sd"])]
st.dataframe(table, hide_index=True)
st.download_button(t("download"), table.to_csv(index=False).encode(), "explorer_view.csv", "text/csv")

with st.expander(t("method")):
    st.markdown(t("method_text", level=ci_level))
    st.markdown(f"**{X_LABEL}**: {th(mx.label, mx.help) or '—'}  \n**{Y_LABEL}**: {th(my.label, my.help) or '—'}")
st.caption(t("built_by"))

# ─── PERSONAL EXPORT (see hook at the top) ────────────────────────────────────
if SOCIAL_EXPORT:
    try:
        from personal.social_export import social_export_panel
    except ImportError:
        social_export_panel = None
    if social_export_panel is not None:
        social_export_panel({
            "title": f"{Y_LABEL} vs {X_LABEL}", "context": context, "level": level,
            "x_label": X_LABEL, "y_label": Y_LABEL, "inv_x": inv_x, "inv_y": inv_y,
            "x": np.asarray(x, float), "y": np.asarray(y, float),
            "labels": list(labels if label_mode != "None" else short_names),
            "show_labels": label_mode != "None", "highlight": list(is_hl),
            "colors": colors, "image_urls": list(image_urls) if use_images else None, "image_kind": image_kind,
            "round": round_text,
            "ellipses": ellipses, "medians": (float(np.nanmedian(x)), float(np.nanmedian(y))) if show_medians else None,
            "quadrants": quads if show_quadrants else None, "leaders": boards,
            "estimate": estimate, "ci_level": ci_level if show_ellipses else None,
            "note_texts": {"Observed": t("export_obs"), "Bayes-adjusted": t("export_adj"),
                           "ellipses": t("export_ell", level=ci_level)},
        })
