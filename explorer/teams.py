"""Team colors and display names, per league.

EuroLeague codes come from the official API, which keeps some historical
codes (for example PAM for Valencia Basket, from the old Pamesa sponsorship).
Add or edit teams freely: unknown teams fall back to a neutral grey and to
the full name provided by the data source.
"""
from __future__ import annotations

DEFAULT = ("#E8E8E8", "#9AA0A6")

# league -> code -> (primary, secondary, short display name)
TEAMS = {
    "EUROLEAGUE": {
        "MAD": ("#FFFFFF", "#FEBE10", "Real Madrid"),
        "BAR": ("#A50044", "#004D98", "Barça"),
        "BAS": ("#C8102E", "#0B2A5B", "Baskonia"),
        "PAM": ("#F47920", "#000000", "Valencia Basket"),
        "VAL": ("#F47920", "#000000", "Valencia Basket"),
        "PAN": ("#007A3D", "#FFFFFF", "Panathinaikos"),
        "OLY": ("#E2001A", "#FFFFFF", "Olympiacos"),
        "ULK": ("#FFED00", "#002D72", "Fenerbahçe"),
        "IST": ("#003A70", "#E30613", "Anadolu Efes"),
        "MCO": ("#E30613", "#FFFFFF", "Monaco"),
        "TEL": ("#FFD200", "#003DA5", "Maccabi Tel Aviv"),
        "HTA": ("#E4002B", "#FFFFFF", "Hapoel Tel Aviv"),
        "MIL": ("#E4002B", "#FFFFFF", "Olimpia Milano"),
        "VIR": ("#000000", "#FFFFFF", "Virtus Bologna"),
        "PAR": ("#000000", "#FFFFFF", "Partizan"),
        "RED": ("#E30613", "#FFFFFF", "Crvena Zvezda"),
        "ZAL": ("#007A33", "#FFFFFF", "Žalgiris"),
        "MUN": ("#DC052D", "#0066B2", "Bayern Munich"),
        "ASV": ("#000000", "#C8102E", "ASVEL"),
        "PRS": ("#1D1D1B", "#E2001A", "Paris Basketball"),
        "DUB": ("#C8A24A", "#000000", "Dubai Basketball"),
    },
    "NBA": {
        "ATL": ("#E03A3E", "#C1D32F", "Hawks"), "BOS": ("#007A33", "#BA9653", "Celtics"),
        "BKN": ("#000000", "#777D84", "Nets"), "CHA": ("#1D1160", "#00788C", "Hornets"),
        "CHI": ("#CE1141", "#000000", "Bulls"), "CLE": ("#860038", "#FDBB30", "Cavaliers"),
        "DAL": ("#00538C", "#B8C4CA", "Mavericks"), "DEN": ("#0E2240", "#FEC524", "Nuggets"),
        "DET": ("#C8102E", "#1D42BA", "Pistons"), "GSW": ("#1D428A", "#FFC72C", "Warriors"),
        "HOU": ("#CE1141", "#000000", "Rockets"), "IND": ("#002D62", "#FDBB30", "Pacers"),
        "LAC": ("#C8102E", "#1D428A", "Clippers"), "LAL": ("#552583", "#FDB927", "Lakers"),
        "MEM": ("#5D76A9", "#12173F", "Grizzlies"), "MIA": ("#98002E", "#F9A01B", "Heat"),
        "MIL": ("#00471B", "#EEE1C6", "Bucks"), "MIN": ("#0C2340", "#78BE20", "Timberwolves"),
        "NOP": ("#0C2340", "#C8102E", "Pelicans"), "NYK": ("#006BB6", "#F58426", "Knicks"),
        "OKC": ("#007AC1", "#EF3B24", "Thunder"), "ORL": ("#0077C0", "#C4CED4", "Magic"),
        "PHI": ("#006BB6", "#ED174C", "76ers"), "PHX": ("#1D1160", "#E56020", "Suns"),
        "POR": ("#E03A3E", "#000000", "Trail Blazers"), "SAC": ("#5A2D81", "#63727A", "Kings"),
        "SAS": ("#C4CED4", "#000000", "Spurs"), "TOR": ("#CE1141", "#000000", "Raptors"),
        "UTA": ("#002B5C", "#F9A01B", "Jazz"), "WAS": ("#002B5C", "#E31837", "Wizards"),
    },
    # Add ACB codes here once you fix the codes used in your CSV files, e.g.
    # "ACB": {"RMB": ("#FFFFFF", "#FEBE10", "Real Madrid"), ...}
    "ACB": {},
}
# EuroCup and custom data reuse the EuroLeague table where codes overlap.
ALIASES = {"EUROCUP": "EUROLEAGUE", "CUSTOM": "EUROLEAGUE", "DEMO": "EUROLEAGUE"}


def _table(league: str) -> dict:
    league = league.upper()
    return TEAMS.get(league) or TEAMS.get(ALIASES.get(league, ""), {})


def short_name(code: str, full_name: str, league: str = "EUROLEAGUE") -> str:
    entry = _table(league).get(str(code).upper())
    return entry[2] if entry else str(full_name)


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def accent_for(team_code: str, background: str = "#0F1115", league: str = "EUROLEAGUE") -> str:
    """Team color that reads well on a dark background (stories)."""
    primary, secondary, *_ = _table(league).get(str(team_code).upper(), DEFAULT)
    for c in (primary, secondary):
        if contrast(c, background) >= 3 and _luminance(c) < 0.85:
            return c
    for c in (primary, secondary):
        if contrast(c, background) >= 3:
            return c
    return "#FFFFFF"


def chart_color(team_code: str, league: str = "EUROLEAGUE") -> str:
    """Color for charts on light or dark backgrounds (avoids pure white/black)."""
    primary, secondary, *_ = _table(league).get(str(team_code).upper(), DEFAULT)
    for c in (primary, secondary):
        if 0.03 < _luminance(c) < 0.8:
            return c
    return "#6B7280"
