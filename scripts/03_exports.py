"""Étape 3 - Exports pour les outils et les partenaires.

  - GeoPackage complet : base du projet QGIS portable (sans serveur)
  - GeoPackage QField : inventaire arboré + fond de plan, pour la saisie terrain
  - Géodatabase fichier (.gdb) : échange avec les partenaires sous ArcGIS,
    écrite par GDAL (pilote OpenFileGDB), sans licence ESRI
  - Jeux open data : vues du schéma diffusion en GeoJSON et CSV
"""
import shutil

import pandas as pd
import pyogrio

import config
from outils import log, pg_lire

# couche du GeoPackage -> requête PostGIS
COUCHES = {
    # référentiels
    "epci": "SELECT * FROM ref_admin.epci",
    "commune": "SELECT * FROM ref_admin.commune",
    "indicateurs_commune": "SELECT * FROM ref_admin.mv_indicateurs_commune",
    "parcelle": "SELECT * FROM ref_cadastre.parcelle",
    "adresse": "SELECT * FROM ref_adresse.adresse",
    "batiment": "SELECT * FROM ref_topo.batiment",
    "troncon_route": "SELECT * FROM ref_topo.troncon_route",
    "troncon_hydro": "SELECT * FROM ref_topo.troncon_hydro",
    "surface_hydro": "SELECT * FROM ref_topo.surface_hydro",
    "equipement": "SELECT * FROM ref_topo.equipement",
    "cimetiere": "SELECT * FROM ref_topo.cimetiere",
    "terrain_sport": "SELECT * FROM ref_topo.terrain_sport",
    # urbanisme et servitudes
    "doc_urba": "SELECT * FROM urbanisme.doc_urba",
    "zone_urba": "SELECT * FROM urbanisme.zone_urba",
    "parcelle_zonage": "SELECT * FROM urbanisme.mv_parcelle_zonage",
    "prescription_surf": "SELECT * FROM urbanisme.prescription_surf",
    "prescription_lin": "SELECT * FROM urbanisme.prescription_lin",
    "prescription_pct": "SELECT * FROM urbanisme.prescription_pct",
    "info_surf": "SELECT * FROM urbanisme.info_surf",
    "sup_assiette_s": "SELECT * FROM servitudes.v_assiette_s",
    "sup_generateur_s": "SELECT * FROM servitudes.v_generateur_s",
    "sup_generateur_l": "SELECT * FROM servitudes.sup_generateur_l",
    "categorie_sup": "SELECT * FROM servitudes.categorie_sup",
    "type_prescription": "SELECT * FROM urbanisme.type_prescription",
    "type_information": "SELECT * FROM urbanisme.type_information",
    "zonage_naturel": "SELECT * FROM environnement.zonage_naturel",
    # données métier
    "arbre": "SELECT * FROM espaces_verts.arbre",
    "intervention": "SELECT * FROM espaces_verts.intervention",
    "arbre_prioritaire": "SELECT * FROM espaces_verts.v_arbre_prioritaire",
    "arbre_diagnostic": "SELECT * FROM espaces_verts.v_arbre_diagnostic_a_programmer",
    "liste_essence": "SELECT * FROM espaces_verts.liste_essence",
    "liste_etat_sanitaire": "SELECT * FROM espaces_verts.liste_etat_sanitaire",
    "liste_stade_dev": "SELECT * FROM espaces_verts.liste_stade_dev",
    "liste_implantation": "SELECT * FROM espaces_verts.liste_implantation",
    "liste_risque": "SELECT * FROM espaces_verts.liste_risque",
    "liste_type_intervention": "SELECT * FROM espaces_verts.liste_type_intervention",
    # contrôle qualité
    "controle_zonage_chevauchement": "SELECT * FROM controle.v_zonage_chevauchement",
    "controle_parcelle_hors_zonage": "SELECT * FROM controle.v_parcelle_hors_zonage",
    "controle_adresse_non_certifiee": "SELECT * FROM controle.v_adresse_non_certifiee",
    "controle_batiment_sans_adresse": "SELECT * FROM controle.v_batiment_sans_adresse",
    "controle_arbre_doublon": "SELECT * FROM controle.v_arbre_doublon",
    "controle_arbre_incomplet": "SELECT * FROM controle.v_arbre_incomplet",
    # catalogue
    "metadonnees_fiche": "SELECT * FROM metadonnees.fiche",
}

# Couches emportées sur le terrain (QField)
QFIELD = ["commune", "parcelle", "batiment", "adresse", "troncon_route", "arbre",
          "intervention", "liste_essence", "liste_etat_sanitaire", "liste_stade_dev",
          "liste_implantation", "liste_risque", "liste_type_intervention"]

# Couches livrées en géodatabase fichier pour les partenaires sous ArcGIS
GDB = ["commune", "indicateurs_commune", "parcelle", "adresse", "batiment", "zone_urba",
       "prescription_surf", "info_surf", "sup_assiette_s", "zonage_naturel", "arbre",
       "intervention", "liste_essence", "liste_etat_sanitaire", "liste_type_intervention"]


def lire_couche(sql):
    """Lit une requête PostGIS : GeoDataFrame si elle a une géométrie, sinon DataFrame."""
    try:
        gdf = pg_lire(sql, geom="geom")
        return gdf.rename_geometry("geom") if gdf.geometry.name != "geom" else gdf
    except (ValueError, KeyError):
        return pg_lire(sql, geom=None)


def nettoyer(df):
    """Types simples pour les formats d'échange (uuid -> texte, tableaux -> texte)."""
    for c in df.columns:
        if c == "geom":
            continue
        echantillon = df[c].dropna().head(1)
        if len(echantillon) and not isinstance(echantillon.iloc[0], (str, int, float, bool)):
            if isinstance(echantillon.iloc[0], (list, tuple)):
                df[c] = df[c].map(lambda v: "; ".join(v) if isinstance(v, (list, tuple)) else v)
            elif hasattr(echantillon.iloc[0], "hex"):  # uuid
                df[c] = df[c].astype(str).where(df[c].notna())
    return df


def ecrire(df, fichier, couche, driver):
    pyogrio.write_dataframe(df, fichier, layer=couche, driver=driver)


def main():
    projets = config.LIVRABLES / "03_Projets_QGIS"
    echanges = config.LIVRABLES / "04_Echanges"
    qfield = projets / "qfield"
    for d in (projets, echanges, qfield):
        d.mkdir(parents=True, exist_ok=True)

    gpkg = projets / "sig_ccst.gpkg"
    gpkg_qfield = qfield / "inventaire_arbres.gpkg"
    gdb = echanges / "sig_ccst.gdb"
    for f in (gpkg, gpkg_qfield):
        f.unlink(missing_ok=True)
    shutil.rmtree(gdb, ignore_errors=True)

    log("GeoPackage du projet QGIS, GeoPackage QField, géodatabase fichier")
    for couche, sql in COUCHES.items():
        df = nettoyer(lire_couche(sql))
        ecrire(df, gpkg, couche, "GPKG")
        if couche in QFIELD:
            ecrire(df, gpkg_qfield, couche, "GPKG")
        if couche in GDB:
            ecrire(df, gdb, couche, "OpenFileGDB")
        log(f"  {couche} : {len(df)}")

    log("Jeux de données ouverts (schéma diffusion)")
    od = echanges / "open_data"
    od.mkdir(exist_ok=True)
    arbres = pg_lire("SELECT * FROM diffusion.v_arbre").to_crs(4326)
    arbres.to_file(od / "arbres_ccst.geojson", driver="GeoJSON", engine="pyogrio")
    ind = pg_lire("SELECT * FROM diffusion.v_indicateurs_commune")
    pd.DataFrame(ind.drop(columns="geom")).to_csv(od / "indicateurs_communes.csv", index=False,
                                                  sep=";", encoding="utf-8-sig")
    (od / "LISEZMOI.txt").write_text(
        "Jeux de données ouverts - Communauté de communes de Sélestat (démonstration)\n\n"
        "arbres_ccst.geojson : inventaire public du patrimoine arboré (WGS84).\n"
        "  Positions issues d'OpenStreetMap : © contributeurs OpenStreetMap, licence ODbL 1.0.\n"
        "  La base dérivée reste sous ODbL (partage à l'identique).\n"
        "  Les attributs d'état et de dimensions sont simulés (jeu de démonstration).\n\n"
        "indicateurs_communes.csv : indicateurs SIG par commune, Licence Ouverte 2.0.\n"
        "  Sources : IGN, Base Adresse Nationale, Géoportail de l'Urbanisme, INPN.\n",
        encoding="utf-8")
    log(f"  -> {od.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
