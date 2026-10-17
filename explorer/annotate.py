"""Self-explanatory chart annotations: quadrant legend and leaderboards."""
from __future__ import annotations

import numpy as np
import pandas as pd

GOOD = "#2E9E44"
BAD = "#D64545"
NEUTRAL = "#8A8F98"


def _side_status(better: str | None, high_side: bool) -> tuple[str, str, str]:
    """Return (arrow, color, word) for the side of an axis.

    high_side: True when this side of the axis holds the higher values.
    """
    if better is None:
        return ("▲", NEUTRAL, "high") if high_side else ("▼", NEUTRAL, "low")
    good = high_side if better == "high" else not high_side
    return ("▲", GOOD, "good") if good else ("▼", BAD, "bad")


def quadrant_labels(mx, my, inv_x: bool, inv_y: bool) -> dict:
    """Text for each corner, e.g. {'top_right': [(arrow, color, 'good Offensive rating'), ...]}."""
    out = {}
    for vert in ("top", "bottom"):
        for horiz in ("left", "right"):
            x_high = (horiz == "right") != inv_x   # reversed axis puts low values on the right
            y_high = (vert == "top") != inv_y
            ax, cx, wx = _side_status(mx.better, x_high)
            ay, cy, wy = _side_status(my.better, y_high)
            out[f"{vert}_{horiz}"] = [(ax, cx, f"{wx} {mx.label}"), (ay, cy, f"{wy} {my.label}")]
    return out


def quadrant_html(lines) -> str:  # kept for backwards compatibility
    return "<br>".join(f"<span style='color:{c}'>{a}</span> {t}" for a, c, t in lines)


def leaders(values: pd.Series, names: pd.Series, metric, n: int = 3, fmt: str = "{:.1f}") -> dict:
    """Top and bottom n entities for a metric, respecting what 'better' means."""
    s = pd.Series(np.asarray(values, float), index=names.values).dropna()
    if s.empty:
        return {}
    if metric.better == "low":
        best, worst = s.nsmallest(n), s.nlargest(n)
        tags = ("Best", "Worst")
    elif metric.better == "high":
        best, worst = s.nlargest(n), s.nsmallest(n)
        tags = ("Best", "Worst")
    else:
        best, worst = s.nlargest(n), s.nsmallest(n)
        tags = ("Highest", "Lowest")
    as_list = lambda ser: [(name, fmt.format(v)) for name, v in ser.items()]  # noqa: E731
    return {"label": metric.label, "top_tag": tags[0], "bottom_tag": tags[1],
            "top": as_list(best), "bottom": as_list(worst)}


def leaders_html(board: dict) -> str:
    if not board:
        return ""
    top = " · ".join(f"{i}. {n} {v}" for i, (n, v) in enumerate(board["top"], 1))
    bot = " · ".join(f"{i}. {n} {v}" for i, (n, v) in enumerate(board["bottom"], 1))
    neutral = board["top_tag"] == "Highest"
    c_top, c_bot = (NEUTRAL, NEUTRAL) if neutral else (GOOD, BAD)
    return (f"<b>{board['label']}</b>  <span style='color:{c_top}'>{board['top_tag']}</span>: {top}"
            f"<br><b>{board['label']}</b>  <span style='color:{c_bot}'>{board['bottom_tag']}</span>: {bot}")


# Condensed "scoreboard" font for badges; browsers fall back down the list.
BADGE_FONT = "Barlow Condensed, Bahnschrift SemiCondensed, Bahnschrift, Oswald, Arial Narrow, sans-serif"


def badge_fill(hex_color: str, alpha: float = 0.13) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def round_label(games_played: int, league: str = "", playoffs: bool = False) -> str:
    """'ROUND 7' from the games played so far (the leader in games played sets the round)."""
    if not games_played or games_played < 1:
        return ""
    if playoffs:
        return "PLAYOFFS"
    if league.upper() == "NBA":
        return f"GAME {games_played}"
    return f"ROUND {games_played}"
