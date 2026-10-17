"""Acceso a la API pública oficial de la EuroLeague (api-live.euroleague.net).

La misma API sirve EuroLeague (código "E") y EuroCup (código "U").
Las respuestas se normalizan a un formato estándar de columnas en inglés
abreviado (pts, fg2a, orb...) para que el resto de la app no dependa de los
nombres exactos que use la API, que cambian a veces entre versiones.
"""
from __future__ import annotations

import re

import pandas as pd
import requests

BASE_URL = "https://api-live.euroleague.net"
COMPETITIONS = {"EuroLeague": "E", "EuroCup": "U"}
PHASES = {"Temporada regular": "RS", "Toda la temporada": None, "Playoffs": "PO"}

HEADERS = {"User-Agent": "el-quinteto-dashboard/1.0 (uso personal y docente)"}

# Nombre estándar -> posibles nombres en la API (se prueba en orden).
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
        raise EuroLeagueAPIError(f"No se pudo leer {url}: {exc}") from exc


def fetch_stats(kind: str, endpoint: str, competition: str, season: int,
                phase: str | None = "RS", mode: str = "PerGame") -> pd.DataFrame:
    """Descarga estadísticas de temporada.

    kind: "players" o "teams".
    endpoint: "traditional" (también "advanced"; para equipos, "opponentsTraditional").
    season: año de inicio (2025 = temporada 2025-26).
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


# ---------------------------------------------------------------- normalización
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
    """Convierte números, porcentajes ('45.2%') y minutos ('25:30') a float."""
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
    """Pasa una respuesta de la API al formato estándar de la app."""
    if raw.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=raw.index)
    for std, cands in ID_FIELDS[kind].items():
        col = _find(raw, cands)
        out[std] = raw[col].astype(str) if col else ""
    crest = next((c for c in raw.columns if "crest" in c.lower()), None)
    if crest is None and kind == "teams":
        crest = next((c for c in raw.columns if "image" in c.lower()), None)
    out["crest_url"] = raw[crest] if crest else None

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
            "La API ha cambiado el formato y faltan columnas clave: "
            f"{sorted(required & set(missing))}. Columnas recibidas: {list(raw.columns)[:40]}"
        )
    if out["trb"].isna().all():
        out["trb"] = out["orb"] + out["drb"]
    return out.reset_index(drop=True)


def load_season(competition: str, season: int, phase: str | None):
    """Devuelve (equipos, rivales_de_cada_equipo, jugadores) ya normalizados."""
    teams = normalize_stats(fetch_stats("teams", "traditional", competition, season, phase), "teams")
    opp = normalize_stats(fetch_stats("teams", "opponentsTraditional", competition, season, phase), "teams")
    players = normalize_stats(fetch_stats("players", "traditional", competition, season, phase), "players")
    return teams, opp, players


def display_name(api_name: str) -> str:
    """'LLULL, SERGIO' -> 'Llull'. Si no hay coma, devuelve el nombre en formato título."""
    name = str(api_name).strip()
    if "," in name:
        name = name.split(",")[0]
    return name.title()


def load_crest(url: str | None):
    """Descarga un escudo como imagen PIL. Devuelve None si no se puede."""
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
