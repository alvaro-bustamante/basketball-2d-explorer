"""Download one NBA season and save it as CSV files in the app's template format.

Usage (from the project folder, with the virtual environment active):
    python pipelines/export_nba_csv.py 2025

Creates data/nba_2025-26_teams.csv and data/nba_2025-26_players.csv, which you
can upload in the app ("Your CSV files"). The data/ folder is in .gitignore.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from explorer import nba  # noqa: E402
from explorer.sources import PLAYER_ID, STAT_COLUMNS  # noqa: E402


def main(season: int):
    teams, opp, players = nba.load_season(season)
    out = Path("data")
    out.mkdir(exist_ok=True)
    label = f"{season}-{str(season + 1)[-2:]}"
    o = opp.set_index("team_code")[STAT_COLUMNS[2:]].add_prefix("opp_")
    t = teams.set_index("team_code")[["team_name"] + STAT_COLUMNS].join(o).reset_index()
    t.to_csv(out / f"nba_{label}_teams.csv", index=False)
    players[PLAYER_ID + STAT_COLUMNS].to_csv(out / f"nba_{label}_players.csv", index=False)
    print(f"Saved {len(t)} teams and {len(players)} players to {out.resolve()}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2025)
