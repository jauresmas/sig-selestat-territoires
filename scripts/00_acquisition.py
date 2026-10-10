"""Étape 0 - Acquisition des référentiels ouverts sur le territoire.

Toutes les sources sont interrogées par flux (WFS / API), sans téléchargement
manuel, puis normalisées dans une base de travail GeoPackage en Lambert-93 :

  - IGN ADMIN EXPRESS COG       : limites communales et intercommunales
  - IGN Parcellaire Express      : parcelles cadastrales (PCI)
  - IGN BD TOPO                  : bâti, voirie, hydrographie, équipements
  - Base Adresse Nationale       : adresses (BAN)
  - Géoportail de l'Urbanisme    : documents d'urbanisme (CNIG) et servitudes
  - INPN / PatriNat              : zonages du patrimoine naturel
  - OpenStreetMap (ODbL)         : arbres déjà cartographiés (amorce de l'inventaire)
"""
import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import config
from outils import SESSION, cql_liste, ecrire, log, requete, wfs


def reparer(texte):
    """Corrige les libellés encodés deux fois en UTF-8 ("ChÃ¢teau" -> "Château"),
    défaut présent dans certaines servitudes livrées au GPU."""
    if not isinstance(texte, str) or not any(c in texte for c in "ÃÂâ€"):
        return texte
    try:
        return texte.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texte


def garder(gdf, colonnes):
    """Conserve les colonnes demandées qui existent, plus la géométrie."""
    cols = [c for c in colonnes if c in gdf.columns]
    gdf = gdf[cols + ["geometry"]].copy()
    for c in cols:
        if gdf[c].dtype == object:
            gdf[c] = gdf[c].map(reparer)
    return gdf


def dans_territoire(gdf, zone):
    """Garde les objets qui touchent la zone (sans les découper)."""
    if gdf.empty:
        return gdf
    idx = gdf.sindex.query(zone, predicate="intersects")
    return gdf.iloc[sorted(set(idx))].reset_index(drop=True)


# --- Limites administratives -------------------------------------------------
def limites():
    log("Communes et EPCI (ADMIN EXPRESS COG)")
    com = wfs("ADMINEXPRESS-COG.LATEST:commune",
              cql=f"codes_siren_des_epci LIKE '%{config.EPCI_SIREN}%'")
    com = garder(com, ["code_insee", "nom_officiel", "statut", "population",
                       "code_postal", "code_siren", "superficie_cadastrale"])
    com = com.rename(columns={"nom_officiel": "nom", "code_siren": "siren_commune"})
    com["surface_ha"] = (com.area / 10_000).round(1)
    com = com.sort_values("code_insee").reset_index(drop=True)
    ecrire(com, "commune")

    epci = com.dissolve()[["geometry"]]
    epci["siren"] = config.EPCI_SIREN
    epci["nom"] = config.EPCI_NOM
    epci["nb_communes"] = len(com)
    epci["population"] = int(com["population"].sum())
    epci["surface_ha"] = round(float(epci.area.iloc[0]) / 10_000, 1)
    ecrire(epci[["siren", "nom", "nb_communes", "population", "surface_ha", "geometry"]], "epci")
    return com


# --- Cadastre et adresses ----------------------------------------------------
def cadastre(insee):
    log("Parcelles cadastrales (Parcellaire Express)")
    parc = wfs("CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle",
               cql=cql_liste("code_insee", insee), sort="gid")
    parc = garder(parc, ["idu", "code_insee", "nom_com", "section", "numero",
                         "feuille", "com_abs", "contenance"])
    parc = parc.drop_duplicates("idu").rename(columns={"nom_com": "commune"})
    ecrire(parc, "parcelle")


def adresses(insee):
    log("Adresses (Base Adresse Nationale)")
    ban = wfs("BAN.DATA.GOUV:ban", cql=cql_liste("code_insee", insee), sort="id")
    ban = garder(ban, ["id", "id_fantoir", "numero", "rep", "nom_voie", "nom_ld",
                       "code_postal", "code_insee", "nom_commune", "type_position",
                       "source_position", "source_nom_voie", "certification_commune",
                       "cad_parcelles"])
    ban = ban.rename(columns={"id": "cle_interop"}).drop_duplicates("cle_interop")
    ban["numero"] = pd.to_numeric(ban["numero"], errors="coerce").astype("Int64")
    ban["certification_commune"] = ban["certification_commune"].astype(str).eq("1")
    ecrire(ban, "adresse")


# --- BD TOPO -----------------------------------------------------------------
COLONNES_BDTOPO = {
    "batiment": ["cleabs", "nature", "usage_1", "usage_2", "construction_legere",
                 "nombre_de_logements", "nombre_d_etages", "hauteur",
                 "date_d_apparition", "origine_du_batiment", "identifiants_rnb"],
    "troncon_route": ["cleabs", "nature", "importance", "nom_collaboratif_gauche",
                      "nom_collaboratif_droite", "cpx_numero", "nombre_de_voies",
                      "largeur_de_chaussee", "sens_de_circulation", "urbain",
                      "acces_vehicule_leger", "prive", "itineraire_vert",
                      "position_par_rapport_au_sol", "fictif"],
    "troncon_hydro": ["cleabs", "nature", "cpx_toponyme_de_cours_d_eau", "persistance",
                      "position_par_rapport_au_sol", "fictif"],
    "surface_hydro": ["cleabs", "nature", "cpx_toponyme_de_plan_d_eau", "persistance"],
    "equipement": ["cleabs", "categorie", "nature", "nature_detaillee", "toponyme",
                   "insee_commune", "fictif"],
    "cimetiere": ["cleabs", "nature", "toponyme"],
    "terrain_sport": ["cleabs", "nature", "nature_detaillee"],
}


def bdtopo(zone_contexte):
    bbox = tuple(zone_contexte.bounds)
    for nom, typename in config.BDTOPO.items():
        log(f"BD TOPO : {nom}")
        gdf = wfs(typename, bbox=bbox, sort="cleabs")
        gdf = dans_territoire(gdf, zone_contexte)
        gdf = garder(gdf, COLONNES_BDTOPO[nom])
        if "etat_de_l_objet" in gdf.columns:
            gdf = gdf[gdf["etat_de_l_objet"] == "En service"]
        # géométries 3D -> 2D (la BD TOPO livre des Z)
        gdf = gdf.set_geometry(gdf.geometry.force_2d())
        ecrire(gdf, nom)


# --- Documents d'urbanisme (GPU, standard CNIG) -------------------------------
def url_piece(df):
    """Lien direct vers une pièce écrite (règlement) déposée sur le GPU."""
    base = "https://data.geopf.fr/annexes/gpu/documents"
    lien = base + "/" + df["partition"] + "/" + df["gpu_doc_id"] + "/" + df["nomfic"].fillna("")
    if "urlfic" in df.columns:
        lien = df["urlfic"].where(df["urlfic"].fillna("").str.startswith("http"), lien)
    return lien.where(df["nomfic"].fillna("") != "")


def urbanisme(insee, territoire):
    partitions = [f"DU_{i}" for i in insee]
    log("Documents d'urbanisme (Géoportail de l'Urbanisme)")
    doc = wfs("wfs_du:doc_urba", cql=cql_liste("partition", partitions))
    doc = pd.DataFrame(doc.drop(columns="geometry", errors="ignore"))
    # un document par commune : celui en vigueur (sans date de fin, le plus récent)
    doc["datefin"] = doc["datefin"].fillna("")
    doc = (doc.sort_values(["partition", "datefin", "datappro"], ascending=[True, True, False])
              .drop_duplicates("partition"))
    doc["code_insee"] = doc["partition"].str[3:]
    doc = doc[["code_insee", "partition", "idurba", "typedoc", "etat", "datappro",
               "nomproc", "nomreg", "gpu_doc_id", "gpu_timestamp"]].copy()
    doc["url_reglement"] = url_piece(doc.rename(columns={"nomreg": "nomfic"}))
    doc["url_gpu"] = "https://www.geoportail-urbanisme.gouv.fr/document/by-id/" + doc["gpu_doc_id"]
    manquants = sorted(set(insee) - set(doc["code_insee"]))
    if manquants:
        log(f"  communes sans document publié sur le GPU : {', '.join(manquants)}")
    ecrire(doc, "doc_urba")

    for couche, cols in {
        "zone_urba": ["partition", "idurba", "libelle", "libelong", "typezone",
                      "destdomi", "nomfic", "urlfic", "datvalid"],
        "prescription_surf": ["partition", "idurba", "libelle", "txt", "typepsc", "stypepsc",
                              "nomfic", "urlfic", "datvalid"],
        "prescription_lin": ["partition", "idurba", "libelle", "txt", "typepsc", "stypepsc",
                             "nomfic", "urlfic", "datvalid"],
        "prescription_pct": ["partition", "idurba", "libelle", "txt", "typepsc", "stypepsc",
                             "nomfic", "urlfic", "datvalid"],
        "info_surf": ["partition", "idurba", "libelle", "txt", "typeinf", "stypeinf",
                      "nomfic", "urlfic", "datvalid"],
    }.items():
        log(f"  {couche}")
        gdf = wfs(f"wfs_du:{couche}", cql=cql_liste("partition", partitions))
        if gdf.empty:
            continue
        gdf = gdf[gdf["idurba"].isin(doc["idurba"])]  # uniquement le document en vigueur
        gdf = garder(gdf, cols + ["gpu_doc_id"])
        gdf["code_insee"] = gdf["partition"].str[3:]
        gdf["url_reglement"] = url_piece(gdf)
        ecrire(gdf, couche)

    log("Servitudes d'utilité publique (GPU)")
    bbox = tuple(territoire.bounds)
    for suffixe in ("s", "l", "p"):
        for genre in ("assiette", "generateur"):
            gdf = wfs(f"wfs_sup:{genre}_sup_{suffixe}", bbox=bbox, sort="gid")
            gdf = dans_territoire(gdf, territoire)
            if gdf.empty:
                continue
            cols = ["suptype", "partition", "idgen", "nomsuplitt", "fichier", "gpu_doc_id"]
            cols += (["idass", "nomass", "typeass", "modegeoass", "paramcalc"]
                     if genre == "assiette" else ["nomgen", "typegen"])
            gdf = garder(gdf, cols)
            gdf["suptype"] = gdf["suptype"].str.upper()
            ecrire(gdf, f"sup_{genre}_{suffixe}")


# --- Patrimoine naturel --------------------------------------------------------
def patrimoine_naturel(territoire):
    log("Zonages du patrimoine naturel (INPN)")
    bbox = tuple(territoire.bounds)
    morceaux = []
    for code, (typename, libelle) in config.PATRINAT.items():
        gdf = wfs(typename, bbox=bbox)
        gdf = dans_territoire(gdf, territoire)
        if gdf.empty:
            continue
        gdf = gdf.rename(columns={"nom_site": "nom", "id_mnhn": "code_mnhn",
                                  "url_fiche": "url_inpn", "gest_site": "gestionnaire"})
        gdf["type_zonage"] = code.upper()
        gdf["libelle_type"] = libelle
        gdf["surface_ha_territoire"] = (gdf.intersection(territoire).area / 10_000).round(1)
        morceaux.append(garder(gdf, ["type_zonage", "libelle_type", "code_mnhn", "nom",
                                     "gestionnaire", "url_inpn", "surface_ha_territoire"]))
        log(f"  {code} : {len(gdf)} zonage(s)")
    zon = gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs=config.CRS)
    zon["nom"] = zon["nom"].str.replace(" ", " ").str.strip()
    zon = zon[zon["surface_ha_territoire"] >= 1].reset_index(drop=True)  # simples contacts en limite
    ecrire(zon, "zonage_naturel")


# --- Arbres OpenStreetMap ----------------------------------------------------------
def arbres_osm(territoire_wgs84, territoire):
    log("Arbres cartographiés dans OpenStreetMap (amorce de l'inventaire)")
    brut = config.RAW / "osm_arbres.json"
    if not brut.exists():
        xmin, ymin, xmax, ymax = territoire_wgs84.bounds
        q = (f'[out:json][timeout:120];node["natural"="tree"]'
             f'({ymin:.5f},{xmin:.5f},{ymax:.5f},{xmax:.5f});out body;')
        for url in config.OVERPASS:
            try:
                r = requete(url, data={"data": q}, timeout=200, essais=2)
                brut.parent.mkdir(parents=True, exist_ok=True)
                brut.write_text(r.text, encoding="utf-8")
                break
            except Exception as err:  # serveur Overpass saturé : on essaie le suivant
                log(f"  {url} indisponible ({err.__class__.__name__})")
        else:
            raise RuntimeError("Aucun serveur Overpass n'a répondu")
    elements = json.loads(brut.read_text(encoding="utf-8"))["elements"]
    lignes = []
    for e in elements:
        t = e.get("tags", {})
        lignes.append({
            "osm_id": e["id"],
            "espece_osm": t.get("species") or t.get("taxon"),
            "genre_osm": t.get("genus"),
            "nom_commun_osm": t.get("species:fr") or t.get("taxon:fr"),
            "type_feuillage": t.get("leaf_type"),
            "hauteur_osm": t.get("height"),
            "circonference_osm": t.get("circumference"),
            "denotation": t.get("denotation"),
            "geometry": Point(e["lon"], e["lat"]),
        })
    gdf = gpd.GeoDataFrame(lignes, crs="EPSG:4326").to_crs(config.CRS)
    gdf = gdf[gdf.within(territoire)].reset_index(drop=True)
    ecrire(gdf, "arbre_osm")


def main():
    com = limites()
    insee = list(com["code_insee"])
    territoire = com.union_all()
    contexte = territoire.buffer(config.TAMPON_CONTEXTE_M)
    territoire_wgs84 = gpd.GeoSeries([territoire], crs=config.CRS).to_crs(4326).iloc[0]

    cadastre(insee)
    adresses(insee)
    bdtopo(contexte)
    urbanisme(insee, territoire)
    patrimoine_naturel(territoire)
    arbres_osm(territoire_wgs84, territoire)


if __name__ == "__main__":
    main()
