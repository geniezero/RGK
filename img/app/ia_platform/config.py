"""Chemins du projet.

    data/ia_platform.db   base de données (créée au premier lancement)
    data/archives/        sauvegardes datées de la base
    data/modeles/         modèles CSV d'import (assets, clients, mesures)
    data/devis/<année>/   devis envoyés (PDF), une version par fichier

La variable d'environnement IA_DB permet d'utiliser une autre base (tests).
"""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODELES_DIR = DATA_DIR / "modeles"
ARCHIVES_DIR = DATA_DIR / "archives"
DB_PATH = Path(os.environ.get("IA_DB") or DATA_DIR / "ia_platform.db")
DEVIS_DIR = DB_PATH.parent / "devis"  # à côté de la base (data/devis)


def _reprendre_ancienne_base():
    """Version 1 : la base et les archives étaient à la racine du projet. On les range dans data/."""
    if os.environ.get("IA_DB"):
        return
    DATA_DIR.mkdir(exist_ok=True)
    ancienne = ROOT / "ia_platform.db"
    if ancienne.exists() and not DB_PATH.exists():
        shutil.move(str(ancienne), DB_PATH)
    anciennes_archives = ROOT / "archives"
    if anciennes_archives.is_dir() and not ARCHIVES_DIR.exists():
        shutil.move(str(anciennes_archives), ARCHIVES_DIR)


_reprendre_ancienne_base()
