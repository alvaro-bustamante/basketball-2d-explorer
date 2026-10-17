"""Colores de equipo para gráficos y stories.

Los códigos son los de la EuroLeague. Si un equipo no está aquí, se usa el
color por defecto y se puede cambiar desde la app con el selector de color.
"""
from __future__ import annotations

DEFAULT = ("#E8E8E8", "#9AA0A6")

# (color principal, color secundario)
TEAM_COLORS = {
    "MAD": ("#FFFFFF", "#FEBE10"),  # Real Madrid
    "BAR": ("#A50044", "#004D98"),  # FC Barcelona
    "BAS": ("#C8102E", "#0B2A5B"),  # Baskonia
    "VAL": ("#F47920", "#000000"),  # Valencia Basket
    "PAN": ("#007A3D", "#FFFFFF"),  # Panathinaikos
    "OLY": ("#E2001A", "#FFFFFF"),  # Olympiacos
    "ULK": ("#FFED00", "#002D72"),  # Fenerbahçe
    "IST": ("#003A70", "#E30613"),  # Anadolu Efes
    "MCO": ("#E30613", "#FFFFFF"),  # AS Monaco
    "TEL": ("#FFD200", "#003DA5"),  # Maccabi Tel Aviv
    "HTA": ("#E4002B", "#FFFFFF"),  # Hapoel Tel Aviv
    "MIL": ("#E4002B", "#FFFFFF"),  # Olimpia Milano
    "VIR": ("#000000", "#FFFFFF"),  # Virtus Bologna
    "PAR": ("#000000", "#FFFFFF"),  # Partizan
    "RED": ("#E30613", "#FFFFFF"),  # Crvena Zvezda
    "ZAL": ("#007A33", "#FFFFFF"),  # Zalgiris
    "MUN": ("#DC052D", "#0066B2"),  # Bayern Munich
    "ASV": ("#000000", "#C8102E"),  # ASVEL
    "PRS": ("#1D1D1B", "#E2001A"),  # Paris Basketball
    "DUB": ("#C8A24A", "#000000"),  # Dubai Basketball
}


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def accent_for(team_code: str, background: str = "#0F1115") -> str:
    """Color del equipo que mejor se lee sobre el fondo de la story."""
    primary, secondary = TEAM_COLORS.get(str(team_code).upper(), DEFAULT)
    # Primero un color con personalidad (ni blanco ni negro) que se lea bien.
    for c in (primary, secondary):
        if contrast(c, background) >= 3 and _luminance(c) < 0.85:
            return c
    for c in (primary, secondary):
        if contrast(c, background) >= 3:
            return c
    return "#FFFFFF"


def chart_color(team_code: str) -> str:
    """Color para gráficos sobre fondo claro u oscuro (evita blanco puro)."""
    primary, secondary = TEAM_COLORS.get(str(team_code).upper(), DEFAULT)
    for c in (primary, secondary):
        if 0.03 < _luminance(c) < 0.8:
            return c
    return "#6B7280"
