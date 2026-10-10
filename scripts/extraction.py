"""Procédure de diffusion : extraction de données pour un demandeur.

Applique la charte de diffusion au moment de l'extraction :
  - jeu "ouverte"    : livré à tous, avec sa licence
  - jeu "interne"    : livré à un service de la collectivité ; pour un tiers,
                       remplacé par sa version publique si elle existe, sinon refusé
  - jeu "restreinte" : livré seulement sous convention (référence obligatoire)
Chaque extraction produit une archive (GeoPackage, fiches de métadonnées,
licences, bordereau de diffusion signé) et une ligne dans le registre
metadonnees.journal_diffusion.

Exemple :
    python scripts/extraction.py --demandeur "Bureau d'études (exemple)" \\
        --objet "Étude de requalification de la RD 1059" --communes 67073 \\
        --jeux zone_urba prescription_surf sup_assiette_s zonage_naturel arbre
"""
import argparse
import re
import shutil
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pyogrio
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import Spacer, Table, TableStyle

import config
import pdf
from outils import log, pg_lire, psql

# version publique des jeux internes (schéma diffusion)
VERSIONS_PUBLIQUES = {"espaces_verts.arbre": "diffusion.v_arbre"}
MENTIONS = {
    "Licence Ouverte 2.0 (Etalab)": "Réutilisation libre, y compris commerciale, sous réserve de "
                                    "mentionner la source et la date de dernière mise à jour.",
    "Open Database License (ODbL) 1.0": "Partage à l'identique : toute base dérivée diffusée doit "
                                        "rester sous ODbL et mentionner « © contributeurs OpenStreetMap ».",
}


def slug(texte):
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")[:40]


def decider(fiche, interne, convention):
    """Renvoie (table à extraire, remarque) ou (None, motif du refus)."""
    table, niveau = fiche["table_nom"], fiche["niveau_diffusion"]
    if niveau == "ouverte":
        return table, ""
    if niveau == "interne":
        if interne:
            return table, "Diffusion interne à la collectivité"
        if table in VERSIONS_PUBLIQUES:
            return VERSIONS_PUBLIQUES[table], "Version publique livrée (champs internes retirés)"
        return None, f"Jeu interne : {fiche['motif_restriction']}"
    if niveau == "restreinte":
        if convention:
            return table, f"Livré sous convention {convention}"
        return None, f"Jeu restreint : convention requise ({fiche['motif_restriction']})"
    return None, "Niveau de diffusion inconnu"


def extraire(table, communes):
    """Objets du jeu situés sur les communes demandées."""
    liste = ",".join(f"'{c}'" for c in communes)
    cols = pg_lire(f"""SELECT column_name FROM information_schema.columns
                       WHERE table_schema || '.' || table_name = '{table}'""", geom=None)["column_name"]
    if "geom" in set(cols):
        sql = (f"SELECT t.* FROM {table} t WHERE EXISTS (SELECT 1 FROM ref_admin.commune c "
               f"WHERE c.code_insee IN ({liste}) AND ST_Intersects(c.geom, t.geom))")
        return pg_lire(sql)
    if "code_insee" in set(cols):
        return pg_lire(f"SELECT * FROM {table} WHERE code_insee IN ({liste})", geom=None)
    return pg_lire(f"SELECT * FROM {table}", geom=None)


def bordereau(chemin, args, lignes, refus, communes_noms, ref):
    H = [pdf.P("Bordereau de diffusion de données géographiques", "h1"),
         pdf.tableau([
             ["Référence", ref],
             ["Date", date.today().strftime("%d/%m/%Y")],
             ["Demandeur", args.demandeur],
             ["Objet de la demande", args.objet],
             ["Destinataire", "Service de la collectivité" if args.interne else "Tiers (externe)"],
             ["Périmètre", ", ".join(communes_noms)],
             ["Système de coordonnées", "RGF93 / Lambert-93 (EPSG:2154)"],
             ["Format", "GeoPackage (OGC), métadonnées ISO 19139"],
         ], [4.5 * cm, 12.5 * cm], entete=False),
         Spacer(1, 10), pdf.P("Jeux de données remis", "h2"),
         pdf.tableau([["Jeu de données", "Objets", "Licence", "Millésime", "Remarque"]] +
                     [[l["titre"], f"{l['nb']:,}".replace(",", " "), l["licence"], l["millesime"], l["remarque"]]
                      for l in lignes], [5 * cm, 1.5 * cm, 3.6 * cm, 2.9 * cm, 4 * cm])]
    if refus:
        H += [Spacer(1, 8), pdf.P("Jeux non remis", "h2"),
              pdf.tableau([["Jeu de données", "Motif"]] + [[t, m] for t, m in refus], [6 * cm, 11 * cm])]
    licences = sorted({l["licence"] for l in lignes})
    H += [Spacer(1, 8), pdf.P("Conditions de réutilisation", "h2")]
    H += pdf.puces([f"<b>{lic}</b> : {MENTIONS.get(lic, 'voir la fiche de métadonnées.')}" for lic in licences])
    H += pdf.puces([
        "Mention obligatoire sur tout document produit : « Sources : " +
        "; ".join(sorted({l['producteur'] for l in lignes})) + f" ; traitement SIG {config.EPCI_COURT}, "
        f"{date.today().year} ».",
        "Les données sont fournies en l'état, à la date indiquée. Les documents d'urbanisme et les "
        "servitudes n'ont pas de valeur opposable sous cette forme : seuls les actes approuvés font foi.",
        "Aucune donnée à caractère personnel n'est transmise. Toute demande portant sur les propriétaires "
        "(fichiers MAJIC) relève d'une procédure distincte (acte d'engagement, finalité déclarée).",
    ])
    visas = Table([["Visa du service SIG", "Accusé de réception du demandeur"], ["", ""]],
                  colWidths=[8.5 * cm, 8.5 * cm], rowHeights=[None, 2.4 * cm])
    visas.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Texte-Gras"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, 0), (-1, 0), pdf.ACCENT),
        ("BOX", (0, 0), (0, -1), 0.5, pdf.GRIS_CLAIR), ("BOX", (1, 0), (1, -1), 0.5, pdf.GRIS_CLAIR)]))
    H += [Spacer(1, 18), visas]
    pdf.construire(chemin, "Bordereau de diffusion", None, H, sujet=f"Diffusion {ref}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demandeur", required=True)
    ap.add_argument("--objet", required=True)
    ap.add_argument("--communes", nargs="+", required=True, help="codes INSEE")
    ap.add_argument("--jeux", nargs="+", required=True, help="noms de tables (ex. zone_urba arbre)")
    ap.add_argument("--interne", action="store_true", help="destinataire : service de la collectivité")
    ap.add_argument("--convention", help="référence de la convention (jeux restreints)")
    ap.add_argument("--reference", help="référence imposée (par défaut DIF-date-heure)")
    args = ap.parse_args(argv)

    fiches = pg_lire("SELECT * FROM metadonnees.fiche", geom=None)
    fiches["table"] = fiches["table_nom"].str.split(".").str[1]
    communes = pg_lire("SELECT code_insee, nom FROM ref_admin.commune", geom=None)
    inconnues = set(args.communes) - set(communes["code_insee"])
    if inconnues:
        raise SystemExit(f"Communes hors territoire : {', '.join(sorted(inconnues))}")
    noms = communes.set_index("code_insee").loc[args.communes, "nom"].tolist()

    ref = args.reference or f"DIF-{datetime.now():%Y%m%d-%H%M}"
    dossier = config.LIVRABLES / "09_Diffusion" / f"{ref}_{slug(args.demandeur)}"
    if dossier.exists():  # même référence : l'extraction est refaite
        shutil.rmtree(dossier)
    (dossier / "metadonnees").mkdir(parents=True, exist_ok=True)
    gpkg = dossier / "donnees.gpkg"
    lignes, refus = [], []
    for jeu in args.jeux:
        sel = fiches[(fiches["table"] == jeu) | (fiches["table_nom"] == jeu)]
        if sel.empty:
            refus.append((jeu, "Jeu inconnu du catalogue"))
            continue
        f = sel.iloc[0]
        table, remarque = decider(f, args.interne, args.convention)
        if table is None:
            refus.append((f["titre"], remarque))
            log(f"  refusé : {f['titre']} ({remarque})")
            continue
        df = extraire(table, args.communes)
        pyogrio.write_dataframe(df, gpkg, layer=f["table"], driver="GPKG")
        xml = config.LIVRABLES / "05_Metadonnees" / "iso19139" / f"{f['table_nom'].replace('.', '__')}.xml"
        if xml.exists():
            shutil.copy(xml, dossier / "metadonnees" / xml.name)
        lignes.append({"titre": f["titre"], "nb": len(df), "licence": f["licence"],
                       "millesime": f["millesime"], "remarque": remarque, "producteur": f["producteur"]})
        log(f"  {f['titre']} : {len(df)} objets ({table})")

    if not lignes:
        raise SystemExit("Aucun jeu ne peut être remis : voir les motifs ci-dessus.")
    bordereau(dossier / "Bordereau_de_diffusion.pdf", args, lignes, refus, noms, ref)
    (dossier / "LISEZMOI.txt").write_text(
        f"Diffusion {ref} - {args.demandeur}\nObjet : {args.objet}\nPérimètre : {', '.join(noms)}\n\n"
        "donnees.gpkg : une couche par jeu (Lambert-93), à ouvrir dans QGIS ou ArcGIS Pro.\n"
        "metadonnees/ : fiches ISO 19139 de chaque jeu.\n"
        "Bordereau_de_diffusion.pdf : liste des jeux, licences et conditions de réutilisation.\n",
        encoding="utf-8")
    archive = shutil.make_archive(str(dossier), "zip", dossier)
    def q(v):  # littéral SQL
        return "NULL" if v is None else "'" + str(v).replace("'", "''") + "'"

    psql("INSERT INTO metadonnees.journal_diffusion (demandeur, objet, destinataire, communes, jeux, "
         f"convention, fichier) VALUES ({q(args.demandeur)}, {q(args.objet)}, "
         f"{q('interne' if args.interne else 'externe')}, "
         f"ARRAY[{','.join(q(c) for c in args.communes)}]::text[], "
         f"ARRAY[{','.join(q(l['titre']) for l in lignes)}]::text[], "
         f"{q(args.convention)}, {q(Path(archive).relative_to(config.ROOT).as_posix())})",
         utilisateur=config.PG_OWNER)
    log(f"  -> {archive}")
    return archive


if __name__ == "__main__":
    main()
