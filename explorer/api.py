"""Client for the official public EuroLeague API (api-live.euroleague.net).

The same API serves the EuroLeague (code "E") and the EuroCup (code "U").
Responses are normalized to a standard set of short English columns
(pts, fg2a, orb...) so the rest of the app does not depend on the exact field
names of the API, which sometimes change between versions.
"""
from __future__ import annotations

import re

import pandas as pd
import requests

BASE_URL = "https://api-live.euroleague.net"
COMPETITIONS = {"EuroLeague": "E", "EuroCup": "U"}
PHASES = {"Regular season": "RS", "Whole season": None, "Playoffs": "PO"}

HEADERS = {"User-Agent": "basketball-2d-explorer/1.0 (non-commercial research and teaching)"}

# Standard name -> possible API field names (tried in order).
STAT_FIELDS = {
    "games": ["gamesPlayed", "games"],
    "min": ["minutesPlayed", "minutes"],
    "pts": ["pointsScored", "points"],
    "fg2m": ["twoPointersMade"],
    "fg2a": ["twoPointersAttempted"],
    "fg3m": ["threePointersMade"],
    "fg3a": ["threePointersAttempted"],
    "ftm": ["freeThrowsMade"],
    "fta": ["freeThrowsAttempted"],
    "orb": ["offensiveRebounds"],
    "drb": ["defensiveRebounds"],
    "trb": ["totalRebounds"],
    "ast": ["assists"],
    "stl": ["steals"],
    "tov": ["turnovers"],
    "blk": ["blocks", "blocksFavour"],
    "pf": ["foulsCommited", "foulsCommitted"],
    "pir": ["pir", "valuation", "performanceIndexRating"],
}
ID_FIELDS = {
    "players": {
        "player_code": ["player.code", "playerCode"],
        "player_name": ["player.name", "playerName"],
        "team_code": ["player.team.code", "team.code", "clubCode"],
        "team_name": ["player.team.name", "team.name", "clubName"],
    },
    "teams": {
        "team_code": ["team.code", "club.code", "code"],
        "team_name": ["team.name", "club.name", "name"],
    },
}


class EuroLeagueAPIError(RuntimeError):
    pass


def _get_json(url: str, params: dict) -> dict | list:
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=25)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as exc:
        raise EuroLeagueAPIError(f"Could not read {url}: {exc}") from exc


def fetch_stats(kind: str, endpoint: str, competition: str, season: int,
                phase: str | None = "RS", mode: str = "PerGame") -> pd.DataFrame:
    """Download season statistics.

    kind: "players" or "teams".
    endpoint: "traditional" (also "advanced"; for teams, "opponentsTraditional").
    season: starting year (2025 = season 2025-26).
    """
    url = f"{BASE_URL}/v3/competitions/{competition}/statistics/{kind}/{endpoint}"
    params = {
        "seasonMode": "Single",
        "seasonCode": f"{competition}{season}",
        "statisticMode": mode,
        "limit": 1000,
    }
    if phase:
        params["phaseTypeCode"] = phase
    data = _get_json(url, params)
    rows = data.get(kind) if isinstance(data, dict) else data
    if rows is None and isinstance(data, dict):
        rows = data.get("data", [])
    return pd.json_normalize(rows or [])


# ---------------------------------------------------------------- normalization
def _find(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    lower = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def _to_number(s: pd.Series) -> pd.Series:
    """Convert numbers, percentages ('45.2%') and minutes ('25:30') to float."""
    if s.dtype.kind in "if":
        return s.astype(float)

    def conv(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return float("nan")
        if isinstance(v, (int, float)):
            return float(v)
        v = str(v).strip().replace("%", "").replace(",", ".")
        m = re.fullmatch(r"(\d+):(\d{1,2})", v)
        if m:
            return int(m.group(1)) + int(m.group(2)) / 60
        try:
            return float(v)
        except ValueError:
            return float("nan")

    return s.map(conv)


def normalize_stats(raw: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Turn an API response into the app's standard format."""
    if raw.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=raw.index)
    for std, cands in ID_FIELDS[kind].items():
        col = _find(raw, cands)
        out[std] = raw[col].astype(str) if col else ""
    crest = next((c for c in raw.columns if "crest" in c.lower()), None)
    if crest is None:
        crest = next((c for c in raw.columns if "image" in c.lower()
                      and (kind == "teams" or "team" in c.lower())), None)
    out["crest_url"] = raw[crest] if crest else None
    if kind == "players":
        photo = next((c for c in raw.columns if "image" in c.lower() and "team" not in c.lower()), None)
        out["photo_url"] = raw[photo] if photo else None

    missing = []
    for std, cands in STAT_FIELDS.items():
        col = _find(raw, cands)
        if col is None:
            missing.append(std)
            out[std] = float("nan")
        else:
            out[std] = _to_number(raw[col])
    required = {"min", "pts", "fg2a", "fg3a", "fta", "orb", "tov"}
    if required & set(missing):
        raise EuroLeagueAPIError(
            "The API format has changed and key columns are missing: "
            f"{sorted(required & set(missing))}. Columns received: {list(raw.columns)[:40]}"
        )
    if out["trb"].isna().all():
        out["trb"] = out["orb"] + out["drb"]
    return out.reset_index(drop=True)


def load_season(competition: str, season: int, phase: str | None):
    """Return normalized (teams, opponents_of_each_team, players)."""
    teams = normalize_stats(fetch_stats("teams", "traditional", competition, season, phase), "teams")
    opp = normalize_stats(fetch_stats("teams", "opponentsTraditional", competition, season, phase), "teams")
    players = normalize_stats(fetch_stats("players", "traditional", competition, season, phase), "players")
    return teams, opp, players


def display_name(api_name: str) -> str:
    """'LLULL, SERGIO' -> 'Llull'. Without a comma, returns the name in title case."""
    name = str(api_name).strip()
    if "," in name:
        name = name.split(",")[0]
    return name.title()


def load_crest(url: str | None):
    """Download a crest or photo as a PIL image (PNG/JPG/WebP). None if not possible."""
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return None
    try:
        from io import BytesIO
        from PIL import Image

        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None
