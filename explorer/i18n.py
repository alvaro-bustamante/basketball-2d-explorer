"""Interface texts in English and Spanish.

t(key) returns the text in the current language (falls back to English, then to the key).
Metric names and help texts are written in English in metrics.py and translated here
with tm() / th(), so the metric registry stays readable.
"""
from __future__ import annotations

import re

LANGS = {"English": "en", "Español": "es"}
_lang = "en"


def set_lang(code: str):
    global _lang
    _lang = code if code in ("en", "es") else "en"


def lang() -> str:
    return _lang


def t(key: str, **kw) -> str:
    entry = TEXTS.get(key)
    text = key if entry is None else (entry.get(_lang) or entry.get("en") or key)
    return text.format(**kw) if kw else text


def tm(label: str) -> str:
    """Metric name in the current language."""
    return label if _lang == "en" else METRICS_ES.get(label, (label, ""))[0]


def th(label: str, help_en: str) -> str:
    """Metric help text in the current language."""
    if _lang == "en":
        return help_en
    es = METRICS_ES.get(label, ("", ""))[1]
    return es or help_en


_KEEP = {"EFG%": "eFG%", "XG": "xG"}


def smart_upper(text: str) -> str:
    return re.sub(r"\b(EFG%|XG)", lambda m: _KEEP[m.group(1)], str(text).upper())


TEXTS: dict[str, dict[str, str]] = {
    "language": {"en": "Language", "es": "Idioma"},
    "data_source": {"en": "Data source", "es": "Fuente de datos"},
    "src_el": {"en": "EuroLeague API", "es": "API EuroLeague"},
    "src_ec": {"en": "EuroCup API", "es": "API EuroCup"},
    "src_nba": {"en": "NBA (stats.nba.com)", "es": "NBA (stats.nba.com)"},
    "src_acb": {"en": "Liga Endesa ACB", "es": "Liga Endesa ACB"},
    "src_feb": {"en": "Primera FEB", "es": "Primera FEB"},
    "src_feb2": {"en": "Segunda FEB", "es": "Segunda FEB"},
    "src_files": {"en": "Your files (any league)", "es": "Tus archivos (cualquier liga)"},
    "src_demo": {"en": "Demo (fictional)", "es": "Demo (ficticio)"},
    "season": {"en": "Season", "es": "Temporada"},
    "phase": {"en": "Phase", "es": "Fase"},
    "season_type": {"en": "Season type", "es": "Tipo de temporada"},
    "league_names": {"en": "League (names and colors)", "es": "Liga (nombres y colores)"},
    "file_format": {"en": "File format", "es": "Formato de archivo"},
    "ff_saved": {"en": "Saved in data/ folder", "es": "Guardados en la carpeta data/"},
    "ff_template": {"en": "App template (CSV)", "es": "Plantilla de la app (CSV)"},
    "ff_tables": {"en": "Season tables (Spanish or English)", "es": "Tablas de temporada (español o inglés)"},
    "ff_log": {"en": "Team game log", "es": "Registro de partidos por equipo"},
    "ff_help": {"en": ("Season tables: a page saved from the league website (HTML), Excel or CSV, with Spanish "
                       "headers (PTS, T2, T3, TL, RO, RD, AS, BR, BP, VAL) or English ones. Team game log: one row "
                       "per team and game, with a game id."),
                "es": ("Tablas de temporada: una página guardada de la web de la liga (HTML), Excel o CSV, con "
                       "cabeceras en español (PTS, T2, T3, TL, RO, RD, AS, BR, BP, VAL) o en inglés. Registro de "
                       "partidos: una fila por equipo y partido, con un identificador de partido.")},
    "dataset": {"en": "Dataset", "es": "Conjunto de datos"},
    "dataset_help": {"en": "CSV files in data/ named <name>_teams.csv (and <name>_players.csv).",
                     "es": "Archivos CSV en data/ llamados <nombre>_teams.csv (y <nombre>_players.csv)."},
    "team_template": {"en": "Team template", "es": "Plantilla de equipos"},
    "player_template": {"en": "Player template", "es": "Plantilla de jugadores"},
    "template_note": {"en": "Shots are written as MADE and MISSED (mutually exclusive): fg2m / fg2x, fg3m / fg3x, ftm / ftx.",
                      "es": "Los tiros van como ANOTADOS y FALLADOS (sucesos excluyentes): fg2m / fg2x, fg3m / fg3x, ftm / ftx."},
    "team_csv": {"en": "Team CSV", "es": "CSV de equipos"},
    "team_own": {"en": "Team stats (own)", "es": "Estadísticas de equipo (propias)"},
    "team_opp": {"en": "Opponent stats", "es": "Estadísticas de los rivales"},
    "values_are": {"en": "Values are", "es": "Los valores son"},
    "averages": {"en": "Per-game averages", "es": "Medias por partido"},
    "totals": {"en": "Season totals", "es": "Totales de temporada"},
    "game_log": {"en": "Team game log", "es": "Registro de partidos"},
    "player_stats": {"en": "Player stats (optional)", "es": "Estadísticas de jugadores (opcional)"},
    "compare": {"en": "Compare", "es": "Comparar"},
    "teams": {"en": "Teams", "es": "Equipos"},
    "players": {"en": "Players", "es": "Jugadores"},
    "no_local": {"en": "No {source} data yet. Create it with {how}; files are saved in data/.",
                 "es": "Aún no hay datos de {source}. Créalos con {how}; los archivos se guardan en data/."},
    "upload_first": {"en": "Upload your files in the sidebar to start. Season tables need two files: "
                           "your teams' own stats and their opponents' stats.",
                     "es": "Sube tus archivos en la barra lateral para empezar. Las tablas de temporada necesitan dos "
                           "archivos: las estadísticas propias de los equipos y las de sus rivales."},
    "no_data": {"en": "No data for this selection yet. Try the previous season.",
                "es": "Aún no hay datos para esta selección. Prueba con la temporada anterior."},
    "no_players": {"en": "No player data for this source.", "es": "No hay datos de jugadores en esta fuente."},
    "min_mpg": {"en": "Min. minutes per game", "es": "Mín. minutos por partido"},
    "min_games": {"en": "Min. games", "es": "Mín. partidos"},
    "min_games_help": {"en": "Up to {n} games played in this selection.", "es": "Hasta {n} partidos jugados en esta selección."},
    "teams_filter": {"en": "Teams", "es": "Equipos"},
    "all_teams": {"en": "All teams", "es": "Todos los equipos"},
    "too_few": {"en": "Too few players with these filters.", "es": "Muy pocos jugadores con estos filtros."},
    "display": {"en": "Display", "es": "Visualización"},
    "labels_teams": {"en": "Team labels", "es": "Etiquetas de equipo"},
    "labels_players": {"en": "Player labels", "es": "Etiquetas de jugador"},
    "labels_help": {"en": "Photos and crests appear when the data source provides them.",
                    "es": "Las fotos y escudos aparecen cuando la fuente de datos los incluye."},
    "lab_short": {"en": "Short name", "es": "Nombre corto"},
    "lab_full": {"en": "Full name", "es": "Nombre completo"},
    "lab_code": {"en": "Code", "es": "Código"},
    "lab_crest": {"en": "Crest", "es": "Escudo"},
    "lab_photo": {"en": "Photo", "es": "Foto"},
    "lab_team_crest": {"en": "Team crest", "es": "Escudo del equipo"},
    "lab_none": {"en": "None", "es": "Ninguna"},
    "ellipses": {"en": "Uncertainty ellipses", "es": "Elipses de incertidumbre"},
    "ellipses_help": {"en": "'Choose' lets you pick which teams or players get an ellipse.",
                      "es": "'Elegir' permite decidir qué equipos o jugadores llevan elipse."},
    "ell_all": {"en": "All", "es": "Todas"},
    "ell_choose": {"en": "Choose", "es": "Elegir"},
    "ell_none": {"en": "None", "es": "Ninguna"},
    "ellipses_for": {"en": "Show ellipses for", "es": "Mostrar elipses de"},
    "ellipses_for_ph": {"en": "Pick teams or players", "es": "Elige equipos o jugadores"},
    "cred_level": {"en": "Credible level", "es": "Nivel de credibilidad"},
    "points_show": {"en": "Points show", "es": "Los puntos muestran"},
    "observed": {"en": "Observed", "es": "Observado"},
    "adjusted": {"en": "Bayes-adjusted", "es": "Ajustado (Bayes)"},
    "arrow": {"en": "Arrow observed → adjusted", "es": "Flecha observado → ajustado"},
    "medians": {"en": "League medians", "es": "Medianas de la liga"},
    "quadrants": {"en": "Quadrant legend", "es": "Leyenda por cuadrantes"},
    "leaders": {"en": "Top 3 / bottom 3", "es": "Top 3 / últimos 3"},
    "round_label": {"en": "Round label", "es": "Etiqueta de jornada"},
    "round_help": {"en": "Worked out from games played. Edit it, or leave it empty to hide it.",
                   "es": "Se calcula con los partidos jugados. Edítala o déjala vacía para ocultarla."},
    "round_word": {"en": "ROUND", "es": "JORNADA"},
    "game_word": {"en": "GAME", "es": "PARTIDO"},
    "playoffs": {"en": "PLAYOFFS", "es": "PLAYOFFS"},
    "img_failed": {"en": "Images could not be downloaded: showing dots instead.",
                   "es": "No se pudieron descargar las imágenes: se muestran puntos."},
    "img_none": {"en": "No images in this data source: showing names instead.",
                 "es": "Esta fuente no tiene imágenes: se muestran nombres."},
    "img_prep": {"en": "Preparing images (crests / face-cropped photos)…",
                 "es": "Preparando imágenes (escudos / fotos recortadas)…"},
    "caption": {"en": "{context} · season totals · uncertainty from an empirical-Bayes model",
                "es": "{context} · totales de temporada · incertidumbre con un modelo bayesiano empírico"},
    "x_axis": {"en": "X axis", "es": "Eje X"},
    "y_axis": {"en": "Y axis", "es": "Eje Y"},
    "reverse_x": {"en": "Reverse X (better to the right)", "es": "Invertir X (mejor a la derecha)"},
    "reverse_y": {"en": "Reverse Y (better at the top)", "es": "Invertir Y (mejor arriba)"},
    "highlight": {"en": "Highlight", "es": "Destacar"},
    "adj": {"en": "adj.", "es": "aj."},
    "ci95": {"en": "95% CI", "es": "IC 95%"},
    "name": {"en": "Name", "es": "Nombre"},
    "team": {"en": "Team", "es": "Equipo"},
    "mpg": {"en": "MPG", "es": "MPP"},
    "download": {"en": "Download this view (CSV)", "es": "Descargar esta vista (CSV)"},
    "method": {"en": "Method: what the ellipses mean", "es": "Método: qué significan las elipses"},
    "method_text": {
        "en": ("**Why adjust?** A player who shoots 8/10 from three has not proven he is an 80% shooter. "
               "Small samples produce extreme values by chance. The app estimates each metric with an "
               "**empirical-Bayes** model whose prior is the league itself:\n\n"
               "* **Rates built from counts** (3P%, eFG%, TOV%, USG%…): Beta-Binomial model.\n"
               "* **Continuous metrics** (ratings, per-game stats, Game Score, ratios, entropies): Normal-Normal "
               "model with an approximate standard error.\n\n"
               "**Reading the chart.** The dot is the observed value; the ellipse ({level} credible region) is "
               "centred on the adjusted value. **Overlapping ellipses = the data cannot separate them yet.**\n\n"
               "**Shots** are stored as made and missed (mutually exclusive events); attempts are only computed "
               "inside formulas that need them."),
        "es": ("**¿Por qué ajustar?** Un jugador que mete 8 de 10 triples no ha demostrado ser un tirador del 80%. "
               "Las muestras pequeñas producen valores extremos por azar. La app estima cada métrica con un modelo "
               "**bayesiano empírico** cuyo prior es la propia liga:\n\n"
               "* **Tasas a partir de conteos** (3P%, eFG%, TOV%, USG%…): modelo Beta-Binomial.\n"
               "* **Métricas continuas** (ratings, valores por partido, Game Score, cocientes, entropías): modelo "
               "Normal-Normal con un error estándar aproximado.\n\n"
               "**Cómo leer el gráfico.** El punto es el valor observado; la elipse (región creíble del {level}) está "
               "centrada en el valor ajustado. **Elipses que se solapan = los datos aún no permiten separarlos.**\n\n"
               "**Los tiros** se guardan como anotados y fallados (sucesos excluyentes); los intentados solo se "
               "calculan dentro de las fórmulas que los necesitan.")},
    "built_by": {"en": "Built by Álvaro Bustamante-Sánchez, PhD", "es": "Creado por Álvaro Bustamante-Sánchez, PhD"},
    "w_good": {"en": "GOOD", "es": "MEJOR"},
    "w_bad": {"en": "BAD", "es": "PEOR"},
    "w_high": {"en": "HIGH", "es": "MÁS"},
    "w_low": {"en": "LOW", "es": "MENOS"},
    "tag_best": {"en": "Best", "es": "Mejores"},
    "tag_worst": {"en": "Worst", "es": "Peores"},
    "tag_highest": {"en": "Highest", "es": "Más altos"},
    "tag_lowest": {"en": "Lowest", "es": "Más bajos"},
    "export_obs": {"en": "Observed values", "es": "Valores observados"},
    "export_adj": {"en": "Bayes-adjusted values", "es": "Valores ajustados (Bayes)"},
    "export_ell": {"en": "ellipses: {level} credible region", "es": "elipses: región creíble del {level}"},
    "demo_context": {"en": "Demo data (fictional teams and players)", "es": "Datos de demo (equipos y jugadores ficticios)"},
}

# English metric name -> (Spanish name, Spanish help). Help texts left empty fall back to English.
METRICS_ES: dict[str, tuple[str, str]] = {
    "Offensive rating": ("Rating ofensivo", "Puntos anotados por 100 posesiones."),
    "Defensive rating": ("Rating defensivo", "Puntos recibidos por 100 posesiones."),
    "Net rating": ("Rating neto", "Rating ofensivo menos rating defensivo."),
    "Pace": ("Ritmo", "Posesiones por partido (40 min FIBA, 48 min NBA)."),
    "eFG%": ("eFG%", "Tiro de campo efectivo: un triple cuenta como 1,5 canastas."),
    "TOV%": ("TOV%", "Pérdidas por posesión."),
    "ORB%": ("ORB%", "Porcentaje de rebotes ofensivos disponibles que se capturan."),
    "DRB%": ("DRB%", "Porcentaje de rebotes defensivos disponibles que se capturan."),
    "TRB%": ("TRB%", "Porcentaje de todos los rebotes disponibles que se capturan."),
    "FT rate": ("Ratio TL anotados", "Tiros libres anotados por tiro de campo."),
    "FTA rate": ("Ratio TL intentados", "Tiros libres intentados por tiro de campo: capacidad de provocar faltas."),
    "3PA rate": ("Ratio de triples", "Proporción de tiros de campo que son triples."),
    "3P%": ("3P%", "Porcentaje de triples."),
    "2P%": ("2P%", "Porcentaje de tiros de dos."),
    "FT%": ("TL%", "Porcentaje de tiros libres."),
    "Ball movement (AST/FGM)": ("Circulación (AST/canastas)", "Proporción de canastas que son asistidas."),
    "Opp eFG%": ("eFG% rival", "Tiro de campo efectivo del rival."),
    "Opp TOV%": ("TOV% rival", "Pérdidas forzadas por posesión."),
    "Opp 3P%": ("3P% rival", "Porcentaje de triples del rival."),
    "TS%": ("TS%", "Tiro verdadero: puntos por posesión de tiro (dos, triples y libres)."),
    "Opp FT rate": ("Ratio TL rival", "Tiros libres concedidos por tiro de campo rival."),
    "STL%": ("STL%", "Robos por posesión rival."),
    "BLK%": ("BLK%", "Tapones por tiro de dos rival."),
    "AST/TOV": ("AST/TOV", "Asistencias por pérdida."),
    "PPS": ("Puntos por tiro (PPS)", "Puntos por tiro de campo intentado."),
    "Shot diet entropy": ("Entropía de la dieta de tiro",
                          "Diversidad entre tiros de 2, triples y viajes a la línea (0 = un solo tipo, 1 = reparto "
                          "uniforme). Con incertidumbre Dirichlet-multinomial."),
    "Scoring balance entropy": ("Entropía del reparto de tiros",
                                "Lo repartido que está el tiro entre los jugadores (0 = uno lo tira todo, 1 = reparto "
                                "uniforme)."),
    "Points per game": ("Puntos por partido", ""),
    "Opp points per game": ("Puntos recibidos por partido", ""),
    "Minutes per game": ("Minutos por partido", ""),
    "Rebounds per game": ("Rebotes por partido", ""),
    "Assists per game": ("Asistencias por partido", ""),
    "Turnovers per game": ("Pérdidas por partido", ""),
    "Steals per game": ("Robos por partido", ""),
    "Blocks per game": ("Tapones por partido", ""),
    "PIR per game": ("Valoración por partido", "Valoración (PIR) de la EuroLeague."),
    "Points per 40": ("Puntos por 40", ""),
    "Rebounds per 40": ("Rebotes por 40", ""),
    "Assists per 40": ("Asistencias por 40", ""),
    "USG%": ("USG%", "Proporción de posesiones del equipo que usa el jugador mientras está en pista."),
    "AST%": ("AST%", "Proporción de canastas de los compañeros que asiste mientras está en pista."),
    "HOB": ("HOB (manos en la canasta)",
            "Canastas en las que participa (anotando o asistiendo) sobre las canastas del equipo con él en pista."),
    "Game Score per 40": ("Game Score por 40", "Game Score de Hollinger por 40 minutos: producción global."),
    "PIR per 40": ("Valoración por 40", ""),
    "Stocks per 40": ("Robos + tapones por 40", "Actividad defensiva."),
}
