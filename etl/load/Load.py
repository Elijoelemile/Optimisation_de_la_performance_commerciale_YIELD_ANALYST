"""
Load.py — Étape « L » (Load) de l'ETL NG Travel
================================================

Rôle : prendre la base transformée qui se trouve EN MÉMOIRE (le DataFrame
produit par Transformation) et l'écrire dans la zone raffinée : le
« Data Warehouse ». On peut RENOMMER la base à l'enregistrement, afin de
distinguer facilement les différentes bases stockées dans l'entrepôt.

Principe ETL : le Data Warehouse stocke la donnée PROPRE et prête à l'analyse.

Utilisation en import (dans le pipeline)
----------------------------------------
    from Load import load
    load(df, data_warehouse="Data Warehouse", nom="ng_travel_2025_2026")

Utilisation en ligne de commande (à lancer depuis la RACINE du projet, avec -m)
--------------------------------------------------------------------------------
Load a besoin d'un DataFrame en mémoire ; en pratique il s'appelle depuis le
pipeline. Lancé seul, il peut recharger un fichier du Data Lake pour dépanner :
    python -m etl.load.Load --nom ng_travel_2025_2026 --depuis-lake "Data Lake"
"""

from __future__ import annotations
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# Rend les éventuels print() robustes aux consoles dont l'encodage ne
# supporte pas les accents (ex. cp1251) — évite un crash quand `load()` est
# appelé depuis un process dont le stdout n'est pas UTF-8 (ex. app Streamlit
# lancée sur une machine dont la console n'est pas en UTF-8).
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

try:
    from logger_config import get_logger
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # racine du projet
    from logger_config import get_logger

log = get_logger(__name__)


def _nom_sur(nom: str) -> str:
    """Nettoie le nom de fichier fourni (évite espaces/caractères gênants)."""
    nom = nom.strip().replace(" ", "_")
    nom = re.sub(r"[^0-9A-Za-zÀ-ÿ_\-.]", "", nom)
    return nom or "base"


def load(
    df: pd.DataFrame,
    data_warehouse: str = "Data Warehouse",
    nom: str = "ng_travel",
    formats=("parquet", "csv"),
    horodater: bool = False,
) -> list[Path]:
    """
    Écrit la base transformée (en mémoire) dans le Data Warehouse.

    Paramètres
    ----------
    df             : DataFrame transformé (variable mémoire venant de Transformation).
    data_warehouse : dossier de destination (créé s'il n'existe pas).
    nom            : nom de base pour distinguer les jeux de données dans l'entrepôt.
    formats        : formats de sortie (parquet et/ou csv).
    horodater      : si True, suffixe le nom avec la date+heure (versioning).

    Retourne la liste des chemins écrits.
    """
    if df is None or len(df) == 0:
        message = "Aucune donnée à charger : le DataFrame mémoire est vide."
        log.error(message)
        raise ValueError(message)

    dossier = Path(data_warehouse).expanduser()
    dossier.mkdir(parents=True, exist_ok=True)

    nom = _nom_sur(nom)
    if horodater:
        nom = f"{nom}_{datetime.now():%Y%m%d_%H%M%S}"

    ecrits: list[Path] = []
    for fmt in formats:
        if fmt == "parquet":
            cible = dossier / f"{nom}.parquet"
            df.to_parquet(cible, index=False)
        elif fmt == "csv":
            cible = dossier / f"{nom}.csv"
            df.to_csv(cible, index=False, encoding="utf-8-sig")
        else:
            log.warning("Format ignoré (non géré) : %s", fmt)
            continue
        ecrits.append(cible)
        log.info("Écrit : %s (%.0f Ko)", cible, cible.stat().st_size / 1024)

    log.info("%d lignes chargées dans « %s » sous le nom « %s ».", len(df), dossier, nom)
    return ecrits


def _cli():
    parser = argparse.ArgumentParser(
        description="Load ETL — écrit la base transformée dans le Data Warehouse."
    )
    parser.add_argument("--nom", default="ng_travel",
                        help="Nom de la base dans le Data Warehouse.")
    parser.add_argument("--data-warehouse", default="Data Warehouse")
    parser.add_argument("--formats", nargs="+", default=["parquet", "csv"],
                        choices=["parquet", "csv"])
    parser.add_argument("--horodater", action="store_true",
                        help="Ajoute un horodatage au nom (versioning).")
    parser.add_argument("--depuis-lake", default=None,
                        help="Dépannage : si aucun DataFrame mémoire, "
                             "retransforme depuis ce Data Lake avant d'écrire.")
    args = parser.parse_args()

    # Lancé seul, Load n'a pas de DataFrame mémoire hérité d'un autre processus.
    # Option de dépannage : on retransforme à la volée depuis le Data Lake.
    if args.depuis_lake:
        from etl.transformation.Transformation import transformation
        df = transformation(args.depuis_lake)
        load(df, args.data_warehouse, args.nom, tuple(args.formats), args.horodater)
    else:
        log.warning("Aucun DataFrame en mémoire (processus isolé). "
                    "Utilise pipeline_orchestrator.py pour l'enchaînement E→T→L en mémoire, "
                    "ou relance avec --depuis-lake \"Data Lake\" pour dépanner.")


if __name__ == "__main__":
    _cli()
