"""NBA data through the `nba_api` package (stats.nba.com).

stats.nba.com is the NBA's own statistics site. It is not an official public
API, it is rate limited and it often blocks requests from cloud servers
(including Streamlit Community Cloud). Use it locally, or export CSV files with
`pipelines/export_nba_csv.py` and load them in the app.
"""
from __future__ import annotations

import time

import pandas as pd

LOGO_URL = "https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"
HEADSHOT_URL = "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"


class NBADataError(RuntimeError):
    pass


def _season_string(season: int) -> str:
    return f"{season}-{str(season + 1)[-2:]}"


def _endpoints():
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashteamstats
        from nba_api.stats.static import teams as static_teams
    except ImportError as exc:  # pragma: no cover
        raise NBADataError("Install nba_api first: pip install nba_api") from exc
    return leaguedashteamstats, leaguedashplayerstats, static_teams


def _with_fg2(df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    c = lambda k: df[prefix + k]  # noqa: E731
    out["pts"] = c("PTS")
    out["fg3m"], out["fg3a"] = c("FG3M"), c("FG3A")
    out["fg2m"], out["fg2a"] = c("FGM") - c("FG3M"), c("FGA") - c("FG3A")
    out["ftm"], out["fta"] = c("FTM"), c("FTA")
    out["orb"], out["drb"], out["trb"] = c("OREB"), c("DREB"), c("REB")
    out["ast"], out["stl"], out["tov"], out["blk"], out["pf"] = c("AST"), c("STL"), c("TOV"), c("BLK"), c("PF")
    out["pir"] = float("nan")  # PIR is a FIBA/EuroLeague metric
    return out


def load_season(season: int, season_type: str = "Regular Season", pause: float = 0.8):
    """Return (teams, opponents, players) in the app's standard per-game format."""
    team_ep, player_ep, static_teams = _endpoints()
    s = _season_string(season)
    try:
        base = team_ep.LeagueDashTeamStats(season=s, season_type_all_star=season_type,
                                           per_mode_detailed="PerGame",
                                           measure_type_detailed_defense="Base",
                                           timeout=60).get_data_frames()[0]
        time.sleep(pause)
        oppo = team_ep.LeagueDashTeamStats(season=s, season_type_all_star=season_type,
                                           per_mode_detailed="PerGame",
                                           measure_type_detailed_defense="Opponent",
                                           timeout=60).get_data_frames()[0]
        time.sleep(pause)
        plyr = player_ep.LeagueDashPlayerStats(season=s, season_type_all_star=season_type,
                                               per_mode_detailed="PerGame",
                                               timeout=60).get_data_frames()[0]
    except Exception as exc:  # network errors, blocks, timeouts
        raise NBADataError(f"stats.nba.com did not answer ({exc}). Try again later, "
                           "or use the CSV export script.") from exc
    if base.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    info = {t["id"]: t for t in static_teams.get_teams()}
    code = base["TEAM_ID"].map(lambda i: info.get(i, {}).get("abbreviation", str(i)))
    ident = pd.DataFrame({"team_code": code, "team_name": base["TEAM_NAME"],
                          "crest_url": base["TEAM_ID"].map(lambda i: LOGO_URL.format(team_id=i)),
                          "games": base["GP"], "min": base["MIN"]})
    teams = pd.concat([ident, _with_fg2(base)], axis=1)

    o = oppo.set_index("TEAM_ID").reindex(base["TEAM_ID"]).reset_index()
    opp = pd.concat([ident, _with_fg2(o, prefix="OPP_")], axis=1)

    players = pd.concat([pd.DataFrame({
        "player_code": plyr["PLAYER_ID"].astype(str), "player_name": plyr["PLAYER_NAME"],
        "team_code": plyr["TEAM_ABBREVIATION"],
        "team_name": plyr["TEAM_ABBREVIATION"].map(
            {t["abbreviation"]: t["full_name"] for t in info.values()}),
        "crest_url": plyr["TEAM_ID"].map(lambda i: LOGO_URL.format(team_id=i)),
        "photo_url": plyr["PLAYER_ID"].map(lambda i: HEADSHOT_URL.format(player_id=i)),
        "games": plyr["GP"], "min": plyr["MIN"]}), _with_fg2(plyr)], axis=1)
    return teams, opp, players
