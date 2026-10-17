"""FICTIONAL demo data to try the app offline.

Invented teams and players ("Team A", "Player A1"...). Do not publish:
they only show how the app works.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

STAT_COLS = ["games", "min", "pts", "fg2m", "fg2a", "fg3m", "fg3a", "ftm", "fta",
             "orb", "drb", "trb", "ast", "stl", "tov", "blk", "pf", "pir"]


def _player_line(rng, minutes, profile):
    m = minutes / 30
    if profile == "base":
        fg2a, fg3a, fta = 5 * m, 4.5 * m, 2.5 * m
        orb, drb, ast = 0.3 * m, 2.0 * m, 5.5 * m
    elif profile == "interior":
        fg2a, fg3a, fta = 7 * m, 0.6 * m, 3.5 * m
        orb, drb, ast = 2.2 * m, 4.5 * m, 1.2 * m
    else:
        fg2a, fg3a, fta = 4.5 * m, 5 * m, 2 * m
        orb, drb, ast = 0.7 * m, 2.8 * m, 2.0 * m
    fg2a, fg3a, fta = (v * rng.uniform(0.75, 1.25) for v in (fg2a, fg3a, fta))
    fg2m = fg2a * rng.uniform(0.48, 0.62)
    fg3m = fg3a * rng.uniform(0.30, 0.42)
    ftm = fta * rng.uniform(0.68, 0.88)
    tov = (1.2 + 0.25 * ast) * rng.uniform(0.8, 1.2)
    stl = 0.9 * m * rng.uniform(0.6, 1.4)
    blk = (0.9 if profile == "interior" else 0.2) * m * rng.uniform(0.5, 1.5)
    pf = 2.4 * m * rng.uniform(0.8, 1.2)
    pts = 2 * fg2m + 3 * fg3m + ftm
    trb = orb + drb
    pir = pts + trb + ast + stl + blk - (fg2a - fg2m) - (fg3a - fg3m) - (fta - ftm) - tov - pf
    return dict(games=30, min=minutes, pts=pts, fg2m=fg2m, fg2a=fg2a, fg3m=fg3m, fg3a=fg3a,
                ftm=ftm, fta=fta, orb=orb, drb=drb, trb=trb, ast=ast, stl=stl, tov=tov,
                blk=blk, pf=pf, pir=pir)


def demo_data(n_teams: int = 18, seed: int = 7):
    rng = np.random.default_rng(seed)
    letters = [chr(65 + i) for i in range(n_teams)]
    profiles = ["base", "base", "exterior", "exterior", "exterior", "exterior",
                "interior", "interior", "interior", "interior", "exterior", "base"]
    players, teams = [], []
    for L in letters:
        mins = np.array(sorted(rng.uniform(6, 30, 12), reverse=True))
        mins = mins / mins.sum() * 200
        rows = []
        for j, (mn, prof) in enumerate(zip(mins, rng.permutation(profiles))):
            line = _player_line(rng, mn, prof)
            line.update(player_code=f"P{L}{j + 1}", player_name=f"PLAYER {L}{j + 1}",
                        team_code=f"E{L}", team_name=f"Team {L}", crest_url=None)
            rows.append(line)
        players += rows
        tot = pd.DataFrame(rows)[STAT_COLS].sum()
        tot["games"] = 30
        teams.append(dict(team_code=f"E{L}", team_name=f"Team {L}", crest_url=None, **tot.to_dict()))

    teams_df = pd.DataFrame(teams)
    # Opponents: other teams' lines with some noise.
    opp = teams_df.copy()
    for c in STAT_COLS:
        if c in ("games", "min"):
            continue
        opp[c] = teams_df[c].sample(frac=1, random_state=seed).values * rng.uniform(0.92, 1.08, n_teams)
    return teams_df, opp, pd.DataFrame(players)
