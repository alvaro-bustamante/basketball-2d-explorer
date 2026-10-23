"""Leagues read from a hoops-warehouse folder (ACB, FEB, FIBA competitions…).

The warehouse writes, for every competition and season, one row per team and game
(<comp>_<season>_team_games.csv) and one per player and game (_player_games.csv). This module
turns them into the app's season tables: per-game averages of each team, of its opponents,
and of each player.

Where is the warehouse? In this order:
  1. the environment variable HOOPS_WAREHOUSE (a folder with the *_team_games.csv files);
  2. `warehouse_dir` in .streamlit/secrets.toml;
  3. ../hoops-warehouse/data/warehouse (both projects side by side);
  4. data/warehouse inside this project.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

STAT_COLUMNS = ["games", "min", "pts", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta",
                "orb", "drb", "trb", "ast", "stl", "tov", "blk", "pf", "pir"]


def folder() -> Path | None:
    candidates = [os.environ.get("HOOPS_WAREHOUSE")]
    try:
        import streamlit as st
        candidates.append(st.secrets.get("warehouse_dir"))
    except Exception:         # no secrets file
        pass
    here = Path(__file__).resolve().parents[1]
    candidates += [here.parent / "hoops-warehouse" / "data" / "warehouse", here / "data" / "warehouse"]
    for c in candidates:
        if c and Path(c).is_dir() and any(Path(c).glob("*_team_games.csv")):
            return Path(c)
    return None


def seasons(prefix: str, base: Path | None = None) -> list[int]:
    base = base or folder()
    if base is None:
        return []
    out = set()
    for f in base.glob(f"{prefix}_*_team_games.csv"):
        tail = f.name[len(prefix) + 1:-len("_team_games.csv")]
        if tail.isdigit():
            out.add(int(tail))
    return sorted(out, reverse=True)


def _app_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Warehouse columns (made / missed, seconds) -> app columns (made / attempts, minutes)."""
    out = pd.DataFrame(index=df.index)
    out["min"] = df["seconds"] / 60
    out["pts"] = df["pts"]
    for k, short in (("fg2", "fg2"), ("fg3", "fg3"), ("ft", "ft")):
        out[f"{short}m"] = df[f"{k}_made"]
        out[f"{short}a"] = df[f"{k}_made"] + df[f"{k}_missed"]
    for c in ("orb", "drb", "ast", "stl", "tov", "blk", "pf", "pir"):
        out[c] = df[c]
    out["trb"] = out["orb"] + out["drb"]
    return out


def load(prefix: str, season: int, base: Path | None = None):
    """(teams, opponents, players) per-game averages, in the app's format."""
    base = base or folder()
    if base is None:
        raise FileNotFoundError("No hoops-warehouse folder found (see explorer/warehouse.py).")
    tg = pd.read_csv(base / f"{prefix}_{season}_team_games.csv", dtype={"game_id": str})
    pg_path = base / f"{prefix}_{season}_player_games.csv"
    pg = pd.read_csv(pg_path, dtype={"game_id": str, "player_id": str}) if pg_path.exists() else None

    stats = _app_stats(tg)
    tg = pd.concat([tg[["game_id", "team", "team_name", "crest_url", "opponent"]], stats], axis=1)
    keys = [c for c in STAT_COLUMNS if c not in ("games",)]
    names = tg.groupby("team")["team_name"].agg(lambda s: s.dropna().iloc[-1] if s.notna().any() else None)
    crests = tg.groupby("team")["crest_url"].agg(lambda s: s.dropna().iloc[-1] if s.notna().any() else None)
    teams = tg.groupby("team")[keys].mean()
    teams.insert(0, "games", tg.groupby("team")["game_id"].nunique())
    teams = teams.reset_index().rename(columns={"team": "team_code"})
    teams.insert(1, "team_name", teams["team_code"].map(names).fillna(teams["team_code"]))
    teams["crest_url"] = teams["team_code"].map(crests)

    opp_rows = tg.merge(tg[["game_id", "team"] + keys], left_on=["game_id", "opponent"], right_on=["game_id", "team"],
                        suffixes=("_own", ""))
    opp = opp_rows.groupby("team_own")[keys].mean().reindex(teams["team_code"]).reset_index()
    opp = opp.rename(columns={"team_own": "team_code"})
    opp.insert(1, "team_name", teams["team_name"].values)
    opp.insert(2, "games", teams["games"].values)
    opp["min"] = teams["min"].values
    opp["crest_url"] = teams["crest_url"].values

    players = None
    if pg is not None and not pg.empty:
        pg = pg[pg["seconds"].fillna(0) > 0]
        ps = _app_stats(pg)
        pg = pd.concat([pg[["game_id", "team", "player_id", "player_name", "photo_url"]], ps], axis=1)
        g = pg.groupby("player_id")
        players = g[keys].mean()
        players.insert(0, "games", g["game_id"].nunique())
        players["player_name"] = g["player_name"].last()
        players["team_code"] = g["team"].last()                         # most recent team
        players["photo_url"] = g["photo_url"].agg(lambda s: s.dropna().iloc[-1] if s.notna().any() else None)
        players = players.reset_index()
        players["team_name"] = players["team_code"].map(teams.set_index("team_code")["team_name"])
        players["crest_url"] = players["team_code"].map(teams.set_index("team_code")["crest_url"])
        players["player_code"] = players["player_name"]
        cols = ["player_name", "team_code", "team_name"] + STAT_COLUMNS + ["player_code", "crest_url", "photo_url",
                                                                            "player_id"]
        players = players[cols]
    return teams[["team_code", "team_name"] + STAT_COLUMNS + ["crest_url"]], \
        opp[["team_code", "team_name"] + STAT_COLUMNS + ["crest_url"]], players


def has_lineups(prefix: str, season: int, base: Path | None = None) -> bool:
    """True if this competition-season comes from play by play (stints, possessions)."""
    base = base or folder()
    return bool(base) and (base / f"{prefix}_{season}_stints.csv.gz").exists()
