"""
tache_quotidienne.py — Tâche planifiée quotidienne NG Travel (8h00)
=====================================================================

Rôle : rafraîchir le Data Warehouse — et sa copie publiée dans data/ — à
partir du fichier déjà présent dans le Data Lake, une fois par jour, sans
intervention manuelle.

Différence avec pipeline_orchestrator.py
-----------------------------------------
`pipeline_orchestrator.py` enchaîne Extraction → Transformation → Load à
partir d'une source EXTERNE (un nouveau fichier à copier dans le Data Lake).
Cette tâche-ci ne relance PAS l'extraction : il n'y a rien de nouveau à
copier, le fichier à traiter est déjà dans Data Lake/. Elle enchaîne donc
directement Transformation → Load, puis publie le résultat dans data/ (copie
LOCALE uniquement — Git n'est jamais touché automatiquement : committer et
pousser restent des actions manuelles et volontaires, comme partout ailleurs
dans ce projet).

Chaque exécution est journalisée dans log/historique_orchestration.log
(démarrage, succès ou échec), en plus du log technique habituel.

Installation de la tâche planifiée Windows (une seule fois)
-------------------------------------------------------------
    powershell -ExecutionPolicy Bypass -File pipeline_orchestrator\\installer_tache_planifiee.ps1

Exécution manuelle (test, depuis la racine du projet, avec -m)
------------------------------------------------------------------
    python -m pipeline_orchestrator.tache_quotidienne
"""

from __future__ import annotations
import shutil
from pathlib import Path

try:
    from logger_config import get_logger, log_historique
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # racine du projet
    from logger_config import get_logger, log_historique

from etl.transformation.Transformation import transformation
from etl.load.Load import load

log = get_logger(__name__)

RACINE = Path(__file__).resolve().parents[1]
NOM_BASE_DEFAUT = "ng_travel_2025_2026"


def executer_rafraichissement(
    data_lake: str = "Data Lake",
    data_warehouse: str = "Data Warehouse",
    nom: str = NOM_BASE_DEFAUT,
    publier: bool = True,
):
    """
    Retransforme le fichier déjà présent dans le Data Lake, recharge le Data
    Warehouse, et (si publier=True) copie le résultat dans data/ pour que
    l'application Streamlit locale reflète le rafraîchissement.
    """
    log.info("=== Tâche quotidienne : rafraîchissement (data_lake=%s, nom=%s) ===",
              data_lake, nom)
    log_historique(f"Rafraîchissement quotidien démarré — data_lake={data_lake}, nom={nom}")

    try:
        df = transformation(data_lake=data_lake)  # Transform : relit le Data Lake existant
        chemins = load(df, data_warehouse=data_warehouse, nom=nom,
                        formats=("parquet", "csv"))  # Load : réécrit le Data Warehouse

        if publier:
            parquet = next((c for c in chemins if c.suffix == ".parquet"), None)
            if parquet is not None:
                cible = RACINE / "data" / parquet.name
                cible.parent.mkdir(exist_ok=True)
                shutil.copy2(parquet, cible)
                log.info("Publié pour l'app (copie locale) : %s", cible)
    except Exception as e:
        log.exception("Échec du rafraîchissement quotidien — voir la trace ci-dessus.")
        log_historique(f"Rafraîchissement quotidien ÉCHOUÉ — data_lake={data_lake}, nom={nom} : {e}")
        raise

    log.info("=== Rafraîchissement quotidien terminé avec succès (%d lignes) ===", len(df))
    log_historique(f"Rafraîchissement quotidien terminé avec SUCCÈS — {len(df)} lignes, nom={nom}")
    return df


if __name__ == "__main__":
    executer_rafraichissement()
