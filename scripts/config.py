"""Paramètres du socle SIG intercommunal.

Toute la chaîne est pilotée depuis ce fichier. Pour la transposer à un autre
EPCI, il suffit de changer EPCI_SIREN, EPCI_NOM, DEPARTEMENT et VILLE_CENTRE.
"""
from pathlib import Path

# --- Arborescence -----------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
GPKG = INTERIM / "sig_ccst_travail.gpkg"  # base de travail (données brutes normalisées)
SQL = ROOT / "sql"
LIVRABLES = ROOT / "livrables"
DOCS = ROOT / "docs"  # carte web publiée avec GitHub Pages
QGIS_DIR = ROOT / "qgis"

# --- Territoire -------------------------------------------------------------
EPCI_SIREN = "246700967"
EPCI_NOM = "Communauté de communes de Sélestat"
EPCI_COURT = "CC de Sélestat"
VILLE_CENTRE = "67462"  # Sélestat
DEPARTEMENT = "67"
CRS = "EPSG:2154"  # Lambert-93
TAMPON_CONTEXTE_M = 300  # marge autour du territoire pour le fond de plan

# --- Services de données ----------------------------------------------------
WFS = "https://data.geopf.fr/wfs/ows"
GPU_API = "https://www.geoportail-urbanisme.gouv.fr/api"
OVERPASS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

# Couches de la BD TOPO (IGN) reprises comme référentiel topographique
BDTOPO = {
    "batiment": "BDTOPO_V3:batiment",
    "troncon_route": "BDTOPO_V3:troncon_de_route",
    "troncon_hydro": "BDTOPO_V3:troncon_hydrographique",
    "surface_hydro": "BDTOPO_V3:surface_hydrographique",
    "equipement": "BDTOPO_V3:zone_d_activite_ou_d_interet",
    "cimetiere": "BDTOPO_V3:cimetiere",
    "terrain_sport": "BDTOPO_V3:terrain_de_sport",
}

# Zonages du patrimoine naturel (INPN / PatriNat)
PATRINAT = {
    "sic": ("patrinat_sic:sic", "Natura 2000 - Zone spéciale de conservation (directive Habitats)"),
    "zps": ("patrinat_zps:zps", "Natura 2000 - Zone de protection spéciale (directive Oiseaux)"),
    "znieff1": ("patrinat_znieff1:znieff1", "ZNIEFF de type I"),
    "znieff2": ("patrinat_znieff2:znieff2", "ZNIEFF de type II"),
    "rnr": ("patrinat_rnr:rnr", "Réserve naturelle régionale"),
    "rnn": ("patrinat_rnn:rnn", "Réserve naturelle nationale"),
    "apb": ("patrinat_apb:apb", "Arrêté préfectoral de protection de biotope"),
    "ramsar": ("patrinat_ramsar:ramsar", "Zone humide d'importance internationale (Ramsar)"),
}

# --- Base PostgreSQL / PostGIS ----------------------------------------------
# Instance de démonstration créée par 01_base_postgis.py dans data/pgdata
# (port dédié pour ne pas interférer avec une instance existante).
PG_BIN = Path(r"C:\Program Files\PostgreSQL\15\bin")
PG_DATA = ROOT / "data" / "pgdata"
PG_HOST = "localhost"
PG_PORT = 5433
PG_DB = "sig_ccst"
PG_SUPERUSER = "postgres"
PG_OWNER = "sig_admin"
PG_SERVICE = "sig_ccst"  # nom du service déclaré dans pg_service.conf

# --- Inventaire du patrimoine arboré (données métier) -----------------------
GRAINE_SIMULATION = 67600  # rend la simulation des attributs reproductible
DATE_REFERENCE = "2026-10-01"

# --- Auteur -----------------------------------------------------------------
AUTEUR = "Jaurès DAA-HINGBANON"
CONTACT_URL = "https://jauresmas.github.io/portfolio/"

# --- QGIS -------------------------------------------------------------------
QGIS_PYTHON = Path(r"C:\Program Files\QGIS 3.34.12\bin\python-qgis-ltr.bat")
