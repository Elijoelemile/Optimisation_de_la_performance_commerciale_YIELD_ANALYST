"""
pipeline_orchestrator.py — Orchestrateur ETL NG Travel (E → T → L)
====================================================================

Rôle : ORCHESTRER les trois briques indépendantes du package `etl/`
(extraction, transformation, load) en une seule exécution. C'est ici que la
« variable mémoire » prend tout son sens : les trois étapes s'exécutent dans
le MÊME processus Python, donc le DataFrame produit par Transformation est
passé DIRECTEMENT à Load, sans jamais toucher le disque entre les deux.

    1. Extraction    : source (n'importe où) ──► Data Lake      (brut)
    2. Transformation: Data Lake ──► DataFrame EN MÉMOIRE       (nettoyé/enrichi)
    3. Load          : DataFrame mémoire ──► Data Warehouse     (prêt à l'analyse)

Exemple (à lancer depuis la RACINE du projet, avec -m) :
--------------------------------------------------------
    python -m pipeline_orchestrator.pipeline_orchestrator "/Users/moi/Downloads/base_de_données_NG_Travel.xlsx" \
        --nom ng_travel_saison_2025_2026

    # Ou en cherchant le fichier dans un dossier :
    python -m pipeline_orchestrator.pipeline_orchestrator "/Users/moi/Downloads" --pattern NG_Travel \
        --nom ng_travel_v1
"""

from __future__ import annotations
import argparse
from pathlib import Path

try:
    from logger_config import get_logger, log_historique
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # racine du projet
    from logger_config import get_logger, log_historique

from etl.extraction.Extraction import extraction
from etl.transformation.Transformation import transformation
from etl.load.Load import load

log = get_logger(__name__)


def executer_pipeline(
    source: str,
    nom_warehouse: str = "ng_travel",
    data_lake: str = "Data Lake",
    data_warehouse: str = "Data Warehouse",
    pattern: str = "",
    formats=("parquet", "csv"),
    horodater: bool = False,
):
    """Enchaîne les trois étapes ETL en gardant la donnée en mémoire entre T et L."""
    log.info("=== Démarrage du pipeline ETL NG Travel (source=%s, nom=%s) ===",
              source, nom_warehouse)
    log_historique(f"Orchestration démarrée — source={source}, nom={nom_warehouse}")
    try:
        # 1) EXTRACT : dépose le brut dans le Data Lake
        extraction(source, data_lake=data_lake, pattern=pattern)

        # 2) TRANSFORM : renvoie un DataFrame conservé en mémoire (RAM)
        df = transformation(data_lake=data_lake)          # <── variable mémoire

        # 3) LOAD : écrit ce DataFrame mémoire dans le Data Warehouse (nom au choix)
        load(df, data_warehouse=data_warehouse, nom=nom_warehouse,
             formats=formats, horodater=horodater)        # <── même variable mémoire
    except Exception as e:
        log.exception("Échec du pipeline ETL — voir la trace ci-dessus.")
        log_historique(f"Orchestration ÉCHOUÉE — source={source}, nom={nom_warehouse} : {e}")
        raise

    log.info("=== Pipeline ETL terminé avec succès (%d lignes) ===", len(df))
    log_historique(f"Orchestration terminée avec SUCCÈS — {len(df)} lignes, nom={nom_warehouse}")
    return df


def _cli():
    parser = argparse.ArgumentParser(description="Orchestrateur ETL NG Travel (E→T→L).")
    parser.add_argument("source", help="Fichier source OU dossier à explorer.")
    parser.add_argument("--nom", default="ng_travel",
                        help="Nom de la base dans le Data Warehouse.")
    parser.add_argument("--data-lake", default="Data Lake")
    parser.add_argument("--data-warehouse", default="Data Warehouse")
    parser.add_argument("--pattern", default="",
                        help="Filtre nom si la source est un dossier.")
    parser.add_argument("--formats", nargs="+", default=["parquet", "csv"],
                        choices=["parquet", "csv"])
    parser.add_argument("--horodater", action="store_true")
    args = parser.parse_args()

    executer_pipeline(
        source=args.source,
        nom_warehouse=args.nom,
        data_lake=args.data_lake,
        data_warehouse=args.data_warehouse,
        pattern=args.pattern,
        formats=tuple(args.formats),
        horodater=args.horodater,
    )


if __name__ == "__main__":
    _cli()
