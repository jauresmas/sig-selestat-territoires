"""Étape 5 - Données de la carte web (docs/, publiée avec GitHub Pages).

Exporte les vues de diffusion en GeoJSON allégé (WGS84, géométries simplifiées,
coordonnées arrondies). La carte web les croise côté navigateur avec la parcelle
interrogée (API Carto de l'IGN) pour éditer la fiche de renseignements.
"""
import json
from datetime import date

import config
from outils import log, pg_lire

EXPORTS = {
    "epci": ("SELECT siren, nom, population, surface_ha, geom FROM ref_admin.epci", 10),
    "communes": ("SELECT * FROM diffusion.v_indicateurs_commune", 5),
    "zonage": ("""SELECT z.code_insee, z.libelle, z.libelong, z.typezone, z.url_reglement, z.geom
                  FROM urbanisme.zone_urba z""", 1),
    "prescriptions": ("""SELECT p.code_insee, p.typepsc, coalesce(t.libelle, 'Prescription') AS type_libelle,
                                p.libelle, p.geom
                         FROM urbanisme.prescription_surf p
                         LEFT JOIN urbanisme.type_prescription t ON t.code = p.typepsc""", 1),
    "informations": ("""SELECT i.code_insee, i.typeinf, coalesce(t.libelle, 'Information') AS type_libelle,
                               i.libelle, i.geom
                        FROM urbanisme.info_surf i
                        LEFT JOIN urbanisme.type_information t ON t.code = i.typeinf""", 2),
    "servitudes": ("SELECT suptype, categorie_libelle, objet, geom FROM servitudes.v_assiette_s", 4),
    "nature": ("""SELECT type_zonage, libelle_type, nom, url_inpn, geom
                  FROM environnement.zonage_naturel""", 5),
    "arbres": ("""SELECT a.numero, a.code_insee, a.essence, a.nom_francais, a.implantation,
                         a.stade_dev, a.hauteur_m, a.circonference_cm, a.etat_sanitaire,
                         a.remarquable, a.geom
                  FROM diffusion.v_arbre a""", 0),
}


def main():
    dossier = config.DOCS / "data"
    dossier.mkdir(parents=True, exist_ok=True)
    meta = {"genere_le": date.today().isoformat(), "territoire": config.EPCI_NOM,
            "siren": config.EPCI_SIREN, "couches": {}}
    for nom, (sql, tolerance) in EXPORTS.items():
        gdf = pg_lire(sql)
        if tolerance:
            gdf["geom"] = gdf.geometry.simplify(tolerance, preserve_topology=True)
        gdf = gdf[~gdf.geometry.is_empty].to_crs(4326)
        for c in gdf.columns:
            if str(gdf[c].dtype).startswith(("datetime", "date")) or gdf[c].dtype == object:
                if c != "geom":
                    gdf[c] = gdf[c].astype(str).where(gdf[c].notna(), None)
        chemin = dossier / f"{nom}.geojson"
        chemin.unlink(missing_ok=True)
        gdf.to_file(chemin, driver="GeoJSON", engine="pyogrio",
                    layer_options={"COORDINATE_PRECISION": 6 if nom == "arbres" else 5,
                                   "RFC7946": "YES"})
        taille = chemin.stat().st_size / 1e6
        meta["couches"][nom] = {"objets": len(gdf), "taille_mo": round(taille, 2)}
        log(f"  {nom} : {len(gdf)} objets, {taille:.2f} Mo")
    (dossier / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
