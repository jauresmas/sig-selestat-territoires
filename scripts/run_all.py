"""Chaîne complète, rejouable à chaque mise à jour des référentiels.

Usage :
    python scripts/run_all.py              # tout reconstruire
    python scripts/run_all.py --depuis 2   # reprendre à partir de l'étape 2

Mise à jour : les flux (WFS IGN, GPU, BAN, INPN) renvoient toujours le dernier
millésime publié. Relancer la chaîne suffit pour rafraîchir les référentiels,
les contrôles, les métadonnées, la carte web et les cartes. Les arbres et
interventions saisis dans la base sont conservés.

    python scripts/run_all.py --reconstruire   # repart de zéro : efface la base
L'étape 6 s'exécute avec le Python de QGIS (PyQGIS), lancé automatiquement.
"""
import argparse
import importlib
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config  # noqa: E402
from outils import log  # noqa: E402

ETAPES = [
    ("00_acquisition", "Acquisition des référentiels ouverts"),
    ("01_base_postgis", "Base PostgreSQL/PostGIS"),
    ("02_controle_qualite", "Contrôle qualité et indicateurs"),
    ("03_exports", "Exports GeoPackage, QField, géodatabase, open data"),
    ("04_metadonnees", "Métadonnées ISO 19139 et dictionnaire des données"),
    ("05_carte_web", "Données de la carte web"),
    ("06_projet_qgis", "Projets QGIS, QField, planches et atlas (PyQGIS)"),
    ("07_documents", "Documents : note d'architecture, charte, tutoriels, bordereau"),
]


def lancer_pyqgis(module):
    script = Path(__file__).parent / f"{module}.py"
    subprocess.run([str(config.QGIS_PYTHON), str(script)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--depuis", type=int, default=0, help="numéro de la première étape")
    parser.add_argument("--jusqua", type=int, default=len(ETAPES) - 1, help="numéro de la dernière étape")
    parser.add_argument("--reconstruire", action="store_true",
                        help="efface et recrée la base (les arbres saisis sont perdus)")
    args = parser.parse_args()
    debut = time.time()
    log(f"SIG intercommunal - {config.EPCI_NOM} (SIREN {config.EPCI_SIREN})")
    for i, (module, libelle) in enumerate(ETAPES):
        if not args.depuis <= i <= args.jusqua:
            continue
        log(f"=== Étape {i} : {libelle}")
        t = time.time()
        if module == "06_projet_qgis":
            lancer_pyqgis(module)
            lancer_pyqgis("06b_captures_qgis")
        elif module == "01_base_postgis":
            importlib.import_module(module).main(reconstruire=args.reconstruire)
        else:
            importlib.import_module(module).main()
        log(f"=== Étape {i} terminée en {time.time() - t:.0f} s")
    log(f"Chaîne exécutée en {(time.time() - debut) / 60:.1f} min")


if __name__ == "__main__":
    main()
