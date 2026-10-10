"""Catalogue des jeux de données : source unique des métadonnées.

Chaque entrée décrit une couche de la base de travail et sa table cible dans
PostGIS. Le catalogue sert à charger la base (schéma, clé primaire), à
renseigner la table metadonnees.fiche, à produire les fiches XML ISO 19139,
les métadonnées des couches QGIS et le catalogue de la carte web.
"""
import uuid

LO = "Licence Ouverte 2.0 (Etalab)"
ODBL = "Open Database License (ODbL) 1.0"

IGN = "IGN - Institut national de l'information géographique et forestière"
GPU = "Collectivités compétentes en urbanisme, via le Géoportail de l'Urbanisme"
DEMO = "Projet de démonstration (étude indépendante)"


def _f(couche, schema, table, cle, titre, resume, theme, mots_cles, producteur,
       licence, source_url, millesime, frequence, echelle="1:5 000",
       diffusion="ouverte", motif=None):
    return {
        "couche": couche, "schema": schema, "table": table, "cle": cle,
        "titre": titre, "resume": resume, "theme_inspire": theme, "mots_cles": mots_cles,
        "producteur": producteur, "licence": licence, "source_url": source_url,
        "millesime": millesime, "frequence_maj": frequence, "echelle": echelle,
        "niveau_diffusion": diffusion, "motif_restriction": motif,
        "identifiant": str(uuid.uuid5(uuid.NAMESPACE_URL, f"sig-ccst/{schema}.{table}")),
    }


CATALOGUE = [
    _f("commune", "ref_admin", "commune", "code_insee",
       "Limites communales",
       "Contours des 12 communes de la communauté de communes, avec leur population légale. "
       "Référentiel de rattachement de toutes les autres données.",
       "Unités administratives", ["limites administratives", "commune", "population"],
       IGN, LO, "https://geoservices.ign.fr/adminexpress", "ADMIN EXPRESS COG 2026", "annuelle"),
    _f("epci", "ref_admin", "epci", "siren",
       "Périmètre intercommunal",
       "Périmètre de la communauté de communes, obtenu par fusion des limites communales.",
       "Unités administratives", ["EPCI", "intercommunalité"],
       IGN, LO, "https://geoservices.ign.fr/adminexpress", "ADMIN EXPRESS COG 2026", "annuelle"),
    _f("parcelle", "ref_cadastre", "parcelle", "idu",
       "Parcelles cadastrales",
       "Plan cadastral informatisé vectorisé (PCI) : géométrie, section, numéro et contenance "
       "de chaque parcelle. Ne contient aucune donnée sur les propriétaires.",
       "Parcelles cadastrales", ["cadastre", "parcelle", "PCI", "foncier"],
       IGN + " / DGFiP", LO, "https://geoservices.ign.fr/parcellaire-express-pci",
       "Parcellaire Express 2026", "semestrielle", "1:2 000"),
    _f("adresse", "ref_adresse", "adresse", "cle_interop",
       "Adresses",
       "Points adresses de la Base Adresse Nationale : numéro, voie, position, parcelle de "
       "rattachement et certification par la commune.",
       "Adresses", ["adresse", "BAN", "voie", "numérotation"],
       "Base Adresse Nationale (communes, IGN, DGFiP, La Poste)", LO,
       "https://adresse.data.gouv.fr", "BAN octobre 2026", "hebdomadaire", "1:1 000"),
    _f("batiment", "ref_topo", "batiment", "cleabs",
       "Bâtiments",
       "Bâtiments de la BD TOPO avec usage, nombre de logements, hauteur et identifiant RNB.",
       "Bâtiments", ["bâti", "BD TOPO", "RNB"], IGN, LO,
       "https://geoservices.ign.fr/bdtopo", "BD TOPO 2026", "trimestrielle"),
    _f("troncon_route", "ref_topo", "troncon_route", "cleabs",
       "Tronçons de route",
       "Réseau routier de la BD TOPO : nature, importance, nom de voie, largeur, sens de circulation.",
       "Réseaux de transport", ["voirie", "route", "BD TOPO"], IGN, LO,
       "https://geoservices.ign.fr/bdtopo", "BD TOPO 2026", "trimestrielle"),
    _f("troncon_hydro", "ref_topo", "troncon_hydro", "cleabs",
       "Cours d'eau",
       "Tronçons hydrographiques de la BD TOPO : Ill, Giessen, Lièpvrette, Blind et cours d'eau phréatiques du Ried.",
       "Hydrographie", ["hydrographie", "cours d'eau", "Ried"], IGN, LO,
       "https://geoservices.ign.fr/bdtopo", "BD TOPO 2026", "trimestrielle"),
    _f("surface_hydro", "ref_topo", "surface_hydro", "cleabs",
       "Surfaces en eau",
       "Plans d'eau et surfaces hydrographiques de la BD TOPO.",
       "Hydrographie", ["hydrographie", "plan d'eau"], IGN, LO,
       "https://geoservices.ign.fr/bdtopo", "BD TOPO 2026", "trimestrielle"),
    _f("equipement", "ref_topo", "equipement", "cleabs",
       "Équipements et sites d'intérêt",
       "Zones d'activité ou d'intérêt de la BD TOPO : enseignement, santé, sport, administration, culture.",
       "Services d'utilité publique et services publics", ["équipement public", "école", "mairie"],
       IGN, LO, "https://geoservices.ign.fr/bdtopo", "BD TOPO 2026", "trimestrielle"),
    _f("cimetiere", "ref_topo", "cimetiere", "cleabs",
       "Cimetières", "Emprises des cimetières (BD TOPO).",
       "Services d'utilité publique et services publics", ["cimetière"], IGN, LO,
       "https://geoservices.ign.fr/bdtopo", "BD TOPO 2026", "trimestrielle"),
    _f("terrain_sport", "ref_topo", "terrain_sport", "cleabs",
       "Terrains de sport", "Terrains et équipements sportifs de plein air (BD TOPO).",
       "Services d'utilité publique et services publics", ["sport"], IGN, LO,
       "https://geoservices.ign.fr/bdtopo", "BD TOPO 2026", "trimestrielle"),
    _f("doc_urba", "urbanisme", "doc_urba", "code_insee",
       "Documents d'urbanisme en vigueur",
       "Un enregistrement par commune : type de document (PLU, carte communale), date "
       "d'approbation et dernière procédure, au standard CNIG.",
       "Usage des sols", ["PLU", "document d'urbanisme", "CNIG", "GPU"], GPU, LO,
       "https://www.geoportail-urbanisme.gouv.fr", "GPU octobre 2026", "à chaque procédure", None),
    _f("zone_urba", "urbanisme", "zone_urba", None,
       "Zonage des PLU",
       "Zones urbaines (U), à urbaniser (AU), agricoles (A) et naturelles (N) des plans "
       "locaux d'urbanisme, avec le lien vers le règlement écrit.",
       "Usage des sols", ["PLU", "zonage", "urbanisme réglementaire"], GPU, LO,
       "https://www.geoportail-urbanisme.gouv.fr", "GPU octobre 2026", "à chaque procédure"),
    _f("prescription_surf", "urbanisme", "prescription_surf", None,
       "Prescriptions surfaciques des PLU",
       "Espaces boisés classés, éléments de paysage protégés, emplacements réservés, secteurs d'OAP...",
       "Usage des sols", ["PLU", "prescription", "EBC", "emplacement réservé"], GPU, LO,
       "https://www.geoportail-urbanisme.gouv.fr", "GPU octobre 2026", "à chaque procédure"),
    _f("prescription_lin", "urbanisme", "prescription_lin", None,
       "Prescriptions linéaires des PLU",
       "Linéaires protégés (haies, alignements, commerces), reculs et marges graphiques.",
       "Usage des sols", ["PLU", "prescription"], GPU, LO,
       "https://www.geoportail-urbanisme.gouv.fr", "GPU octobre 2026", "à chaque procédure"),
    _f("prescription_pct", "urbanisme", "prescription_pct", None,
       "Prescriptions ponctuelles des PLU",
       "Éléments ponctuels protégés (arbres remarquables, petit patrimoine).",
       "Usage des sols", ["PLU", "prescription", "patrimoine"], GPU, LO,
       "https://www.geoportail-urbanisme.gouv.fr", "GPU octobre 2026", "à chaque procédure"),
    _f("info_surf", "urbanisme", "info_surf", None,
       "Informations surfaciques des PLU",
       "Périmètres reportés à titre d'information (droit de préemption, risques, ZAC...).",
       "Usage des sols", ["PLU", "information"], GPU, LO,
       "https://www.geoportail-urbanisme.gouv.fr", "GPU octobre 2026", "à chaque procédure"),
    _f("sup_assiette_s", "servitudes", "sup_assiette_s", None,
       "Servitudes d'utilité publique (assiettes)",
       "Emprises où s'applique une servitude : abords des monuments historiques (AC1), "
       "plans de prévention des risques (PM1), protection des captages (AS1), réseaux...",
       "Zones de gestion, de restriction ou de réglementation et unités de déclaration",
       ["servitude", "SUP", "monument historique", "PPR"],
       "Gestionnaires des servitudes (UDAP, DDT, ARS, opérateurs de réseaux), via le GPU", LO,
       "https://www.geoportail-urbanisme.gouv.fr", "GPU octobre 2026", "continue"),
    _f("sup_generateur_s", "servitudes", "sup_generateur_s", None,
       "Servitudes d'utilité publique (générateurs surfaciques)",
       "Objets qui génèrent une servitude : monuments historiques, sites, captages.",
       "Zones de gestion, de restriction ou de réglementation et unités de déclaration",
       ["servitude", "SUP", "générateur"],
       "Gestionnaires des servitudes, via le GPU", LO,
       "https://www.geoportail-urbanisme.gouv.fr", "GPU octobre 2026", "continue"),
    _f("sup_generateur_l", "servitudes", "sup_generateur_l", None,
       "Servitudes d'utilité publique (générateurs linéaires)",
       "Canalisations, lignes électriques et voies qui génèrent une servitude.",
       "Zones de gestion, de restriction ou de réglementation et unités de déclaration",
       ["servitude", "SUP", "réseau"],
       "Gestionnaires des servitudes, via le GPU", LO,
       "https://www.geoportail-urbanisme.gouv.fr", "GPU octobre 2026", "continue"),
    _f("sup_generateur_p", "servitudes", "sup_generateur_p", None,
       "Servitudes d'utilité publique (générateurs ponctuels)",
       "Objets ponctuels qui génèrent une servitude.",
       "Zones de gestion, de restriction ou de réglementation et unités de déclaration",
       ["servitude", "SUP"], "Gestionnaires des servitudes, via le GPU", LO,
       "https://www.geoportail-urbanisme.gouv.fr", "GPU octobre 2026", "continue"),
    _f("zonage_naturel", "environnement", "zonage_naturel", None,
       "Zonages du patrimoine naturel",
       "Natura 2000, ZNIEFF, réserve naturelle régionale du Ried de Sélestat (Ill*Wald) et "
       "arrêtés de protection de biotope qui concernent le territoire.",
       "Sites protégés", ["Natura 2000", "ZNIEFF", "réserve naturelle", "biodiversité", "Ried"],
       "MNHN - PatriNat (INPN), DREAL Grand Est", LO,
       "https://inpn.mnhn.fr", "INPN 2026", "annuelle", "1:25 000"),
]

# Données métier : créées par sql/03_espaces_verts.sql, pas par chargement
CATALOGUE_METIER = [
    _f(None, "espaces_verts", "arbre", "id",
       "Inventaire du patrimoine arboré",
       "Arbres gérés par la collectivité : essence, dimensions, état sanitaire, risque et "
       "historique. Positions issues d'OpenStreetMap ; attributs simulés pour la démonstration.",
       "Répartition des espèces", ["arbre", "espaces verts", "patrimoine arboré", "QField"],
       DEMO, ODBL, "https://www.openstreetmap.org", "Inventaire 2026", "continue (saisie terrain)",
       "1:500", "interne",
       "Contient des observations libres et l'identité des agents ; version publique : diffusion.v_arbre"),
    _f(None, "espaces_verts", "intervention", "id",
       "Interventions sur le patrimoine arboré",
       "Historique des diagnostics, tailles, élagages et abattages, avec leur coût.",
       "Répartition des espèces", ["arbre", "intervention", "gestion"],
       DEMO, ODBL, None, "2022-2026", "continue (saisie terrain)", "1:500", "interne",
       "Coûts et prestataires : informations de gestion interne"),
]


def par_couche():
    return {f["couche"]: f for f in CATALOGUE}


def tout():
    return CATALOGUE + CATALOGUE_METIER
