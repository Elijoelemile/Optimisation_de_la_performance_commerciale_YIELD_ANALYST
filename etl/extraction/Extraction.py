"""
Extraction.py — Étape « E » (Extract) de l'ETL NG Travel
=========================================================

Rôle : aller récupérer le fichier brut de la base de données, où qu'il se
trouve sur l'ordinateur (chemin direct OU dossier à explorer), et le déposer
tel quel — sans transformation — dans la zone d'atterrissage brute : le
« Data Lake ».

Principe ETL : le Data Lake stocke la donnée BRUTE, à l'identique de la source.
Aucune transformation ici : on ne fait que localiser et copier.

Utilisation en ligne de commande
--------------------------------
    # Copier un fichier précis dans le Data Lake :
    python Extraction.py "/chemin/vers/base_de_données_NG_Travel.xlsx"

    # Chercher automatiquement le fichier dans un dossier (récursif) :
    python Extraction.py "/Users/moi/Downloads" --pattern "NG_Travel"

    # Personnaliser le dossier Data Lake et le nom d'atterrissage :
    python Extraction.py "source.csv" --data-lake "Data Lake" --nom base_brute.csv

Utilisation en import (dans le pipeline)
----------------------------------------
    from Extraction import extraction
    chemin_depose = extraction("/chemin/source", data_lake="Data Lake")
"""

from __future__ import annotations
import argparse
import shutil
from pathlib import Path

try:
    from logger_config import get_logger
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # racine du projet
    from logger_config import get_logger

log = get_logger(__name__)

# Extensions reconnues comme "base de données" source
EXTENSIONS_VALIDES = {".csv", ".xlsx", ".xls"}


def trouver_source(chemin: str, pattern: str = "") -> Path:
    """
    Localise le fichier source.

    - Si `chemin` pointe vers un fichier : on le retourne directement.
    - Si `chemin` pointe vers un dossier : on l'explore RÉCURSIVEMENT et on
      retourne le fichier le plus récent dont le nom contient `pattern`
      (insensible à la casse) et dont l'extension est reconnue.

    Lève FileNotFoundError si rien n'est trouvé.
    """
    p = Path(chemin).expanduser()

    if p.is_file():
        return p

    if p.is_dir():
        candidats = [
            f for f in p.rglob("*")
            if f.is_file()
            and f.suffix.lower() in EXTENSIONS_VALIDES
            and (pattern.lower() in f.name.lower() if pattern else True)
        ]
        if not candidats:
            message = (
                f"Aucun fichier {sorted(EXTENSIONS_VALIDES)} "
                f"{f'contenant « {pattern} » ' if pattern else ''}"
                f"trouvé dans « {p} »."
            )
            log.error(message)
            raise FileNotFoundError(message)
        # Le plus récemment modifié (le plus à jour)
        return max(candidats, key=lambda f: f.stat().st_mtime)

    log.error("Chemin introuvable : « %s »", chemin)
    raise FileNotFoundError(f"Chemin introuvable : « {chemin} »")


def extraction(
    chemin_source: str,
    data_lake: str = "Data Lake",
    nom: str | None = None,
    pattern: str = "",
) -> Path:
    """
    Extrait (copie) le fichier source brut vers le Data Lake.

    Paramètres
    ----------
    chemin_source : chemin d'un fichier OU d'un dossier à explorer.
    data_lake     : dossier de destination (créé s'il n'existe pas).
    nom           : nom de fichier à l'atterrissage (par défaut : nom d'origine).
    pattern       : filtre sur le nom quand `chemin_source` est un dossier.

    Retourne le chemin (Path) du fichier déposé dans le Data Lake.
    """
    source = trouver_source(chemin_source, pattern)

    dossier_lake = Path(data_lake).expanduser()
    dossier_lake.mkdir(parents=True, exist_ok=True)

    destination = dossier_lake / (nom if nom else source.name)
    shutil.copy2(source, destination)  # copy2 conserve les métadonnées

    taille_ko = destination.stat().st_size / 1024
    log.info("Source : %s", source)
    log.info("Déposé dans : %s (%.0f Ko)", destination, taille_ko)
    return destination


def _cli():
    parser = argparse.ArgumentParser(
        description="Extraction ETL — copie le fichier brut vers le Data Lake."
    )
    parser.add_argument("source", help="Chemin du fichier OU d'un dossier à explorer.")
    parser.add_argument("--data-lake", default="Data Lake",
                        help="Dossier Data Lake (défaut : 'Data Lake').")
    parser.add_argument("--nom", default=None,
                        help="Nom du fichier à l'atterrissage (défaut : nom d'origine).")
    parser.add_argument("--pattern", default="",
                        help="Filtre sur le nom si la source est un dossier "
                             "(ex. 'NG_Travel').")
    args = parser.parse_args()
    extraction(args.source, data_lake=args.data_lake, nom=args.nom, pattern=args.pattern)


if __name__ == "__main__":
    _cli()
