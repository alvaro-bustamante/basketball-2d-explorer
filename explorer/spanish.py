"""Import Spanish-language stats tables (ACB, Primera FEB, Segunda FEB...).

Neither league offers a public API. This module reads tables you saved
yourself, or that a club gives you, and converts them to the app's standard
format:

* an HTML page saved from the browser (File > Save as), an Excel file or a CSV;
* Spanish headers (PJ, MIN, PTS, T2, T3, TL, RO, RD, RT, AS, BR, BP, TAP, FC, VAL)
  or English ones (GP, FGM, 3PA, OREB...);
* shooting written as one column ("25/50", "25-50") or as two columns
  ("T2 Anot." and "T2 Int.");
* season averages or totals (totals are divided by games).

Two layouts are supported:

1. Season tables: one table for each team's own stats and one for the stats
   its opponents made against it ("rivales"). Optional player table.
2. A team game log: one row per team and game with a game id. Opponent stats
   are then derived automatically from the other team in each game, so a
   single file is enough. This is the most robust option for club data.
"""
from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

STAT_COLUMNS = ["games", "min", "pts", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta",
                "orb", "drb", "trb", "ast", "stl", "tov", "blk", "pf", "pir"]

# Normalized header -> standard column. Headers are upper-cased, accents and
# punctuation removed ("T2 Anot." -> "T2ANOT").
SINGLE = {
    "games": ["PJ", "J", "PART", "PARTIDOS", "GP", "G", "GAMES"],
    "min": ["MIN", "MINUTOS", "MINS", "MP"],
    "pts": ["PTS", "PT", "PUNTOS", "P", "POINTS"],
    "orb": ["RO", "REBO", "REBOF", "OF", "OREB", "ORB"],
    "drb": ["RD", "REBD", "REBDEF", "DEF", "DREB", "DRB"],
    "trb": ["RT", "REB", "REBT", "REBOTES", "TOT", "TREB", "TRB"],
    "ast": ["AS", "ASI", "ASIS", "ASISTENCIAS", "AST", "A"],
    "stl": ["BR", "REC", "ROB", "RECUPERACIONES", "STL"],
    "tov": ["BP", "PER", "PERD", "PERDIDAS", "TOV", "TO"],
    "blk": ["TAP", "TF", "TAPF", "TAPFAV", "TAPONES", "BLK"],
    "pf": ["FC", "FP", "FALTAS", "FALC", "PF"],
    "pir": ["VAL", "VA", "V", "VALORACION", "PIR", "EFF"],
}
# Shooting families: Spanish and English prefixes.
SHOTS = {"fg2": ["T2", "2P", "FG2", "TC2"], "fg3": ["T3", "3P", "FG3", "TC3"], "ft": ["TL", "T1", "FT"],
         "fg": ["TC", "FG"]}   # all field goals: used only to derive twos when they are missing
MADE_SUFFIX = ["ANOT", "CONV", "MET", "M", "C", "MADE"]
ATT_SUFFIX = ["INT", "LANZ", "A", "I", "ATT", "ATTEMPTED"]
NAME_COLS = {"team_name": ["EQUIPO", "TEAM", "CLUB"],
             "player_name": ["JUGADOR", "JUGADORA", "NOMBRE", "PLAYER"],
             "game_id": ["IDPARTIDO", "PARTIDO", "GAMEID", "GAME", "MATCH"],
             "photo_url": ["PHOTOURL", "FOTO"], "crest_url": ["CRESTURL", "ESCUDO"],
             "team_code": ["TEAMCODE", "CODIGO", "COD"]}


def _norm(h) -> str:
    if isinstance(h, tuple):  # multi-level HTML headers ("Rebotes", "RO") -> "RO"
        parts = [str(x) for x in h if "Unnamed" not in str(x)]
        h = parts[-1] if parts else ""
    h = re.sub(r"\.\d+$", "", str(h))   # pandas renames duplicates: "TC.1" -> "TC"
    t = unicodedata.normalize("NFKD", str(h)).encode("ascii", "ignore").decode().upper()
    t = t.replace("%", "PCT")
    return re.sub(r"[^A-Z0-9_]", "", t)


def _num(s: pd.Series, pick: str = "first") -> pd.Series:
    """Text to float. Cells with two numbers ("334 / 83,5": total and average)
    keep the first (pick="first") or the last (pick="last")."""
    def conv(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return np.nan
        if isinstance(v, (int, float, np.number)):
            return float(v)
        v = str(v).strip()
        two = re.fullmatch(r"([\d.,:]+)\s*(?:/|\s)\s*\(?([\d.,:]+)\)?", v)
        if two and " " in v:
            v = two.group(1) if pick == "first" else two.group(2)
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", v):   # Spanish thousands: 1.234
            v = v.replace(".", "")
        v = v.replace(",", ".")
        m = re.fullmatch(r"(\d+):(\d{1,2})", v)       # minutes 25:30
        if m:
            return int(m.group(1)) + int(m.group(2)) / 60
        try:
            return float(v)
        except ValueError:
            return np.nan
    return s.map(conv)


def _split_made_att(s: pd.Series):
    """'25/50', '25-50' or '25 de 50' -> (25, 50)."""
    parts = s.astype(str).str.extract(r"(\d+(?:[.,]\d+)?)\s*(?:/|-|de)\s*(\d+(?:[.,]\d+)?)")
    return _num(parts[0]), _num(parts[1])


def standardize(df: pd.DataFrame, values: str = "averages") -> pd.DataFrame:
    """Map any Spanish/English stats table to the standard columns.

    values: "averages" (per game) or "totals" (divided by games played).
    """
    cols = {c: _norm(c) for c in df.columns}
    pick = "first" if values == "totals" else "last"
    out = pd.DataFrame(index=df.index)
    used = set()
    for std, keys in NAME_COLS.items():
        col = next((c for c, n in cols.items() if n in keys), None)
        if col is not None:
            out[std] = df[col].astype(str).str.strip()
            used.add(col)
    for std, keys in SINGLE.items():
        col = next((c for c, n in cols.items() if n in keys and c not in used), None)
        if col is not None:
            out[std] = _num(df[col], pick)
            used.add(col)
    for fam, prefixes in SHOTS.items():
        made = att = None
        for c, n in cols.items():
            if c in used:
                continue
            p = next((p for p in prefixes if n.startswith(p)), None)
            if p is None or "PCT" in n:
                continue
            rest = n[len(p):]
            if rest == "":
                m, a = _split_made_att(df[c])
                if m.notna().any():
                    made, att = m, a
                    used.add(c)
            elif rest in MADE_SUFFIX and made is None:
                made = _num(df[c]); used.add(c)
            elif rest in ATT_SUFFIX and att is None:
                att = _num(df[c]); used.add(c)
        if made is not None and att is not None:
            out[fam + "m"], out[fam + "a"] = made, att
    if "orb" not in out:   # rebounds written as "D+O" ("12+4")
        col = next((c for c, n in cols.items() if n in ("DO", "RDO", "REBDO") and c not in used), None)
        if col is not None:
            parts = df[col].astype(str).str.extract(r"(\d+)\s*\+\s*(\d+)")
            out["drb"], out["orb"] = _num(parts[0]), _num(parts[1])
    if "fg2m" not in out and {"fgm", "fga", "fg3m", "fg3a"} <= set(out):
        out["fg2m"], out["fg2a"] = out["fgm"] - out["fg3m"], out["fga"] - out["fg3a"]
    out = out.drop(columns=[c for c in ("fgm", "fga") if c in out])
    if "trb" not in out and {"orb", "drb"} <= set(out):
        out["trb"] = out["orb"] + out["drb"]
    if "pir" not in out:
        out["pir"] = np.nan
    if "pf" not in out:
        out["pf"] = np.nan
    if values == "totals" and "games" in out:
        g = out["games"].replace(0, np.nan)
        for c in STAT_COLUMNS:
            if c in out and c not in ("games",):
                out[c] = out[c] / g
    missing = [c for c in ["pts", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "ast", "tov"]
               if c not in out]
    if missing:
        raise ValueError(f"Could not find columns for {missing}. Headers found: {list(df.columns)}")
    return out


# --------------------------------------------------------------------- reading
def read_tables(source, name: str = "") -> list[pd.DataFrame]:
    """All tables in an HTML page, Excel file or CSV (path or uploaded file)."""
    name = (name or str(getattr(source, "name", source))).lower()
    data = source.getvalue() if hasattr(source, "getvalue") else Path(source).read_bytes()
    if name.endswith((".html", ".htm")):
        return pd.read_html(io.StringIO(data.decode("utf-8", errors="ignore")), thousands=None)
    if name.endswith((".xlsx", ".xls")):
        return list(pd.read_excel(io.BytesIO(data), sheet_name=None).values())
    text = data.decode("utf-8-sig", errors="ignore")
    sep = ";" if text.count(";") > text.count(",") else ","
    return [pd.read_csv(io.StringIO(text), sep=sep, decimal="," if sep == ";" else ".")]


def _biggest_stats_table(tables: list[pd.DataFrame], values: str) -> pd.DataFrame:
    best, err = None, None
    for t in sorted(tables, key=len, reverse=True):
        try:
            best = standardize(t, values)
            break
        except ValueError as exc:
            err = exc
    if best is None:
        raise err or ValueError("No stats table found.")
    return best


def _with_codes(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["team_name"].str.len() > 0].copy()
    df = df[~df["team_name"].str.upper().isin(["TOTAL", "TOTALES", "MEDIA", "PROMEDIO", "LIGA"])]
    if "team_code" not in df:
        lookup, seen = {}, {}
        for name in dict.fromkeys(df["team_name"]):      # unique names, in order
            base = team_code_from_name(name)
            seen[base] = seen.get(base, 0) + 1
            lookup[name] = base if seen[base] == 1 else f"{base}{seen[base]}"
        df["team_code"] = df["team_name"].map(lookup)
    return df


def team_code_from_name(name: str) -> str:
    """Stable short code from a team name: 'Dreamland Gran Canaria' -> 'DGC'."""
    plain = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().upper()
    words = [w for w in re.findall(r"[A-Z0-9]+", plain)
             if w not in ("CB", "CD", "CLUB", "BASKET", "BASQUET", "BALONCESTO", "DE", "LA", "EL")]
    if not words:
        return "TEAM"
    return words[0][:3] if len(words) == 1 else "".join(w[0] for w in words[:3])


# ------------------------------------------------------------------ layouts
def from_season_tables(team_src, opp_src, player_src=None, values: str = "averages"):
    """Layout 1: own team stats + opponents' stats (+ optional players)."""
    teams = _with_codes(_biggest_stats_table(read_tables(team_src), values))
    opp = _with_codes(_biggest_stats_table(read_tables(opp_src), values))
    # Match opponents to teams by name (codes come from names).
    opp = opp.set_index("team_name").reindex(teams["team_name"]).reset_index()
    opp["team_code"] = teams["team_code"].values
    for c in ("games", "min"):
        if c in teams:
            opp[c] = teams[c].values
    players = None
    if player_src is not None:
        players = _biggest_stats_table(read_tables(player_src), values)
        if "player_name" not in players:
            raise ValueError("Player table needs a 'Jugador' (or 'Player') column.")
        if "team_code" not in players:
            lookup = dict(zip(teams["team_name"], teams["team_code"]))
            players["team_code"] = players.get("team_name", pd.Series("", index=players.index)).map(lookup)
        players["player_code"] = players["player_name"]
    return _finish(teams), _finish(opp), _finish(players) if players is not None else None


def from_game_log(src, players_src=None):
    """Layout 2: one row per team and game (needs a game id). Opponents derived."""
    log = _biggest_stats_table(read_tables(src), "averages")  # one game per row
    players = None
    if players_src is not None:
        players = _biggest_stats_table(read_tables(players_src), "averages")
        players["player_code"] = players["player_name"]
    return aggregate_game_log(log, players)


def aggregate_game_log(log: pd.DataFrame, players: pd.DataFrame | None = None):
    """Season per-game averages for teams and their opponents from a team game log."""
    log = log.copy()
    if "game_id" not in log:
        raise ValueError("The game log needs a game id column ('Partido', 'IdPartido' or 'game_id').")
    log = _with_codes(log)
    if "min" not in log:
        log["min"] = 200.0
    stats = [c for c in STAT_COLUMNS if c in log and c not in ("games",)]
    counts = log.groupby("game_id")["team_code"].transform("count")
    log = log[counts == 2]
    other = log.merge(log, on="game_id", suffixes=("", "_opp"))
    other = other[other["team_code"] != other["team_code_opp"]]
    teams = log.groupby(["team_code", "team_name"])[stats].mean().reset_index()
    games = log.groupby("team_code")["game_id"].nunique()
    teams["games"] = teams["team_code"].map(games)
    if "crest_url" in log:
        crest = log.dropna(subset=["crest_url"]).groupby("team_code")["crest_url"].first()
        teams["crest_url"] = teams["team_code"].map(crest)
    opp = other.groupby("team_code")[[c + "_opp" for c in stats]].mean()
    opp.columns = stats
    opp = opp.reindex(teams["team_code"]).reset_index()
    opp.insert(1, "team_name", teams["team_name"].values)
    opp["games"], opp["min"] = teams["games"].values, teams["min"].values
    if players is not None and "team_code" not in players and "team_name" in players:
        players["team_code"] = players["team_name"].map(dict(zip(teams["team_name"], teams["team_code"])))
    return _finish(teams), _finish(opp), _finish(players) if players is not None else None


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    for c in STAT_COLUMNS:
        if c not in df:
            df[c] = 200.0 if c == "min" and "player_name" not in df else np.nan
    for c in ("crest_url", "photo_url", "team_name"):
        if c not in df:
            df[c] = None
    return df.reset_index(drop=True)


def to_template(teams: pd.DataFrame, opp: pd.DataFrame) -> pd.DataFrame:
    """One CSV in the app's team template format (with opp_ columns)."""
    o = opp.set_index("team_code")[STAT_COLUMNS[2:]].add_prefix("opp_")
    keep = ["team_code", "team_name"] + STAT_COLUMNS + (["crest_url"] if teams["crest_url"].notna().any() else [])
    from .sources import to_made_missed
    return to_made_missed(teams[keep].set_index("team_code").join(o).reset_index())
