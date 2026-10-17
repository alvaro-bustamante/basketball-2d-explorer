"""Data sources: official EuroLeague/EuroCup API, your own CSV files, or demo data.

Every source returns (teams, opponents, players) in the same standard format
(per-game averages): see STANDARD_COLUMNS.
"""
from __future__ import annotations

import io

import pandas as pd

from . import api
from .demo import demo_data

STAT_COLUMNS = ["games", "min", "pts", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta",
                "orb", "drb", "trb", "ast", "stl", "tov", "blk", "pf", "pir"]
TEAM_ID = ["team_code", "team_name"]
PLAYER_ID = ["player_name", "team_code", "team_name"]


def from_api(competition_code: str, season: int, phase: str | None):
    return api.load_season(competition_code, season, phase)


def from_demo():
    return demo_data()


# ------------------------------------------------------------------ CSV files
def team_template() -> bytes:
    """One row per team: own per-game stats plus the same stats prefixed opp_."""
    teams, opp, _ = demo_data()
    o = opp.set_index("team_code")[STAT_COLUMNS[2:]].add_prefix("opp_")
    df = teams.set_index("team_code")[["team_name"] + STAT_COLUMNS].join(o).reset_index()
    return df.round(2).to_csv(index=False).encode()


def player_template() -> bytes:
    _, _, players = demo_data()
    return players[PLAYER_ID + STAT_COLUMNS].round(2).to_csv(index=False).encode()


def from_csv(team_file, player_file):
    """Read the two CSV files produced from the templates (ACB, NBA, any league)."""
    t = pd.read_csv(io.BytesIO(team_file.getvalue()))
    missing = [c for c in TEAM_ID + STAT_COLUMNS + ["opp_" + c for c in STAT_COLUMNS[2:]] if c not in t.columns]
    if missing:
        raise ValueError(f"Team CSV is missing columns: {missing}")
    teams = t[TEAM_ID + STAT_COLUMNS].copy()
    opp = t[["team_code", "team_name", "games", "min"] + ["opp_" + c for c in STAT_COLUMNS[2:]]].copy()
    opp.columns = ["team_code", "team_name", "games", "min"] + STAT_COLUMNS[2:]
    for df in (teams, opp):
        df["crest_url"] = None
    players = None
    if player_file is not None:
        p = pd.read_csv(io.BytesIO(player_file.getvalue()))
        missing = [c for c in PLAYER_ID + STAT_COLUMNS if c not in p.columns]
        if missing:
            raise ValueError(f"Player CSV is missing columns: {missing}")
        players = p[PLAYER_ID + STAT_COLUMNS].copy()
        players["player_code"] = players["player_name"]
        players["crest_url"] = None
    return teams, opp, players
