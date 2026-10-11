"""Fonctions communes : accès WFS, base de travail GeoPackage, base PostGIS."""
import os
import subprocess
import time
from functools import lru_cache

import geopandas as gpd
import pandas as pd
import pyogrio
import requests

import config

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "sig-selestat-territoires (projet portfolio)"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def requete(url, params=None, data=None, timeout=180, essais=4):
    """GET (ou POST si data) avec reprise automatique en cas d'erreur réseau."""
    for essai in range(essais):
        try:
            if data is None:
                r = SESSION.get(url, params=params, timeout=timeout)
            else:
                r = SESSION.post(url, data=data, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as err:
            if essai == essais - 1:
                raise
            log(f"  nouvel essai ({err.__class__.__name__})")
            time.sleep(5 * (essai + 1))


def wfs(typename, cql=None, bbox=None, page=5000, sort=None):
    """Télécharge une couche WFS de la Géoplateforme IGN, page par page.

    cql  : filtre CQL (ex. "code_insee IN ('67462','67073')")
    bbox : (xmin, ymin, xmax, ymax) en Lambert-93, incompatible avec cql
    """
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": typename,
        "outputFormat": "application/json",
        "srsName": config.CRS,
        "count": page,
    }
    if cql:
        params["CQL_FILTER"] = cql
    if bbox is not None:
        params["BBOX"] = ",".join(str(round(v, 1)) for v in bbox) + f",{config.CRS}"
    if sort:
        params["sortBy"] = sort

    morceaux, debut = [], 0
    while True:
        params["startIndex"] = debut
        data = requete(config.WFS, params=params).json()
        feats = data.get("features", [])
        if not feats:
            break
        morceaux.append(gpd.GeoDataFrame.from_features(feats, crs=config.CRS))
        debut += len(feats)
        if len(feats) < page:
            break
    if not morceaux:
        return gpd.GeoDataFrame(geometry=[], crs=config.CRS)
    return gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs=config.CRS)


def cql_liste(champ, valeurs):
    return f"{champ} IN (" + ",".join(f"'{v}'" for v in valeurs) + ")"


# --- Base de travail GeoPackage ---------------------------------------------
def lire(couche, **kw):
    return gpd.read_file(config.GPKG, layer=couche, engine="pyogrio", **kw)


def ecrire(gdf, couche, gpkg=None):
    gpkg = gpkg or config.GPKG
    gpkg.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(gdf, gpd.GeoDataFrame):
        gdf.to_file(gpkg, layer=couche, driver="GPKG", engine="pyogrio")
    else:  # table attributaire
        pyogrio.write_dataframe(gdf, gpkg, layer=couche, driver="GPKG")
    log(f"  -> {couche} : {len(gdf)} entités")


def couches(gpkg=None):
    gpkg = gpkg or config.GPKG
    if not gpkg.exists():
        return set()
    return {nom for nom, _ in pyogrio.list_layers(gpkg)}


def communes():
    return lire("commune").sort_values("code_insee")


def codes_insee():
    return list(communes()["code_insee"])


# --- Base PostGIS -----------------------------------------------------------
def pg_env():
    env = os.environ.copy()
    env.update(PGHOST=config.PG_HOST, PGPORT=str(config.PG_PORT), PGCLIENTENCODING="UTF8",
               LC_ALL="C", LANG="C")  # messages de psql en ASCII, quelle que soit la langue du poste
    return env


def psql(sql=None, fichier=None, base=None, utilisateur=None, variables=None, capture=False):
    """Exécute du SQL avec psql (arrêt à la première erreur)."""
    cmd = [str(config.PG_BIN / "psql.exe"), "-X", "-q", "-v", "ON_ERROR_STOP=1",
           "-d", base or config.PG_DB, "-U", utilisateur or config.PG_SUPERUSER]
    for cle, val in (variables or {}).items():
        cmd += ["-v", f"{cle}={val}"]
    if fichier:
        cmd += ["-f", str(fichier)]
    else:
        # le SQL passe par l'entrée standard en UTF-8 : en argument de ligne de
        # commande, Windows le convertirait dans la page de code locale
        cmd += ["-At"]
    res = subprocess.run(cmd, env=pg_env(), capture_output=True, text=True, encoding="utf-8",
                         errors="replace", input=None if fichier else sql)
    if res.returncode != 0:
        raise RuntimeError(f"psql a échoué ({fichier or sql[:80]}) :\n{res.stderr}")
    if res.stderr.strip():
        for ligne in res.stderr.strip().splitlines():
            if not any(m in ligne for m in ("NOTICE", "DETAIL", "drop cascades")):
                log(f"  psql : {ligne}")
    return res.stdout.strip() if capture or sql else None


@lru_cache(maxsize=1)
def moteur():
    from sqlalchemy import create_engine
    url = (f"postgresql+psycopg2://{config.PG_SUPERUSER}@{config.PG_HOST}:"
           f"{config.PG_PORT}/{config.PG_DB}")
    return create_engine(url)


def pg_lire(sql, geom="geom"):
    if geom:
        return gpd.read_postgis(sql, moteur(), geom_col=geom)
    return pd.read_sql(sql, moteur())


def pg_ecrire(gdf, table, schema, mode="replace"):
    gdf.to_postgis(table, moteur(), schema=schema, if_exists=mode, index=False, chunksize=5000)
    log(f"  -> {schema}.{table} : {len(gdf)} entités")
