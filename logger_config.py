"""
logger_config.py — Gestionnaire de log centralisé NG Travel
=============================================================

Point d'entrée UNIQUE pour la journalisation du projet, partagé par le
pipeline ETL (etl/, pipeline_orchestrator/) et par l'application
Streamlit (utils.py, pages/). Objectif : remplacer les print() épars par des
messages horodatés, classés par niveau de gravité, et conservés sur disque —
utile pour rejouer ou auditer une exécution du pipeline, ou diagnostiquer une
erreur survenue en production (ex. Copilote IA).

Deux niveaux de traçabilité, dans deux fichiers distincts du dossier `log/` :

  1. Le log TECHNIQUE (`log/ng_travel.log`) — chaque appel à `get_logger(nom)`
     renvoie un logger qui écrit toujours sur la console (stdout, visible en
     local et dans les logs du conteneur sur Streamlit Community Cloud, menu
     « Manage app » → « Logs »), et si le disque est accessible en écriture,
     également dans ce fichier TOURNANT (5 Mo par fichier, 3 fichiers
     d'historique conservés, les plus anciens sont purgés automatiquement).
     Sur un hébergement où l'écriture disque serait refusée ou éphémère, le
     fichier est simplement désactivé sans faire planter l'app.

  2. L'HISTORIQUE des orchestrations (`log/historique_orchestration.log`) —
     alimenté par `log_historique(evenement)`. Contrairement au log
     technique ci-dessus, ce fichier n'est JAMAIS tourné ni purgé : il
     s'agit d'une trace permanente, une ligne par exécution du pipeline
     (démarrage, succès, échec), pour pouvoir consulter l'historique complet
     des exécutions passées (notamment celles lancées par la tâche planifiée
     quotidienne — voir pipeline_orchestrator/).

Utilisation
-----------
    from logger_config import get_logger, log_historique
    log = get_logger(__name__)

    log.info("Transformation terminée : %d lignes.", len(df))
    log.warning("Compagnie non renseignée sur %d dossiers.", n)
    log.error("Échec de l'appel à l'API Mistral : %s", erreur)

    log_historique("Orchestration terminée avec succès (18 627 lignes).")

Niveau de log réglable via la variable d'environnement NG_TRAVEL_LOG_LEVEL
(INFO par défaut), ex. :
    NG_TRAVEL_LOG_LEVEL=DEBUG streamlit run streamlit_app.py
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path

# Ancré sur ce fichier (racine du projet) : le dossier log/ est donc toujours
# créé au même endroit, quel que soit le répertoire d'exécution (contrairement
# à un chemin relatif "log" qui dépendrait du dossier courant).
_DOSSIER_LOGS = Path(__file__).resolve().parent / "log"
_FICHIER_LOG = _DOSSIER_LOGS / "ng_travel.log"
_FICHIER_HISTORIQUE = _DOSSIER_LOGS / "historique_orchestration.log"

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_FORMAT_DATE = "%Y-%m-%d %H:%M:%S"

# Empêche de ré-ajouter des handlers à chaque appel (ex. reruns Streamlit) :
# un logger Python est un singleton par nom, mais get_logger() peut être
# rappelé plusieurs fois sur le même nom au fil de l'exécution.
_loggers_configures: set[str] = set()


def get_logger(nom: str) -> logging.Logger:
    """Retourne un logger prêt à l'emploi pour le module `nom` (passer __name__)."""
    logger = logging.getLogger(nom)
    if nom in _loggers_configures:
        return logger

    niveau = os.environ.get("NG_TRAVEL_LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, niveau, logging.INFO))
    logger.propagate = False  # évite les doublons si un logger racine est aussi configuré

    formatteur = logging.Formatter(_FORMAT, datefmt=_FORMAT_DATE)

    console = logging.StreamHandler()
    console.setFormatter(formatteur)
    logger.addHandler(console)

    try:
        _DOSSIER_LOGS.mkdir(exist_ok=True)
        fichier = logging.handlers.RotatingFileHandler(
            _FICHIER_LOG, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        fichier.setFormatter(formatteur)
        logger.addHandler(fichier)
    except OSError:
        # Disque non accessible en écriture (certains hébergements cloud,
        # permissions restreintes...) : on continue avec la seule sortie
        # console plutôt que de faire planter l'appelant.
        logger.debug("Journalisation fichier indisponible — sortie console uniquement.")

    _loggers_configures.add(nom)
    return logger


def log_historique(evenement: str) -> None:
    """
    Ajoute une ligne à l'historique PERMANENT des orchestrations
    (log/historique_orchestration.log) : une ligne = un événement notable
    (démarrage, succès, échec) d'une exécution du pipeline ETL.

    Contrairement au log technique de `get_logger()` (tournant, purgé au-delà
    de 3 fichiers), ce fichier n'est jamais tourné ni tronqué : il grossit
    indéfiniment pour conserver une trace complète de toutes les exécutions
    passées, notamment celles lancées automatiquement par la tâche planifiée
    quotidienne (voir pipeline_orchestrator/).
    """
    horodatage = datetime.now().strftime(_FORMAT_DATE)
    ligne = f"{horodatage} | {evenement}\n"
    try:
        _DOSSIER_LOGS.mkdir(exist_ok=True)
        with open(_FICHIER_HISTORIQUE, "a", encoding="utf-8") as f:
            f.write(ligne)
    except OSError:
        # Disque non accessible en écriture : l'événement reste malgré tout
        # visible via le logger technique (console + fichier tournant).
        pass
