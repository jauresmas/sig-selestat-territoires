"""Import des saisies terrain (QField) dans la base PostGIS.

Lit le GeoPackage revenu de la tablette, le compare à la base par identifiant
(UUID) et applique les différences en une seule transaction :
  - arbres nouveaux        -> insérés (la base attribue le numéro et la commune)
  - arbres modifiés        -> mis à jour (champs changés seulement)
  - interventions nouvelles -> insérées (la base met à jour l'état de l'arbre)
  - photos (dossier DCIM)  -> copiées à côté du projet QGIS de production
Un arbre n'est mis à jour que s'il a été modifié sur le terrain après sa
dernière modification dans la base (date_maj, renseignée par QField à chaque
saisie) : la modification la plus récente l'emporte, et réimporter une tablette
restée en arrière n'écrase rien. Un arbre refusé par la base (hors territoire,
valeur incohérente) n'empêche pas l'import des autres : il est listé dans le
rapport. Rien n'est supprimé : un arbre absent du GeoPackage est seulement signalé.

Usage :
    python scripts/import_terrain.py chemin/inventaire_arbres.gpkg --simulation
    python scripts/import_terrain.py chemin/inventaire_arbres.gpkg
Options : --base, --port (autre base que celle de config.py), --photos (dossier DCIM).

Avec QFieldSync ou QFieldCloud sur le projet PostGIS, ce script n'est pas
nécessaire : la synchronisation écrit directement dans la base.
"""
import argparse
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg2
import pyogrio

import config
from outils import log

CHAMPS_ARBRE = ["essence", "implantation", "stade_dev", "hauteur_m", "circonference_cm",
                "annee_plantation", "etat_sanitaire", "risque", "remarquable", "date_diagnostic",
                "statut", "observations", "photo", "precision_m", "source_geom", "source_attributs"]
CHAMPS_INTERVENTION = ["arbre_id", "type_intervention", "date_intervention", "intervenant",
                       "cout_ht", "etat_constate", "commentaire"]
DATES = {"date_diagnostic", "date_intervention"}
ENTIERS = {"circonference_cm", "annee_plantation"}
DECIMAUX = {"hauteur_m", "precision_m", "cout_ht"}


def propre(champ, v):
    """Valeur du GeoPackage -> valeur Python comparable à celle de la base."""
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    if champ in DATES:
        return pd.Timestamp(v).date()
    if champ in ENTIERS:
        return int(float(v))
    if champ in DECIMAUX:
        return round(float(v), 2)
    if champ == "remarquable":
        return bool(v)
    if hasattr(v, "item"):  # types numpy
        v = v.item()
    if isinstance(v, float):
        return round(v, 2)
    return v


def horodatage(v):
    """date_maj du GeoPackage (enregistrée en UTC) ou de la base -> datetime UTC."""
    if v is None or v is pd.NaT or (isinstance(v, float) and math.isnan(v)):
        return None
    t = pd.Timestamp(v)
    return (t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")).to_pydatetime()


def egal(a, b):
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(float(a) - float(b)) < 0.01
    return a == b


def lire_base(cur, sql, cle="id"):
    cur.execute(sql)
    noms = [d[0] for d in cur.description]
    return {str(r[noms.index(cle)]): dict(zip(noms, r)) for r in cur.fetchall()}


def importer(gpkg, cur, rapport, auteur):
    arbres = pyogrio.read_dataframe(gpkg, layer="arbre")
    inters = pyogrio.read_dataframe(gpkg, layer="intervention", read_geometry=False)
    base_a = lire_base(cur, "SELECT id::text AS id, " + ", ".join(CHAMPS_ARBRE)
                       + ", date_maj, ST_AsBinary(geom) AS wkb FROM espaces_verts.arbre")
    base_i = lire_base(cur, "SELECT id::text AS id FROM espaces_verts.intervention")
    ids_terrain = set(arbres["id"].astype(str))
    plus_recents_en_base = 0

    for _, a in arbres.iterrows():
        id_ = str(a["id"])
        valeurs = {c: propre(c, a[c]) for c in CHAMPS_ARBRE if c in arbres.columns}
        wkb = a.geometry.wkb if a.geometry is not None else None
        cur.execute("SAVEPOINT arbre")
        try:
            if id_ not in base_a:
                cols = ["id"] + list(valeurs) + ["auteur_creation", "date_creation", "geom"]
                cur.execute(
                    f"INSERT INTO espaces_verts.arbre ({', '.join(cols)}) VALUES "
                    f"(%s, {', '.join(['%s'] * len(valeurs))}, %s, %s, ST_GeomFromWKB(%s, 2154)) "
                    "RETURNING numero, code_insee",
                    [id_, *valeurs.values(), propre("x", a.get("auteur_creation")) or auteur,
                     propre("x", a.get("date_creation")) or datetime.now(), psycopg2.Binary(wkb)])
                numero, insee = cur.fetchone()
                rapport.append(("arbre", "ajouté", numero, insee))
            else:
                ancien = base_a[id_]
                changes = {c: v for c, v in valeurs.items() if not egal(v, ancien.get(c))}
                deplace = wkb is not None and bytes(ancien["wkb"]) != wkb
                maj_terrain = horodatage(a.get("date_maj"))
                maj_base = horodatage(ancien.get("date_maj"))
                plus_recent = maj_terrain is not None and (maj_base is None or maj_terrain > maj_base)
                if not changes and not deplace:
                    cur.execute("RELEASE SAVEPOINT arbre")
                    continue
                if not plus_recent:  # la base est plus récente que la tablette : on la garde
                    cur.execute("RELEASE SAVEPOINT arbre")
                    plus_recents_en_base += 1
                    continue
                sets = [f"{c} = %s" for c in changes] + ["auteur_maj = %s"]
                params = [*changes.values(), propre("x", a.get("auteur_maj")) or auteur]
                if deplace:
                    sets.append("geom = ST_GeomFromWKB(%s, 2154)")
                    params.append(psycopg2.Binary(wkb))
                cur.execute(f"UPDATE espaces_verts.arbre SET {', '.join(sets)} WHERE id = %s "
                            "RETURNING numero", [*params, id_])
                detail = ", ".join(sorted(changes)) + (" + position" if deplace else "")
                rapport.append(("arbre", "modifié", cur.fetchone()[0], detail))
            cur.execute("RELEASE SAVEPOINT arbre")
        except psycopg2.Error as err:
            cur.execute("ROLLBACK TO SAVEPOINT arbre")
            message = (err.diag.message_primary or str(err)).strip()
            rapport.append(("arbre", "refusé", a.get("numero") or id_[:8], message))

    if plus_recents_en_base:
        rapport.append(("arbre", "conservé en base", f"{plus_recents_en_base} arbre(s)",
                        "différents sur la tablette mais modifiés plus récemment dans la base"))
    absents = [v for k, v in base_a.items() if k not in ids_terrain]
    if absents:
        rapport.append(("arbre", "absent du terrain", f"{len(absents)} arbre(s)",
                        "non supprimés : vérifier s'ils ont été retirés volontairement"))

    for _, i in inters.sort_values("date_intervention").iterrows():
        id_ = str(i["id"])
        if id_ in base_i:
            continue
        valeurs = {c: propre(c, i[c]) for c in CHAMPS_INTERVENTION}
        cur.execute("SAVEPOINT inter")
        try:
            cols = ["id", *valeurs, "auteur_creation", "date_creation"]
            cur.execute(f"INSERT INTO espaces_verts.intervention ({', '.join(cols)}) VALUES "
                        f"({', '.join(['%s'] * len(cols))})",
                        [id_, *valeurs.values(), propre("x", i.get("auteur_creation")) or auteur,
                         propre("x", i.get("date_creation")) or datetime.now()])
            cur.execute("RELEASE SAVEPOINT inter")
            rapport.append(("intervention", "ajoutée", valeurs["type_intervention"],
                            str(valeurs["date_intervention"])))
        except psycopg2.Error as err:
            cur.execute("ROLLBACK TO SAVEPOINT inter")
            rapport.append(("intervention", "refusée", valeurs["type_intervention"],
                            (err.diag.message_primary or str(err)).strip()))


def copier_photos(dossier, rapport):
    """Photos du terrain -> à côté du projet de production (chemins relatifs DCIM/...)."""
    if not dossier or not Path(dossier).is_dir():
        return
    cible = config.QGIS_DIR / "DCIM"
    cible.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in Path(dossier).glob("*.jp*g"):
        if not (cible / f.name).exists():
            shutil.copy2(f, cible / f.name)
            n += 1
    if n:
        rapport.append(("photo", "copiée", f"{n} photo(s)", str(cible)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gpkg", type=Path, help="GeoPackage revenu du terrain")
    ap.add_argument("--photos", type=Path, help="dossier DCIM (par défaut : à côté du GeoPackage)")
    ap.add_argument("--simulation", action="store_true", help="tout vérifier sans rien enregistrer")
    ap.add_argument("--base", default=config.PG_DB)
    ap.add_argument("--port", type=int, default=config.PG_PORT)
    ap.add_argument("--utilisateur", default=config.PG_OWNER)
    args = ap.parse_args(argv)
    if not args.gpkg.exists():
        raise SystemExit(f"GeoPackage introuvable : {args.gpkg}")

    cnx = psycopg2.connect(host=config.PG_HOST, port=args.port, dbname=args.base,
                           user=args.utilisateur)
    rapport = []
    try:
        with cnx.cursor() as cur:
            importer(args.gpkg, cur, rapport, auteur=f"import QField ({args.utilisateur})")
            ajoutes = sum(1 for r in rapport if r[1] in ("ajouté", "ajoutée", "modifié"))
            cur.execute("INSERT INTO metadonnees.journal_integration (table_nom, nb_objets, source, script) "
                        "VALUES ('espaces_verts.arbre', %s, %s, 'scripts/import_terrain.py')",
                        [ajoutes, f"QField : {args.gpkg.name}"])
        if args.simulation:
            cnx.rollback()
        else:
            cnx.commit()
            copier_photos(args.photos or args.gpkg.parent / "DCIM", rapport)
    finally:
        cnx.close()

    titre = "SIMULATION (rien n'est enregistré)" if args.simulation else "Import enregistré"
    log(f"{titre} : {args.gpkg}")
    if not rapport:
        log("  aucune différence avec la base")
    for objet, action, qui, detail in rapport:
        log(f"  {objet:<12} {action:<18} {qui} {('- ' + detail) if detail else ''}")
    resume = pd.Series([f"{o} {a}" for o, a, _, _ in rapport]).value_counts()
    for cle, n in resume.items():
        log(f"  total {cle} : {n}")
    return rapport


if __name__ == "__main__":
    main()
