"""Metric registry: how every metric is computed and how uncertain it is.

Each metric returns either
  ("prop", successes, trials)  -> Beta-Binomial shrinkage, shown in %
  ("normal", value, std_error) -> Normal-Normal shrinkage
  ("none", value, None)        -> no uncertainty (context metrics like minutes)

Inputs are season TOTALS (per-game averages x games), built by
`team_totals` and `player_totals`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

# Documented approximations (see README, "Method").
SD_POINTS_PER_POSSESSION = 1.1   # SD of points scored on a single possession
SD_PACE_PER_GAME = 4.0           # game-to-game SD of possessions per 40 min
SD_TEAM_POINTS_PER_GAME = 11.0   # game-to-game SD of team points
DISPERSION = {"pts": 2.3, "trb": 1.2, "ast": 1.2, "tov": 1.2, "stl": 1.2, "blk": 1.2, "pir": 4.0}

STAT_COLS = ["pts", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta",
             "orb", "drb", "trb", "ast", "stl", "tov", "blk", "pf", "pir"]


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    better: str | None            # "high", "low" or None
    compute: Callable[[pd.DataFrame], tuple]
    help: str = ""


def _game_minutes_per_game(min_pg: pd.Series) -> pd.Series:
    """Team minutes can come as 200 (5 players x 40) or as 40."""
    return min_pg / 5 if min_pg.median() > 100 else min_pg


# --------------------------------------------------------------------- totals
def team_totals(teams: pd.DataFrame, opp: pd.DataFrame) -> pd.DataFrame:
    t = teams.set_index("team_code")
    o = opp.set_index("team_code").reindex(t.index)
    g = t["games"].astype(float)
    T = pd.DataFrame(index=t.index)
    T["name"] = t["team_name"]
    T["crest_url"] = t.get("crest_url")
    T["games"] = g
    for c in STAT_COLS:
        T["t_" + c] = t[c] * g
        T["o_" + c] = o[c] * g
    for p in ("t_", "o_"):
        T[p + "fga"] = T[p + "fg2a"] + T[p + "fg3a"]
        T[p + "fgm"] = T[p + "fg2m"] + T[p + "fg3m"]
        T[p + "poss"] = T[p + "fga"] + 0.44 * T[p + "fta"] - T[p + "orb"] + T[p + "tov"]
    T["poss"] = (T["t_poss"] + T["o_poss"]) / 2
    T["game_min"] = _game_minutes_per_game(t["min"]) * g
    return T


def player_totals(players: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    p = players.copy()
    tm = teams.set_index("team_code")
    g = p["games"].astype(float)
    P = pd.DataFrame(index=p.index)
    P["name"] = p["player_name"]
    P["team_code"] = p["team_code"]
    P["team_name"] = p["team_name"]
    P["games"] = g
    P["min_pg"] = p["min"]
    P["min"] = p["min"] * g
    for c in STAT_COLS:
        P[c] = p[c] * g
    P["fga"] = P["fg2a"] + P["fg3a"]
    P["fgm"] = P["fg2m"] + P["fg3m"]
    # Team context while the player is on court (per-game team values).
    tm_game_min = _game_minutes_per_game(tm["min"])
    share = p["min"] / p["team_code"].map(tm_game_min)
    tm_usage = p["team_code"].map(tm["fg2a"] + tm["fg3a"] + 0.44 * tm["fta"] + tm["tov"])
    tm_fgm = p["team_code"].map(tm["fg2m"] + tm["fg3m"])
    P["usage_opps"] = share * tm_usage * g
    P["teammate_fgm"] = (share * tm_fgm - (p["fg2m"] + p["fg3m"])) * g
    return P


# ------------------------------------------------------------------- helpers
def _prop(s, n):
    return ("prop", s, n)


def _rate100_se(poss):
    return 100 * SD_POINTS_PER_POSSESSION / np.sqrt(poss)


def _per_game(total_col, disp):
    def f(P):
        mean = P[total_col] / P["games"]
        se = np.sqrt(disp * mean.clip(lower=0.05) / P["games"])
        return ("normal", mean, se)
    return f


def _per40(total_col, disp):
    def f(P):
        val = 40 * P[total_col] / P["min"]
        se = 40 * np.sqrt(disp * P[total_col].clip(lower=0.5)) / P["min"]
        return ("normal", val, se)
    return f


# ------------------------------------------------------------------ registry
TEAM_METRICS = [
    Metric("ortg", "Offensive rating", "high",
           lambda T: ("normal", 100 * T.t_pts / T.poss, _rate100_se(T.poss)),
           "Points scored per 100 possessions."),
    Metric("drtg", "Defensive rating", "low",
           lambda T: ("normal", 100 * T.o_pts / T.poss, _rate100_se(T.poss)),
           "Points allowed per 100 possessions."),
    Metric("net", "Net rating", "high",
           lambda T: ("normal", 100 * (T.t_pts - T.o_pts) / T.poss, np.sqrt(2) * _rate100_se(T.poss)),
           "Offensive minus defensive rating."),
    Metric("pace", "Pace", None,
           lambda T: ("normal", 40 * T.poss / T.game_min, SD_PACE_PER_GAME / np.sqrt(T.games)),
           "Possessions per 40 minutes."),
    Metric("efg", "eFG%", "high", lambda T: _prop(T.t_fgm + 0.5 * T.t_fg3m, T.t_fga),
           "Effective field goal %: a three counts as 1.5 makes."),
    Metric("tov", "TOV%", "low", lambda T: _prop(T.t_tov, T.t_poss), "Turnovers per possession."),
    Metric("orb", "ORB%", "high", lambda T: _prop(T.t_orb, T.t_orb + T.o_drb),
           "Share of available offensive rebounds."),
    Metric("drb", "DRB%", "high", lambda T: _prop(T.t_drb, T.t_drb + T.o_orb),
           "Share of available defensive rebounds."),
    Metric("ftr", "FT rate", "high", lambda T: _prop(T.t_ftm, T.t_fga), "Free throws made per FGA."),
    Metric("par3", "3PA rate", None, lambda T: _prop(T.t_fg3a, T.t_fga), "Share of FGA that are threes."),
    Metric("p3", "3P%", "high", lambda T: _prop(T.t_fg3m, T.t_fg3a), "Three-point %."),
    Metric("p2", "2P%", "high", lambda T: _prop(T.t_fg2m, T.t_fg2a), "Two-point %."),
    Metric("ft", "FT%", "high", lambda T: _prop(T.t_ftm, T.t_fta), "Free throw %."),
    Metric("astp", "AST%", None, lambda T: _prop(T.t_ast, T.t_fgm), "Share of made FG that are assisted."),
    Metric("o_efg", "Opp eFG%", "low", lambda T: _prop(T.o_fgm + 0.5 * T.o_fg3m, T.o_fga),
           "Opponent effective FG%."),
    Metric("o_tov", "Opp TOV%", "high", lambda T: _prop(T.o_tov, T.o_poss), "Turnovers forced per possession."),
    Metric("o_p3", "Opp 3P%", "low", lambda T: _prop(T.o_fg3m, T.o_fg3a), "Opponent three-point %."),
    Metric("pts", "Points per game", "high",
           lambda T: ("normal", T.t_pts / T.games, SD_TEAM_POINTS_PER_GAME / np.sqrt(T.games))),
    Metric("o_pts", "Opp points per game", "low",
           lambda T: ("normal", T.o_pts / T.games, SD_TEAM_POINTS_PER_GAME / np.sqrt(T.games))),
]

PLAYER_METRICS = [
    Metric("min", "Minutes per game", None, lambda P: ("none", P.min_pg, None)),
    Metric("pts", "Points per game", "high", _per_game("pts", DISPERSION["pts"])),
    Metric("reb", "Rebounds per game", "high", _per_game("trb", DISPERSION["trb"])),
    Metric("ast", "Assists per game", "high", _per_game("ast", DISPERSION["ast"])),
    Metric("tov", "Turnovers per game", "low", _per_game("tov", DISPERSION["tov"])),
    Metric("stl", "Steals per game", "high", _per_game("stl", DISPERSION["stl"])),
    Metric("blk", "Blocks per game", "high", _per_game("blk", DISPERSION["blk"])),
    Metric("pir", "PIR per game", "high", _per_game("pir", DISPERSION["pir"]), "EuroLeague efficiency rating."),
    Metric("pts40", "Points per 40", "high", _per40("pts", DISPERSION["pts"])),
    Metric("reb40", "Rebounds per 40", "high", _per40("trb", DISPERSION["trb"])),
    Metric("ast40", "Assists per 40", "high", _per40("ast", DISPERSION["ast"])),
    Metric("ts", "TS%", "high", lambda P: _prop(P.pts / 2, P.fga + 0.44 * P.fta),
           "True shooting %: points per shooting possession."),
    Metric("efg", "eFG%", "high", lambda P: _prop(P.fgm + 0.5 * P.fg3m, P.fga)),
    Metric("p3", "3P%", "high", lambda P: _prop(P.fg3m, P.fg3a)),
    Metric("p2", "2P%", "high", lambda P: _prop(P.fg2m, P.fg2a)),
    Metric("ft", "FT%", "high", lambda P: _prop(P.ftm, P.fta)),
    Metric("par3", "3PA rate", None, lambda P: _prop(P.fg3a, P.fga), "Share of FGA that are threes."),
    Metric("ftr", "FT rate", "high", lambda P: _prop(P.ftm, P.fga)),
    Metric("usg", "USG%", None, lambda P: _prop(P.fga + 0.44 * P.fta + P.tov, P.usage_opps),
           "Share of team possessions used while on court."),
    Metric("astp", "AST%", "high", lambda P: _prop(P.ast, P.teammate_fgm),
           "Share of teammates' made FG assisted while on court."),
    Metric("tovp", "TOV%", "low", lambda P: _prop(P.tov, P.fga + 0.44 * P.fta + P.tov),
           "Turnovers per possession used."),
]


def evaluate(metric: Metric, frame: pd.DataFrame, shrink) -> pd.DataFrame:
    """Observed value, adjusted (posterior) value and posterior SD for one metric."""
    kind, a, b = metric.compute(frame)
    out = pd.DataFrame(index=frame.index)
    if kind == "prop":
        s = np.asarray(a, float)
        n = np.asarray(b, float)
        with np.errstate(divide="ignore", invalid="ignore"):
            obs = np.where(n > 0, s / n, np.nan)
        post, sd, _ = shrink["prop"](s, n)
        out["observed"] = 100 * obs
        out["adjusted"] = 100 * post
        out["sd"] = 100 * sd
    elif kind == "normal":
        obs = np.asarray(a, float)
        post, sd, _ = shrink["normal"](obs, np.asarray(b, float))
        out["observed"] = obs
        out["adjusted"] = post
        out["sd"] = sd
    else:
        obs = np.asarray(a, float)
        out["observed"] = obs
        out["adjusted"] = obs
        out["sd"] = 0.0
    return out
