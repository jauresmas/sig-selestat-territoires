"""Étape 1 - Base PostgreSQL/PostGIS : structure, chargement et règles métier.

  1. instance PostgreSQL de démonstration (data/pgdata, port 5433), créée si besoin
  2. base sig_ccst : extensions, rôles, schémas et droits      (sql/01_structure.sql)
  3. chargement des référentiels depuis la base de travail, puis intégrité
                                                              (sql/02_referentiels.sql)
  4. modèle métier du patrimoine arboré et jeu de démonstration (sql/03_espaces_verts.sql)
  5. fiche parcelle, contrôles, diffusion, indicateurs         (sql/04 à 07)
  6. catalogue des données, puis sauvegarde (pg_dump)

En production, les étapes 2 à 6 s'appliquent telles quelles au serveur
PostgreSQL de la collectivité : seule l'étape 1 est propre à la démonstration.
"""
import subprocess
import time

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import MultiLineString, MultiPolygon

import catalogue
import config
from outils import couches, lire, log, moteur as moteur_pg, pg_env, psql

PG_CTL = str(config.PG_BIN / "pg_ctl.exe")


# --- 1. Instance de démonstration ------------------------------------------------
def instance():
    if not (config.PG_DATA / "PG_VERSION").exists():
        log(f"Création de l'instance PostgreSQL de démonstration ({config.PG_DATA})")
        config.PG_DATA.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(config.PG_BIN / "initdb.exe"), "-D", str(config.PG_DATA),
                        "-U", config.PG_SUPERUSER, "-A", "trust", "-E", "UTF8",
                        "--locale=C", "--lc-messages=C"],
                       check=True, capture_output=True)
        # n'écoute que sur la machine locale
        conf = config.PG_DATA / "postgresql.conf"
        conf.write_text(conf.read_text() + f"\nport = {config.PG_PORT}\n"
                        "listen_addresses = 'localhost'\nshared_buffers = 256MB\n"
                        "work_mem = 32MB\nmaintenance_work_mem = 256MB\n")
    etat = subprocess.run([PG_CTL, "status", "-D", str(config.PG_DATA)], capture_output=True)
    if etat.returncode != 0:
        log(f"Démarrage de PostgreSQL sur le port {config.PG_PORT}")
        # sorties vers NUL : le serveur lancé hérite des descripteurs, les capturer
        # bloquerait le script jusqu'à l'arrêt de PostgreSQL
        subprocess.run([PG_CTL, "start", "-D", str(config.PG_DATA), "-w",
                        "-l", str(config.PG_DATA.parent / "postgresql.log")],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       stdin=subprocess.DEVNULL)
        time.sleep(1)


def base_neuve():
    log(f"Base {config.PG_DB} : création")
    psql(f"DROP DATABASE IF EXISTS {config.PG_DB} WITH (FORCE)", base="postgres")
    psql(f"CREATE DATABASE {config.PG_DB} ENCODING 'UTF8' TEMPLATE template0", base="postgres")
    psql(fichier=config.SQL / "01_structure.sql")


# --- 3. Référentiels ---------------------------------------------------------------
def en_multi(gdf):
    """Homogénéise les géométries (Polygon -> MultiPolygon...) pour typer la colonne."""
    types = set(gdf.geom_type.dropna())
    if types <= {"Polygon", "MultiPolygon"}:
        gdf["geometry"] = [MultiPolygon([g]) if g.geom_type == "Polygon" else g
                           for g in gdf.geometry]
    elif types <= {"LineString", "MultiLineString"}:
        gdf["geometry"] = [MultiLineString([g]) if g.geom_type == "LineString" else g
                           for g in gdf.geometry]
    return gdf


def charger_referentiels():
    from sqlalchemy import create_engine
    moteur = create_engine(f"postgresql+psycopg2://{config.PG_OWNER}@{config.PG_HOST}:"
                           f"{config.PG_PORT}/{config.PG_DB}")
    presentes = couches()
    journal = []
    for fiche in catalogue.CATALOGUE:
        if fiche["couche"] not in presentes:
            log(f"  {fiche['couche']} absente de la base de travail : ignorée")
            continue
        gdf = lire(fiche["couche"])
        gdf.columns = [c.lower() for c in gdf.columns]
        table = f"{fiche['schema']}.{fiche['table']}"
        if isinstance(gdf, gpd.GeoDataFrame) and gdf.geometry.notna().any():
            gdf = en_multi(gdf).rename_geometry("geom")
            gdf.to_postgis(fiche["table"], moteur, schema=fiche["schema"],
                           if_exists="replace", index=False, chunksize=5000)
        else:
            pd.DataFrame(gdf.drop(columns="geometry", errors="ignore")).to_sql(
                fiche["table"], moteur, schema=fiche["schema"], if_exists="replace", index=False)
        cle = fiche["cle"]
        if cle:
            psql(f"ALTER TABLE {table} ADD PRIMARY KEY ({cle})", utilisateur=config.PG_OWNER)
        else:
            psql(f"ALTER TABLE {table} ADD COLUMN gid integer GENERATED ALWAYS AS IDENTITY "
                 f"PRIMARY KEY", utilisateur=config.PG_OWNER)
        journal.append((table, len(gdf), fiche["source_url"]))
        log(f"  -> {table} : {len(gdf)} objets")

    valeurs = ",".join(f"('{t}', {n}, '{s}', 'scripts/01_base_postgis.py')" for t, n, s in journal)
    psql("INSERT INTO metadonnees.journal_integration (table_nom, nb_objets, source, script) "
         f"VALUES {valeurs}", utilisateur=config.PG_OWNER)
    psql(fichier=config.SQL / "02_referentiels.sql", utilisateur=config.PG_OWNER)


# --- 4. Patrimoine arboré : jeu de démonstration -------------------------------------
# Correspondance des noms OpenStreetMap vers le référentiel des essences
SYNONYMES = {
    "platanus x acerifolia": "Platanus x hispanica", "platanus × acerifolia": "Platanus x hispanica",
    "platanus × hispanica": "Platanus x hispanica", "platanus acerifolia": "Platanus x hispanica",
    "tilia × europaea": "Tilia x europaea", "tilia europaea": "Tilia x europaea",
    "styphnolobium japonicum": "Sophora japonica", "salix babylonica": "Salix babylonica",
    "tilia tomentosa": "Tilia tomentosa",
}
GENRE_DEFAUT = {
    "Tilia": "Tilia cordata", "Platanus": "Platanus x hispanica", "Acer": "Acer platanoides",
    "Carpinus": "Carpinus betulus", "Fraxinus": "Fraxinus excelsior", "Quercus": "Quercus robur",
    "Aesculus": "Aesculus hippocastanum", "Betula": "Betula pendula", "Prunus": "Prunus avium",
    "Pinus": "Pinus nigra", "Robinia": "Robinia pseudoacacia", "Salix": "Salix alba",
    "Populus": "Populus nigra", "Celtis": "Celtis australis", "Juglans": "Juglans regia",
    "Malus": "Malus domestica", "Taxus": "Taxus baccata", "Ginkgo": "Ginkgo biloba",
    "Liquidambar": "Liquidambar styraciflua", "Alnus": "Alnus x spaethii",
    "Fagus": "Fagus sylvatica", "Magnolia": "Magnolia x soulangeana",
    "Koelreuteria": "Koelreuteria paniculata", "Paulownia": "Paulownia tomentosa",
    "Ailanthus": "Ailanthus altissima", "Cedrus": "Cedrus atlantica",
}
# Répartition type d'un patrimoine urbain du Grand Est (essences non renseignées)
REPARTITION = {
    "Tilia cordata": 10, "Tilia x europaea": 6, "Platanus x hispanica": 11, "Acer platanoides": 9,
    "Acer pseudoplatanus": 5, "Acer campestre": 4, "Carpinus betulus": 8,
    "Aesculus hippocastanum": 6, "Fraxinus excelsior": 5, "Prunus serrulata": 4,
    "Prunus avium": 3, "Quercus robur": 4, "Betula pendula": 4, "Celtis australis": 3,
    "Robinia pseudoacacia": 3, "Pinus nigra": 3, "Ginkgo biloba": 2, "Liquidambar styraciflua": 2,
    "Sophora japonica": 2, "Salix alba": 1, "Indetermine": 5,
}
OBSERVATIONS = {
    "surveiller": ["Bois mort dans le houppier", "Blessure au collet (tonte)",
                   "Conflit avec l'éclairage public", "Racines soulevant le trottoir"],
    "deperissant": ["Cavité au collet", "Champignon lignivore au pied",
                    "Fissure sur une charpentière", "Houppier clairsemé, descente de cime"],
    "mort": ["Arbre sec sur pied", "Pourriture racinaire avancée"],
}


def essence_osm(row, essences):
    for champ in ("espece_osm", "genre_osm"):
        val = row.get(champ)
        if not isinstance(val, str) or not val.strip():
            continue
        v = val.strip()
        v = SYNONYMES.get(v.lower(), v)
        if v in essences:
            return v
        genre = v.split()[0].capitalize()
        if genre in GENRE_DEFAUT:
            return GENRE_DEFAUT[genre]
    return None


def simuler_arbres(essences):
    """Attributs plausibles et reproductibles sur les positions réelles d'OSM."""
    rng = np.random.default_rng(config.GRAINE_SIMULATION)
    arb = lire("arbre_osm")
    routes = lire("troncon_route")
    equip = lire("equipement")
    ecoles = equip[equip["categorie"].isin(["Science et enseignement", "Sport", "Santé"])]
    parcs = equip[equip["nature"].isin(["Espace public", "Aire de détente"])]

    noms, poids = zip(*REPARTITION.items())
    poids = np.array(poids) / sum(poids)
    proches_route = arb.geometry.apply(lambda g: False)
    idx = routes.sindex.query(arb.geometry.buffer(10), predicate="intersects")
    proches_route.iloc[sorted(set(idx[0]))] = True
    voisins = arb.sindex.query(arb.geometry.buffer(15), predicate="intersects")
    nb_voisins = pd.Series(voisins[0]).value_counts().reindex(range(len(arb)), fill_value=1) - 1
    dans_parc = arb.geometry.apply(lambda g: False)
    if len(parcs):
        i = parcs.sindex.query(arb.geometry, predicate="within")
        dans_parc.iloc[sorted(set(i[0]))] = True
    pres_equip = arb.geometry.apply(lambda g: False)
    if len(ecoles):
        i = ecoles.sindex.query(arb.geometry.buffer(20), predicate="intersects")
        pres_equip.iloc[sorted(set(i[0]))] = True

    lignes = []
    for k, row in arb.iterrows():
        ess = essence_osm(row, essences)
        source_attr = "osm + simulation" if ess else "simulation"
        ess = ess or rng.choice(noms, p=poids)
        genre = ess.split()[0]

        if dans_parc.iloc[k]:
            implantation = "parc"
        elif pres_equip.iloc[k]:
            implantation = "equipement"
        elif proches_route.iloc[k]:
            implantation = "alignement"
        elif nb_voisins.iloc[k] >= 3:
            implantation = "groupe"
        else:
            implantation = "isole"

        stade = rng.choice(["jeune", "adulte", "mature", "senescent"], p=[0.16, 0.44, 0.32, 0.08])
        base_h = {"jeune": (3, 7), "adulte": (8, 15), "mature": (14, 25), "senescent": (16, 28)}[stade]
        base_c = {"jeune": (15, 50), "adulte": (60, 140), "mature": (130, 260), "senescent": (220, 420)}[stade]
        facteur = 0.7 if genre in ("Prunus", "Malus", "Taxus", "Sophora") else 1.0
        hauteur = round(float(rng.uniform(*base_h)) * facteur, 1)
        circ = int(rng.uniform(*base_c) * facteur)
        try:
            hauteur = float(str(row.get("hauteur_osm")).replace(",", ".").split()[0])
        except (ValueError, IndexError):
            pass
        if not (0.5 <= hauteur <= 50):
            hauteur = round(float(rng.uniform(*base_h)), 1)
        annee = {"jeune": (2016, 2024), "adulte": (1980, 2015), "mature": (1945, 1985),
                 "senescent": (1890, 1950)}[stade]
        annee = int(rng.integers(*annee)) if rng.random() < 0.6 else None

        p_etat = {"jeune": [0.70, 0.20, 0.07, 0.03, 0.00], "adulte": [0.58, 0.26, 0.11, 0.04, 0.01],
                  "mature": [0.45, 0.30, 0.15, 0.08, 0.02], "senescent": [0.15, 0.25, 0.30, 0.22, 0.08]}[stade]
        if genre == "Fraxinus":  # chalarose du frêne
            p_etat = [0.15, 0.20, 0.30, 0.28, 0.07]
        etat = rng.choice(["bon", "moyen", "surveiller", "deperissant", "mort"], p=p_etat)
        expose = implantation in ("alignement", "equipement")
        if etat == "mort" or (etat == "deperissant" and expose):
            risque = "eleve"
        elif etat in ("deperissant", "surveiller") or (stade == "senescent" and expose):
            risque = "modere"
        else:
            risque = "faible"
        obs = None
        if etat in OBSERVATIONS and rng.random() < 0.8:
            obs = rng.choice(OBSERVATIONS[etat])
        if genre == "Fraxinus" and etat in ("surveiller", "deperissant", "mort"):
            obs = "Symptômes de chalarose"
        if genre == "Aesculus" and etat != "bon" and rng.random() < 0.6:
            obs = "Mineuse du marronnier"
        # campagne de diagnostics 2024-2026 sur la plupart des arbres, quelques
        # diagnostics anciens, et des arbres jamais diagnostiqués
        tirage, diag = rng.random(), None
        if tirage < 0.72:
            diag = pd.Timestamp("2023-11-01") + pd.Timedelta(days=int(rng.integers(0, 1060)))
        elif tirage < 0.84:
            diag = pd.Timestamp("2020-03-01") + pd.Timedelta(days=int(rng.integers(0, 1300)))
        remarquable = bool(circ >= 300 and rng.random() < 0.6)

        lignes.append({
            "essence": ess, "implantation": implantation, "stade_dev": stade,
            "hauteur_m": hauteur, "circonference_cm": circ, "annee_plantation": annee,
            "etat_sanitaire": etat, "risque": risque, "remarquable": remarquable,
            "date_diagnostic": diag.date() if diag is not None else None,
            "observations": obs, "source_geom": "osm", "source_attributs": source_attr,
            "osm_id": int(row["osm_id"]), "geom": row.geometry,
        })
    return gpd.GeoDataFrame(lignes, geometry="geom", crs=config.CRS)


def simuler_interventions(arbres):
    """Historique 2022-2026 cohérent avec l'état de chaque arbre."""
    rng = np.random.default_rng(config.GRAINE_SIMULATION + 1)
    cout = {"diagnostic": 60, "taille": 180, "formation": 90, "elagage": 350,
            "haubanage": 450, "abattage": 650}
    lignes = []

    def ajout(a, type_, date, etat=None, commentaire=None):
        prestataire = type_ in ("elagage", "haubanage", "abattage") or rng.random() < 0.2
        lignes.append({
            "arbre_id": a["id"], "type_intervention": type_, "date_intervention": date,
            "intervenant": ("Prestataire élagage (marché à bons de commande)" if prestataire
                            else "Régie espaces verts"),
            "cout_ht": round(cout[type_] * float(rng.uniform(0.8, 1.3)), 2),
            "etat_constate": etat, "commentaire": commentaire,
        })

    for _, a in arbres.iterrows():
        if pd.notna(a["date_diagnostic"]):
            ajout(a, "diagnostic", a["date_diagnostic"], a["etat_sanitaire"],
                  a["observations"] if isinstance(a["observations"], str) else None)
        if a["stade_dev"] == "jeune" and rng.random() < 0.5:
            ajout(a, "formation", pd.Timestamp("2022-11-01").date()
                  + pd.Timedelta(days=int(rng.integers(0, 1400))))
        elif rng.random() < 0.35:
            ajout(a, "taille", pd.Timestamp("2022-11-01").date()
                  + pd.Timedelta(days=int(rng.integers(0, 1400))))
        if a["risque"] == "eleve" and a["etat_sanitaire"] != "mort" and rng.random() < 0.5:
            ajout(a, "elagage", pd.Timestamp("2025-01-15").date()
                  + pd.Timedelta(days=int(rng.integers(0, 500))), commentaire="Mise en sécurité")
        if a["etat_sanitaire"] == "mort" and rng.random() < 0.4:
            ajout(a, "abattage", pd.Timestamp("2026-02-01").date()
                  + pd.Timedelta(days=int(rng.integers(0, 200))),
                  commentaire="Abattage pour raison de sécurité, remplacement à programmer")
    df = pd.DataFrame(lignes)
    # les diagnostics d'abord, pour que la fiche de l'arbre suive l'ordre chronologique
    return df.sort_values(["date_intervention"]).reset_index(drop=True)


def espaces_verts():
    from sqlalchemy import create_engine
    moteur = create_engine(f"postgresql+psycopg2://{config.PG_OWNER}@{config.PG_HOST}:"
                           f"{config.PG_PORT}/{config.PG_DB}")
    psql(fichier=config.SQL / "03_espaces_verts.sql", utilisateur=config.PG_OWNER)
    log("Patrimoine arboré : positions OpenStreetMap + attributs simulés")
    essences = set(pd.read_sql("SELECT code FROM espaces_verts.liste_essence", moteur)["code"])
    arb = simuler_arbres(essences)
    arb.to_postgis("arbre_demo", moteur, schema="import", if_exists="replace", index=False)
    colonnes = [c for c in arb.columns]
    liste = ", ".join(colonnes)
    psql(f"INSERT INTO espaces_verts.arbre ({liste}) SELECT {liste} FROM import.arbre_demo "
         "ORDER BY ST_X(geom), ST_Y(geom)", utilisateur=config.PG_OWNER)
    inseres = pd.read_sql("SELECT id::text, numero, etat_sanitaire, stade_dev, risque, "
                          "date_diagnostic, observations FROM espaces_verts.arbre", moteur)
    log(f"  -> espaces_verts.arbre : {len(inseres)} arbres")
    inter = simuler_interventions(inseres)
    inter.to_sql("intervention_demo", moteur, schema="import", if_exists="replace", index=False)
    cols = ", ".join(inter.columns)
    psql(f"INSERT INTO espaces_verts.intervention ({cols}) "
         f"SELECT arbre_id::uuid, type_intervention, date_intervention::date, intervenant, "
         f"cout_ht, etat_constate, commentaire FROM import.intervention_demo "
         f"ORDER BY date_intervention", utilisateur=config.PG_OWNER)
    log(f"  -> espaces_verts.intervention : {len(inter)} interventions")
    psql("DROP TABLE import.arbre_demo, import.intervention_demo", utilisateur=config.PG_OWNER)


# Descriptions des champs les plus courants (deviennent des commentaires de colonnes,
# affichés dans QGIS, pgAdmin et le dictionnaire des données)
CHAMPS = {
    "code_insee": "Code officiel géographique de la commune (INSEE)",
    "nom": "Nom", "population": "Population municipale légale (INSEE)",
    "surface_ha": "Surface calculée (ha, Lambert-93)",
    "idu": "Identifiant unique de la parcelle (département + commune + préfixe + section + numéro)",
    "section": "Section cadastrale", "numero": "Numéro (parcelle ou adresse)",
    "contenance": "Contenance cadastrale (m²), surface fiscale indicative",
    "cle_interop": "Clé d'interopérabilité de l'adresse (BAN)",
    "nom_voie": "Nom de la voie", "rep": "Indice de répétition (bis, ter...)",
    "certification_commune": "Adresse certifiée par la commune dans sa Base Adresse Locale",
    "cad_parcelles": "Parcelles cadastrales de rattachement (identifiants séparés par |)",
    "cleabs": "Identifiant de l'objet dans la BD TOPO",
    "usage_1": "Usage principal du bâtiment", "nombre_de_logements": "Nombre de logements",
    "hauteur": "Hauteur du bâtiment (m)", "identifiants_rnb": "Identifiant du Référentiel national des bâtiments",
    "typezone": "Type de zone CNIG : U, AUc, AUs, A, N",
    "libelle": "Libellé court", "libelong": "Libellé long",
    "idurba": "Identifiant du document d'urbanisme (standard CNIG)",
    "url_reglement": "Lien vers le règlement écrit (pièce déposée au GPU)",
    "typepsc": "Type de prescription (nomenclature CNIG)", "typeinf": "Type d'information (nomenclature CNIG)",
    "suptype": "Catégorie de servitude d'utilité publique (AC1, PM1...)",
    "type_zonage": "Type de zonage (SIC, ZPS, ZNIEFF1, ZNIEFF2, RNR, APB)",
    "geom": "Géométrie (Lambert-93, EPSG:2154)", "gid": "Identifiant technique",
}


def commenter_colonnes():
    """Pose les descriptions de champs courants en commentaires de colonnes."""
    cols = pd.read_sql("""SELECT table_schema, table_name, column_name
                      FROM information_schema.columns
                      WHERE table_schema IN ('ref_admin','ref_cadastre','ref_adresse','ref_topo',
                                             'urbanisme','servitudes','environnement')
                        AND table_name IN (SELECT table_name FROM information_schema.tables
                                           WHERE table_type = 'BASE TABLE')""", moteur_pg())
    ordres = []
    for _, c in cols.iterrows():
        if c["column_name"] in CHAMPS:
            texte = CHAMPS[c["column_name"]].replace("'", "''")
            ordres.append(f"COMMENT ON COLUMN {c['table_schema']}.{c['table_name']}."
                          f"{c['column_name']} IS '{texte}';")
    psql("\n".join(ordres), utilisateur=config.PG_OWNER)
    log(f"  {len(ordres)} champs commentés dans la base")


# --- 6. Catalogue ------------------------------------------------------------------------
def remplir_catalogue():
    log("Catalogue des données (metadonnees.fiche)")
    lignes = []
    for f in catalogue.tout():
        table = f"{f['schema']}.{f['table']}"
        existe = psql(f"SELECT to_regclass('{table}') IS NOT NULL", utilisateur=config.PG_OWNER)
        if existe != "t":
            continue
        a_geom = psql("SELECT count(*) FROM information_schema.columns WHERE "
                      f"table_schema='{f['schema']}' AND table_name='{f['table']}' "
                      "AND column_name='geom'", utilisateur=config.PG_OWNER) == "1"
        emprise = (f"(SELECT ST_Envelope(ST_Expand(ST_SetSRID(ST_Extent(geom)::geometry, 2154), 1))"
                   f"::geometry(Polygon, 2154) FROM {table})"
                   if a_geom else "NULL")

        def q(v):
            if v is None:
                return "NULL"
            if isinstance(v, list):
                return "ARRAY[" + ",".join(q(x) for x in v) + "]::text[]"
            return "'" + str(v).replace("'", "''") + "'"

        lignes.append(
            f"({q(f['identifiant'])}::uuid, {q(table)}, {q(f['titre'])}, {q(f['resume'])}, "
            f"{q(f['theme_inspire'])}, {q(f['mots_cles'])}, {q(f['producteur'])}, "
            f"'Service des systèmes d''information (SIG)', {q(f['licence'])}, "
            f"{q(f['niveau_diffusion'])}, {q(f['motif_restriction'])}, {q(f['source_url'])}, "
            f"{q(f['millesime'])}, {q(f['frequence_maj'])}, {q(f['echelle'])}, "
            f"(SELECT count(*) FROM {table}), {emprise})")
        psql(f"COMMENT ON TABLE {table} IS {q(f['titre'] + ' - ' + f['resume'])}",
             utilisateur=config.PG_OWNER)
    psql("TRUNCATE metadonnees.fiche; INSERT INTO metadonnees.fiche (identifiant, table_nom, "
         "titre, resume, theme_inspire, mots_cles, producteur, gestionnaire, licence, "
         "niveau_diffusion, motif_restriction, source_url, millesime, frequence_maj, echelle, "
         "nb_objets, emprise) VALUES " + ",\n".join(lignes), utilisateur=config.PG_OWNER)
    log(f"  -> {len(lignes)} fiches")


def sauvegarder():
    dossier = config.LIVRABLES / "02_Base_PostGIS"
    dossier.mkdir(parents=True, exist_ok=True)
    log("Sauvegarde de la base (pg_dump)")
    dump = str(config.PG_BIN / "pg_dump.exe")
    base = ["-U", config.PG_SUPERUSER, "-d", config.PG_DB, "--no-owner", "--no-privileges"]
    subprocess.run([dump, *base[:4], "-Fc", "-f", str(dossier / "sig_ccst.backup")],
                   check=True, env=pg_env())
    subprocess.run([dump, *base, "--schema-only", "-f", str(dossier / "sig_ccst_structure.sql")],
                   check=True, env=pg_env())
    log(f"  -> {dossier.relative_to(config.ROOT)}")


def main():
    instance()
    base_neuve()
    log("Chargement des référentiels")
    charger_referentiels()
    espaces_verts()
    for f in ("04_urbanisme.sql", "05_controles.sql", "06_diffusion.sql", "07_indicateurs.sql"):
        log(f"Exécution de sql/{f}")
        psql(fichier=config.SQL / f, utilisateur=config.PG_OWNER)
    remplir_catalogue()
    commenter_colonnes()
    psql("VACUUM ANALYZE")
    sauvegarder()


if __name__ == "__main__":
    main()
