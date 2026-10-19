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
# Shots are exchanged as MADE and MISSED (mutually exclusive events); attempts are only
# computed internally (made + missed) where a formula needs them.
MISSED = {"fg2a": "fg2x", "fg3a": "fg3x", "fta": "ftx"}
MADE = {"fg2a": "fg2m", "fg3a": "fg3m", "fta": "ftm"}


def to_made_missed(df: pd.DataFrame, prefixes=("", "opp_")) -> pd.DataFrame:
    """Replace attempt columns (fg2a, fg3a, fta) by missed columns (fg2x, fg3x, ftx)."""
    out = df.copy()
    for pre in prefixes:
        for att, miss in MISSED.items():
            if pre + att in out.columns and pre + MADE[att] in out.columns:
                out.insert(out.columns.get_loc(pre + att), pre + miss, out[pre + att] - out[pre + MADE[att]])
                out = out.drop(columns=[pre + att])
    return out


def from_made_missed(df: pd.DataFrame, prefixes=("", "opp_")) -> pd.DataFrame:
    """Accept files written either with missed (fg2x...) or with attempts (fg2a...)."""
    out = df.copy()
    for pre in prefixes:
        for att, miss in MISSED.items():
            if pre + miss in out.columns and pre + att not in out.columns and pre + MADE[att] in out.columns:
                out[pre + att] = out[pre + MADE[att]] + out[pre + miss]
    return out
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
    return to_made_missed(df).round(3).to_csv(index=False).encode()


def player_template() -> bytes:
    _, _, players = demo_data()
    return to_made_missed(players[PLAYER_ID + STAT_COLUMNS]).round(3).to_csv(index=False).encode()


def _bytes(f) -> bytes:
    """Uploaded file (Streamlit) or a path on disk."""
    from pathlib import Path
    return f.getvalue() if hasattr(f, "getvalue") else Path(f).read_bytes()


def from_csv(team_file, player_file):
    """Read the two CSV files produced from the templates (ACB, Primera FEB, NBA, any league).

    Optional columns: crest_url (teams and players) and photo_url (players).
    """
    t = from_made_missed(pd.read_csv(io.BytesIO(_bytes(team_file))))
    missing = [c for c in TEAM_ID + STAT_COLUMNS + ["opp_" + c for c in STAT_COLUMNS[2:]] if c not in t.columns]
    if missing:
        raise ValueError(f"Team CSV is missing columns: {missing}")
    teams = t[TEAM_ID + STAT_COLUMNS].copy()
    opp = t[["team_code", "team_name", "games", "min"] + ["opp_" + c for c in STAT_COLUMNS[2:]]].copy()
    opp.columns = ["team_code", "team_name", "games", "min"] + STAT_COLUMNS[2:]
    for df in (teams, opp):
        df["crest_url"] = t["crest_url"] if "crest_url" in t.columns else None
    players = None
    if player_file is not None:
        p = from_made_missed(pd.read_csv(io.BytesIO(_bytes(player_file))))
        missing = [c for c in PLAYER_ID + STAT_COLUMNS if c not in p.columns]
        if missing:
            raise ValueError(f"Player CSV is missing columns: {missing}")
        players = p[PLAYER_ID + STAT_COLUMNS].copy()
        players["player_code"] = players["player_name"]
        # Optional image columns: crest_url (team crest) and photo_url (player photo).
        for c in ("crest_url", "photo_url"):
            players[c] = p[c] if c in p.columns else None
    return teams, opp, players
