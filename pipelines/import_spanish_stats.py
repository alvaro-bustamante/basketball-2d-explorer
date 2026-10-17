"""Convert ACB / Primera FEB stats tables into the app's CSV templates.

Two ways to use it (from the project folder, with the virtual environment active):

1) Season tables (own stats + opponents' stats), saved from the league
   website (File > Save as... > HTML), exported to Excel or copied into a CSV:

    python pipelines/import_spanish_stats.py --league acb ^
        --teams data/acb_equipos.html --opponents data/acb_rivales.html ^
        --players data/acb_jugadores.html

   Add --totals if the tables hold season totals instead of per-game averages.

2) A team game log (one row per team and game, with a game id column):

    python pipelines/import_spanish_stats.py --league primera-feb --gamelog data/feb_partidos.xlsx

Output: data/<league>_teams.csv (and data/<league>_players.csv), ready to load
in the app with "Your files" > "App template (CSV)". The data/ folder is in
.gitignore, so these files never reach GitHub.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from explorer import spanish  # noqa: E402
from explorer.sources import PLAYER_ID, STAT_COLUMNS  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--league", default="acb", help="Used in the output file names (acb, primera-feb...).")
    ap.add_argument("--teams", help="Own team stats (HTML, XLSX or CSV).")
    ap.add_argument("--opponents", help="Opponents' stats against each team (rivales).")
    ap.add_argument("--players", help="Player stats (optional).")
    ap.add_argument("--gamelog", help="Team game log: one row per team and game, with a game id.")
    ap.add_argument("--totals", action="store_true", help="Tables hold season totals, not averages.")
    args = ap.parse_args()

    if args.gamelog:
        teams, opp, players = spanish.from_game_log(args.gamelog, args.players)
    elif args.teams and args.opponents:
        teams, opp, players = spanish.from_season_tables(args.teams, args.opponents, args.players,
                                                         values="totals" if args.totals else "averages")
    else:
        ap.error("Give --gamelog, or both --teams and --opponents.")

    out = Path("data")
    out.mkdir(exist_ok=True)
    spanish.to_template(teams, opp).round(3).to_csv(out / f"{args.league}_teams.csv", index=False)
    print(f"Saved {len(teams)} teams to {out / f'{args.league}_teams.csv'}")
    if players is not None:
        cols = [c for c in PLAYER_ID + STAT_COLUMNS + ["photo_url", "crest_url"] if c in players.columns]
        players[cols].round(3).to_csv(out / f"{args.league}_players.csv", index=False)
        print(f"Saved {len(players)} players to {out / f'{args.league}_players.csv'}")


if __name__ == "__main__":
    main()
