"""Étape 7 - Documents d'accompagnement et visuels.

  - aperçus PNG des planches (tirés des PDF exportés par QGIS)
  - captures de la carte web (navigateur sans interface, Playwright)
  - schéma d'architecture
  - PDF : note d'architecture, charte de diffusion, fiches tutoriel, bordereau
Les chiffres sont lus dans la base PostGIS : relancer la chaîne met les
documents à jour.
"""
import functools
import http.server
import socketserver
import threading
import unicodedata
from pathlib import Path

import matplotlib
import pymupdf
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, PageBreak, Spacer

import config
import pdf
from outils import log, pg_lire
from pdf import P, code, encadre, etapes, figure, puces, tableau

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

DOCS_PDF = config.LIVRABLES / "01_Documents"
IMG = config.DOCS / "img"
CARTES = config.LIVRABLES / "06_Cartes"


def nb(v, d=0):
    return f"{float(v):,.{d}f}".replace(",", " ").replace(".", ",")


# =============================================================================
# Visuels
# =============================================================================
def apercus_planches():
    log("Aperçus PNG des planches")
    for f in sorted(CARTES.glob("P*.pdf")):
        page = pymupdf.open(f)[0]
        page.get_pixmap(dpi=110).save(CARTES / f"{f.stem}.png")
    atlas = config.LIVRABLES / "07_Atlas_communal" / "Atlas_communal.pdf"
    if atlas.exists():
        # pages triées par nom de commune (le texte du PDF est vectorisé, donc non cherchable)
        noms = pg_lire("SELECT nom FROM ref_admin.commune", geom=None)["nom"].tolist()
        cle = lambda n: unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()  # noqa: E731
        rang = sorted(noms, key=cle).index("Sélestat")
        pymupdf.open(atlas)[rang].get_pixmap(dpi=90).save(IMG / "atlas_selestat.png")


def captures_web():
    """Captures de la carte web servie en local (Playwright, Chromium sans interface)."""
    from playwright.sync_api import sync_playwright
    log("Captures de la carte web")
    class Silencieux(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    gestionnaire = functools.partial(Silencieux, directory=str(config.DOCS))
    with socketserver.TCPServer(("127.0.0.1", 0), gestionnaire) as serveur:
        port = serveur.server_address[1]
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        with sync_playwright() as pw:
            nav = pw.chromium.launch()
            page = nav.new_page(viewport={"width": 1440, "height": 860}, device_scale_factor=1)
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            page.wait_for_timeout(2500)
            page.screenshot(path=str(IMG / "web_vue_generale.png"))
            page.fill("#q", "67462 03 174")
            page.press("#q", "Enter")
            page.wait_for_selector(".fiche", timeout=30000)
            page.wait_for_timeout(3500)
            page.screenshot(path=str(IMG / "web_fiche_parcelle.png"))
            page.click("button[data-onglet='communes']")
            page.wait_for_timeout(600)
            page.click(".leaflet-control-zoom-out")
            page.click(".leaflet-control-zoom-out")
            page.wait_for_timeout(2500)
            page.screenshot(path=str(IMG / "web_communes.png"))
            page.click("button[data-onglet='donnees']")
            page.wait_for_timeout(800)
            page.screenshot(path=str(IMG / "web_catalogue.png"))
            nav.close()
        serveur.shutdown()


def schema_architecture():
    log("Schéma d'architecture")
    fig, ax = plt.subplots(figsize=(11, 6.2), dpi=160)
    ax.set_xlim(0, 110)
    ax.set_ylim(0, 62)
    ax.axis("off")
    teal, pale, gris = "#1f4e5a", "#d9e8eb", "#4f5a60"

    def boite(x, y, w, h, titre, lignes, fond=pale, bord=teal, couleur_titre=teal):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                    fc=fond, ec=bord, lw=1.2))
        ax.text(x + w / 2, y + h - 2.6, titre, ha="center", va="top", fontsize=9.5,
                fontweight="bold", color=couleur_titre)
        ax.text(x + w / 2, y + h - 6.6, "\n".join(lignes), ha="center", va="top", fontsize=7.6,
                color="#1d2327", linespacing=1.45)

    def fleche(x1, y1, x2, y2, texte=None):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
                                     lw=1.3, color=gris))
        if texte:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 1.2, texte, ha="center", fontsize=7, color=gris,
                    style="italic")

    boite(1, 34, 21, 26, "Sources ouvertes", ["IGN : ADMIN EXPRESS,", "BD TOPO, Parcellaire Express",
          "Géoportail de l'Urbanisme", "(PLU CNIG, servitudes)", "Base Adresse Nationale",
          "INPN (Natura 2000, ZNIEFF)", "OpenStreetMap (arbres)"], fond="#ffffff")
    boite(1, 3, 21, 26, "Terrain", ["QField sur tablette", "formulaires, photos, GNSS",
          "hors connexion", "", "synchronisation", "QFieldSync / QFieldCloud"], fond="#ffffff")
    boite(28, 34, 22, 26, "Chaîne Python", ["flux WFS et API", "normalisation, Lambert-93",
          "correction d'encodage", "contrôles qualité", "métadonnées ISO 19139", "rejouable : run_all.py"])
    ax.add_patch(FancyBboxPatch((56, 3), 24, 57, boxstyle="round,pad=0.4,rounding_size=1.2",
                                fc=teal, ec=teal))
    ax.text(68, 57.4, "PostgreSQL / PostGIS", ha="center", va="top", fontsize=10.5, fontweight="bold",
            color="white")
    schemas = ["ref_admin · ref_cadastre", "ref_adresse · ref_topo", "urbanisme · servitudes",
               "environnement", "espaces_verts (métier)", "metadonnees · controle", "diffusion (public)"]
    for i, s in enumerate(schemas):
        ax.add_patch(FancyBboxPatch((58, 46.5 - i * 5.4), 20, 3.9, boxstyle="round,pad=0.2,rounding_size=0.8",
                                    fc="#2f6f7e", ec="none"))
        ax.text(68, 48.4 - i * 5.4, s, ha="center", va="center", fontsize=7.6, color="white")
    ax.text(68, 7.6, "rôles : admin · éditeur\nlecteur · public\ndéclencheurs · journal", ha="center",
            va="center", fontsize=7.3, color=pale, linespacing=1.4)
    boite(86, 45, 23, 15, "QGIS (bureau)", ["consultation, édition", "thèmes, planches, atlas"])
    boite(86, 27, 23, 15, "Carte web", ["fiche parcelle, communes", "Leaflet · Lizmap en prod."])
    boite(86, 3, 23, 21, "Diffusion", ["open data (GeoJSON, CSV)", "extractions + bordereau",
          "catalogue GeoNetwork", ".gdb pour ArcGIS"])
    fleche(22.5, 47, 27.5, 47, "WFS / API")
    fleche(50.5, 47, 55.5, 47)
    fleche(22.5, 16, 55.5, 16, "synchronisation")
    fleche(80.5, 52, 85.5, 52)
    fleche(80.5, 34, 85.5, 34)
    fleche(80.5, 13, 85.5, 13)
    fig.tight_layout()
    fig.savefig(IMG / "architecture.png", facecolor="white")
    plt.close(fig)


# =============================================================================
# Données pour les documents
# =============================================================================
def chiffres():
    q = lambda sql: pg_lire(sql, geom=None)  # noqa: E731
    c = {}
    c["ind"] = q("SELECT * FROM (SELECT * FROM ref_admin.mv_indicateurs_commune) x").drop(columns="geom")
    c["qc"] = q("SELECT * FROM controle.v_synthese")
    c["fiches"] = q("SELECT * FROM metadonnees.fiche ORDER BY table_nom")
    c["tables"] = q("""SELECT schemaname AS schema, count(*) AS tables FROM pg_tables
                       WHERE schemaname NOT IN ('pg_catalog', 'information_schema', 'public', 'import')
                       GROUP BY 1 ORDER BY 1""")
    c["vues"] = q("""SELECT table_schema AS schema, count(*) AS vues FROM information_schema.views
                     WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'public')
                     GROUP BY 1""")
    c["arbres"] = q("""SELECT count(*) FILTER (WHERE statut = 'en_place') AS en_place,
                              count(*) FILTER (WHERE statut = 'abattu') AS abattus,
                              count(*) FILTER (WHERE remarquable) AS remarquables,
                              count(DISTINCT essence) AS essences,
                              count(*) FILTER (WHERE etat_sanitaire IN ('deperissant', 'mort')
                                               AND statut = 'en_place') AS degrades
                       FROM espaces_verts.arbre""").iloc[0]
    c["prio"] = q("SELECT priorite, count(*) AS n FROM espaces_verts.v_arbre_prioritaire GROUP BY 1 ORDER BY 1")
    c["inter"] = q("SELECT count(*) AS n, sum(cout_ht) AS cout FROM espaces_verts.intervention").iloc[0]
    c["journal"] = int(q("SELECT count(*) AS n FROM espaces_verts.journal").iloc[0]["n"])
    c["taille"] = q("SELECT pg_size_pretty(pg_database_size(current_database())) AS t").iloc[0]["t"]
    c["chev"] = q("SELECT * FROM controle.v_zonage_chevauchement")
    c["diffusions"] = q("SELECT * FROM metadonnees.journal_diffusion ORDER BY id")
    return c


# =============================================================================
# Note d'architecture
# =============================================================================
def note_architecture(c):
    ind = c["ind"]
    pop = int(ind["population"].sum())
    adr = int(ind["nb_adresses"].sum())
    cert = (ind["nb_adresses"] * ind["adresses_certifiees_pct"]).sum() / adr
    sans_doc = ", ".join(ind.loc[ind["document_urbanisme"] == "Non publié", "nom"])
    qc = dict(zip(c["qc"]["controle"], c["qc"]["anomalies"]))
    a = c["arbres"]
    prio = dict(zip(c["prio"]["priorite"], c["prio"]["n"]))
    nb_tables = int(c["tables"]["tables"].sum())
    nb_vues = int(c["vues"]["vues"].sum())

    H = [P("Sommaire", "h1")]
    H += puces(["1. Contexte et objectifs", "2. Architecture d'ensemble", "3. Correspondance avec l'environnement ESRI",
                "4. La base PostgreSQL/PostGIS", "5. Intégration des référentiels et contrôle qualité",
                "6. Données métier : le patrimoine arboré, du bureau au terrain",
                "7. Consultation : projets QGIS et carte web", "8. Cartographie",
                "9. Métadonnées et diffusion", "10. Exploitation et mise à jour", "11. Limites"])
    H += [Spacer(1, 12), P("En bref", "h2"), tableau([
        ["Indicateur", "Valeur"],
        ["Territoire", f"{config.EPCI_NOM} : 12 communes, {nb(pop)} habitants"],
        ["Base PostGIS", f"{len(c['tables'])} schémas, {nb_tables} tables, {nb_vues} vues, {c['taille']}"],
        ["Jeux de données catalogués", f"{len(c['fiches'])} fiches ISO 19139 (profil INSPIRE)"],
        ["Parcelles · adresses · bâtiments", f"{nb(ind['nb_parcelles'].sum())} · {nb(adr)} · {nb(ind['nb_batiments'].sum())}"],
        ["Arbres inventoriés", f"{nb(a['en_place'])} en place, {a['essences']} essences, {a['remarquables']} remarquables"],
        ["Anomalies relevées par les contrôles", f"{nb(sum(qc.values()))} sur 8 contrôles automatiques"],
        ["Coût de licence", "0 € : QGIS, PostgreSQL/PostGIS, QField, Python, Leaflet"],
    ], [5.5 * cm, 11.5 * cm])]

    H += [PageBreak(), P("1. Contexte et objectifs", "h1")]
    H += [P("La Ville de Sélestat et la communauté de communes partagent un service des systèmes "
            "d'information, qui pilote la mise en place d'un système d'information géographique commun "
            "aux 12 communes : acquisition des données, administration, traitement, analyse et diffusion. "
            "Ce projet construit ce socle de bout en bout avec des logiciels libres, à partir des seules "
            "données ouvertes, et montre comment chaque mission du poste s'y traduit."),
          tableau([
              ["Mission", "Réponse dans le projet"],
              ["Assurer le fonctionnement et le développement du SIG", "Base PostGIS structurée par schémas, rôles et droits ; chaîne de traitement rejouable"],
              ["Numériser et intégrer les données", "Flux WFS de l'IGN, du GPU et de l'INPN ; modèle métier saisi au bureau et sur le terrain"],
              ["Paramétrer le logiciel de consultation", "Projets QGIS par thèmes, formulaires de saisie, carte web avec fiche parcelle"],
              ["Utiliser plusieurs logiciels", "QGIS, PostgreSQL/PostGIS, pgAdmin, QField, Python (GeoPandas, PyQGIS), GDAL"],
              ["Cartographier et valoriser l'information", "6 planches A3, atlas communal, carte web publique"],
              ["Respecter et faire respecter la diffusion", "Charte de diffusion, niveaux par jeu, outil d'extraction, registre des diffusions"],
              ["Conseiller et accompagner les utilisateurs", "Trois fiches tutoriel (QGIS, QField, carte web)"],
          ], [6 * cm, 11 * cm]),
          Spacer(1, 8),
          encadre("<b>Pourquoi le libre ?</b> Les compétences ESRI demandées (ArcGIS Pro, Experience Builder, "
                  "Field Maps) se transposent directement : les concepts sont les mêmes (base géographique "
                  "d'entreprise, formulaires, applications web, collecte mobile). Le socle reste "
                  "interopérable avec ArcGIS : ArcGIS Pro lit et écrit PostGIS, ouvre les GeoPackage, et "
                  "une géodatabase fichier (.gdb) est produite par GDAL pour les partenaires équipés.")]

    H += [PageBreak(), P("2. Architecture d'ensemble", "h1"),
          figure(IMG / "architecture.png", "Figure 1 - Architecture du socle SIG : sources ouvertes, base "
                 "PostGIS centrale, outils de consultation, de saisie et de diffusion."),
          P("La base PostgreSQL/PostGIS est le point unique de vérité. Les référentiels y arrivent par "
            "une chaîne Python qui interroge les services officiels ; les données métier y sont saisies "
            "depuis QGIS au bureau ou QField sur le terrain ; tous les outils de consultation et de "
            "diffusion lisent la même base. Les règles de gestion (numérotation, rattachement communal, "
            "cohérences, traçabilité) sont portées par la base elle-même : elles s'appliquent quel que "
            "soit l'outil utilisé pour saisir.")]

    H += [P("3. Correspondance avec l'environnement ESRI", "h1"), tableau([
        ["Usage", "Environnement ESRI (fiche de poste)", "Équivalent libre utilisé"],
        ["SIG bureautique", "ArcGIS Pro", "QGIS 3.34 LTR"],
        ["Base d'entreprise", "Géodatabase d'entreprise (SDE)", "PostgreSQL 15 / PostGIS 3.5, pgAdmin"],
        ["Domaines, sous-types", "Domaines de géodatabase", "Tables de listes de valeurs + widgets « Relation de valeur »"],
        ["Règles attributaires", "Attribute rules (Arcade)", "Déclencheurs PL/pgSQL + contraintes de formulaire QGIS"],
        ["Suivi des modifications", "Editor tracking, archivage", "Colonnes auteur/date + table journal (avant/après en JSON)"],
        ["Collecte terrain", "Field Maps", "QField (+ QFieldSync ou QFieldCloud)"],
        ["Application web", "Experience Builder, Web AppBuilder", "Carte web Leaflet (démo) ; Lizmap / QGIS Server en production"],
        ["Modules métier", "Arcopole Builder (cadastre, urbanisme)", "Fiche parcelle PostGIS, extension Cadastre de QGIS (3liz)"],
        ["Mises en page", "Layouts, map series", "Mises en page et atlas QGIS"],
        ["Automatisation", "ModelBuilder, ArcPy", "Python (GeoPandas, PyQGIS), modeleur graphique QGIS"],
        ["Catalogue", "ArcGIS Hub / Portal", "Fiches ISO 19139 moissonnables (GeoNetwork, DataGrandEst)"],
        ["Échange", "Géodatabase fichier", "GeoPackage ; .gdb écrite par GDAL (OpenFileGDB)"],
    ], [3.2 * cm, 5.6 * cm, 8.2 * cm])]

    H += [PageBreak(), P("4. La base PostgreSQL/PostGIS", "h1"),
          P("Un schéma par famille de données rend la base lisible et permet de donner des droits par "
            "bloc. Les droits par défaut (<i>ALTER DEFAULT PRIVILEGES</i>) s'appliquent aussi aux tables "
            "créées plus tard : un nouveau référentiel est immédiatement visible des lecteurs."),
          tableau([["Schéma", "Contenu", "Tables"]] + [
              [r.schema, {
                  "ref_admin": "Communes, EPCI, indicateurs communaux", "ref_cadastre": "Parcelles (PCI)",
                  "ref_adresse": "Adresses BAN", "ref_topo": "Bâti, voirie, hydrographie, équipements",
                  "urbanisme": "Documents, zonage, prescriptions, informations (CNIG)",
                  "servitudes": "Servitudes d'utilité publique et nomenclature",
                  "environnement": "Natura 2000, ZNIEFF, réserve, biotopes",
                  "espaces_verts": "Arbres, interventions, listes de valeurs, journal",
                  "metadonnees": "Catalogue, journal des intégrations et des diffusions",
              }.get(r.schema, ""), str(r.tables)] for r in c["tables"].itertuples()],
              [3.3 * cm, 11.2 * cm, 2.5 * cm]),
          Spacer(1, 6), P("Rôles et droits", "h2"),
          tableau([["Rôle", "Droits", "Exemple de compte"],
                   ["sig_admin", "Propriétaire des schémas, intégration des référentiels", "technicien SIG"],
                   ["sig_editeur", "Lecture de tout + saisie dans espaces_verts (sauf listes et journal)", "u_espaces_verts"],
                   ["sig_lecteur", "Lecture de toutes les données internes", "u_urbanisme (instructeur ADS)"],
                   ["sig_public", "Lecture du seul schéma diffusion", "u_web (carte publique)"]],
                  [3 * cm, 9.5 * cm, 4.5 * cm]),
          P("Aucun mot de passe n'est écrit dans les scripts ni dans les projets : les projets QGIS se "
            "connectent par un <b>service</b> (pg_service.conf) et chaque agent enregistre ses "
            "identifiants dans la base d'authentification chiffrée de QGIS.", "corps"),
          P("Fiche parcelle en une requête", "h2"),
          P("La fonction <i>urbanisme.fiche_parcelle(idu)</i> rassemble ce qu'un instructeur ADS ou un "
            "agent d'accueil cherche : zonage avec la part de la parcelle et le lien vers le règlement, "
            "prescriptions, informations, servitudes, zonages naturels, adresses et arbres inventoriés. "
            "Elle renvoie un document JSON exploitable par QGIS, un service web ou un publipostage."),
          code("SELECT urbanisme.fiche_parcelle('67462000030174');\n"
               "-- {\"commune\": \"Sélestat\", \"section\": \"03\", \"numero\": \"0174\",\n"
               "--  \"zonage\": [{\"zone\": \"UA\", \"libelle\": \"centre ancien\", \"part_pct\": 100.0,\n"
               "--    \"reglement\": \"https://data.geopf.fr/annexes/gpu/.../67462_reglement_20260716.pdf\"}],\n"
               "--  \"servitudes\": [{\"categorie\": \"AC1\", \"objet\": \"PDA Centre\"},\n"
               "--    {\"categorie\": \"AC2\", \"objet\": \"Ensemble urbain formé par les quartiers anciens\"}],\n"
               "--  \"informations\": [{\"type\": \"Droit de préemption urbain\", ...}], \"arbres_inventories\": 3}")]

    H += [PageBreak(), P("5. Intégration des référentiels et contrôle qualité", "h1"),
          P("Les référentiels sont lus directement sur les flux officiels (WFS de la Géoplateforme, API "
            "du Géoportail de l'Urbanisme), filtrés sur les 12 communes, normalisés puis chargés. "
            "Chaque chargement est tracé dans <i>metadonnees.journal_integration</i>. Deux défauts des "
            "sources ont été corrigés à l'intégration : des libellés de servitudes encodés deux fois "
            "en UTF-8 (« ChÃ¢teau » pour « Château »), et l'absence de lien vers les règlements écrits, "
            "reconstitué à partir des identifiants du GPU."),
          tableau([["Contrôle (vue du schéma controle)", "Anomalies"]] +
                  [[r.controle, nb(r.anomalies)] for r in c["qc"].itertuples()], [13 * cm, 4 * cm]),
          Spacer(1, 6), P("Ce que les contrôles révèlent", "h2")]
    chev = c["chev"]
    H += puces([
        f"<b>Documents d'urbanisme</b> : {sans_doc} n'ont pas de document publié sur le Géoportail de "
        "l'Urbanisme, alors que la publication conditionne leur caractère exécutoire depuis 2020.",
        f"<b>Zonage</b> : {len(chev)} chevauchements entre zones d'un même PLU" +
        (f", dont {nb(chev['surface_m2'].max())} m² à {('Ebersheim' if '67115' in set(chev['code_insee']) else chev['code_insee'].iloc[0])}" if len(chev) else "") +
        f" ; {qc.get('Parcelles hors zonage', 0)} parcelles couvertes à moins de 50 % par le zonage.",
        f"<b>Adressage</b> : {nb(cert)} % des adresses sont certifiées par leur commune, de 0 % à "
        f"Dieffenthal et Ebersmunster à 100 % à Kintzheim ou Muttersholtz ; "
        f"{qc.get('Logements sans adresse proche', 0)} bâtiments d'habitation n'ont aucune adresse à "
        "moins de 30 m. Ces listes servent à accompagner les communes dans leur Base Adresse Locale.",
        f"<b>Patrimoine arboré</b> : {qc.get('Arbres en doublon', 0)} doublon de saisie et "
        f"{qc.get('Fiches arbre incomplètes', 0)} fiches incomplètes (essence à déterminer), à reprendre "
        "lors de la prochaine tournée.",
    ])
    H += [P("Les vues de contrôle renvoient une ligne par anomalie, avec sa géométrie : elles s'ouvrent "
            "dans le groupe « Contrôle qualité » du projet QGIS pour corriger sur place, et le classeur "
            "<i>controle_qualite_et_indicateurs.xlsx</i> les liste avec l'action corrective attendue.")]

    H += [PageBreak(), P("6. Données métier : le patrimoine arboré, du bureau au terrain", "h1"),
          P(f"L'inventaire compte {nb(a['en_place'])} arbres en place ({a['essences']} essences). Les "
            "positions viennent d'OpenStreetMap ; les attributs (dimensions, état sanitaire, "
            "interventions) sont simulés de façon reproductible pour la démonstration, avec des règles "
            "réalistes : chalarose sur les frênes, mineuse sur les marronniers, risque plus élevé pour "
            "les arbres d'alignement."),
          P("Modèle de données", "h2"),
          tableau([["Table", "Rôle", "Points clés"],
                   ["arbre", "Un point par arbre", "UUID (pas de conflit hors connexion), numéro ARB-insee-n attribué par la base"],
                   ["intervention", "Historique des opérations", "Met à jour l'arbre : état constaté, abattage, plantation"],
                   ["liste_*", "Listes de valeurs", "Essences (allergisant, envahissante), états, stades, types d'intervention"],
                   ["journal", "Audit", f"{nb(c['journal'])} opérations tracées avec l'état avant/après"],
                   ["v_arbre_prioritaire", "Priorités", f"{prio.get(1, 0)} arbres en priorité 1, {prio.get(2, 0)} en priorité 2, {prio.get(3, 0)} en surveillance"]],
                  [3.6 * cm, 4 * cm, 9.4 * cm]),
          Spacer(1, 6), P("Règles portées par la base", "h2")]
    H += puces(["La commune est déduite de la position ; un point hors du territoire est refusé avec un message clair.",
                "Le numéro lisible est attribué à la création ; l'année de plantation ne peut pas être future.",
                "Un arbre mort passe automatiquement en risque élevé ; un abattage le retire de l'inventaire en place.",
                "Toute modification est datée, signée et journalisée (qui, quand, avant, après)."])
    H += [P("Saisie terrain avec QField", "h2"),
          P("Le projet <i>inventaire_arbres.qgz</i> reprend les mêmes formulaires (onglets Identification, "
            "Dimensions, État sanitaire, Interventions, Traçabilité), avec des listes déroulantes, des "
            "contrôles de saisie (hauteur, circonférence, photo recommandée pour un arbre dépérissant) et "
            "des valeurs automatiques : identifiant, commune calculée hors connexion par expression, "
            "précision GNSS, auteur. À la synchronisation, la base applique ses propres règles.")]
    if (IMG / "qgis_patrimoine_arbore.png").exists():
        H += [figure(IMG / "qgis_patrimoine_arbore.png", "Figure 2 - Thème « Patrimoine arboré » du projet "
                     "QGIS : état sanitaire (couleur), circonférence (taille), priorités (anneaux).", max_hauteur=10 * cm)]

    H += [PageBreak(), P("7. Consultation : projets QGIS et carte web", "h1"),
          P("Le projet QGIS existe en deux versions identiques : connectée à PostGIS par service pour "
            "l'usage quotidien, et sur GeoPackage pour un poste sans accès au serveur. Il organise les "
            "couches par groupes, propose 12 thèmes de carte (Urbanisme, Servitudes et risques, "
            "Patrimoine arboré, Adressage, Contrôle qualité...) et porte les métadonnées de chaque couche."),
          P("La carte web reprend les usages d'une application Experience Builder ou Lizmap : couches "
            "commentées, recherche d'adresse (géocodage IGN) ou de référence cadastrale, fiche de "
            "renseignements imprimable, indicateurs communaux et catalogue des données.")]
    if (IMG / "web_fiche_parcelle.png").exists():
        H += [figure(IMG / "web_fiche_parcelle.png", "Figure 3 - Carte web : fiche de renseignements d'une "
                     "parcelle du centre ancien de Sélestat (zone UA, abords de monuments historiques, site inscrit).", max_hauteur=10.5 * cm)]

    H += [PageBreak(), P("8. Cartographie", "h1"),
          P("Six planches A3 et un atlas communal sont générés par le projet QGIS (mises en page et "
            "atlas), donc régénérés à chaque mise à jour. Les choix de sémiologie suivent les conventions "
            "de l'urbanisme : couleurs du standard CNIG pour le zonage, hachures pour les servitudes "
            "(qui se superposent au zonage), valeurs relatives en aplats gradués, fond de plan IGN en "
            "gris pour laisser la couleur aux données, voile blanc hors du territoire.")]
    H += puces(["P01 Le territoire intercommunal", "P02 Documents d'urbanisme et zonage",
                "P03 Servitudes d'utilité publique et risques", "P04 Patrimoine naturel",
                "P05 Patrimoine arboré de Sélestat", "P06 Qualité de l'adressage",
                "Atlas communal A4 : une fiche d'identité SIG par commune"])
    if (CARTES / "P06_Adressage.png").exists():
        H += [figure(CARTES / "P06_Adressage.png", "Figure 4 - Planche P06 : certification des adresses "
                     "par commune et logements sans adresse proche.")]

    H += [PageBreak(), P("9. Métadonnées et diffusion", "h1"),
          P("Chaque jeu de données a une fiche dans <i>metadonnees.fiche</i> : titre, résumé, thème "
            "INSPIRE, producteur, licence, millésime, fréquence de mise à jour et niveau de diffusion. "
            "Les fiches XML ISO 19139 en sont tirées automatiquement et peuvent être moissonnées par un "
            "catalogue GeoNetwork (plateforme régionale DataGrandEst, catalogue local). Les mêmes "
            "informations alimentent les métadonnées des couches QGIS et le catalogue de la carte web."),
          tableau([["Niveau", "Jeux", "Exemples"]] + [
              [niv, str(len(g)), ", ".join(g["titre"].head(3))]
              for niv, g in c["fiches"].groupby("niveau_diffusion")], [3 * cm, 2 * cm, 12 * cm]),
          Spacer(1, 6),
          P("La charte de diffusion fixe les règles ; l'outil <i>scripts/extraction.py</i> les applique "
            "au moment de l'extraction : il livre les jeux ouverts, remplace un jeu interne par sa "
            "version publique quand elle existe, refuse le reste en indiquant le motif, joint les fiches "
            "de métadonnées et un bordereau de diffusion, et inscrit la remise au registre."),
          code("python scripts/extraction.py --demandeur \"Bureau d'études (exemple)\" \\\n"
               "  --objet \"Étude de requalification de la traversée de Châtenois\" --communes 67073 \\\n"
               "  --jeux zone_urba prescription_surf sup_assiette_s zonage_naturel arbre intervention\n"
               "# interventions : refusé (jeu interne) ; arbres : version publique livrée")]

    H += [P("10. Exploitation et mise à jour", "h1"), tableau([
        ["Référentiel", "Fréquence de mise à jour", "Action"],
        ["Base Adresse Nationale", "Hebdomadaire", "Relancer l'étape 0 puis 1 (ou planifier run_all.py)"],
        ["Cadastre (PCI)", "Semestrielle", "Idem ; contrôler les parcelles hors zonage"],
        ["BD TOPO", "Trimestrielle", "Idem"],
        ["PLU, servitudes (GPU)", "À chaque procédure", "Idem ; vérifier la date d'approbation dans doc_urba"],
        ["Zonages naturels (INPN)", "Annuelle", "Idem"],
        ["Patrimoine arboré", "Continue", "Saisie QGIS / QField ; aucun rechargement"],
    ], [4.5 * cm, 4 * cm, 8.5 * cm])]
    H += puces([
        "<b>Sauvegarde</b> : pg_dump quotidien au format personnalisé (restauration table par table avec pg_restore).",
        "<b>Passage en production</b> : serveur PostgreSQL de la collectivité, comptes nominatifs, "
        "Lizmap sur QGIS Server pour la carte interne avec authentification, QFieldCloud ou dossier "
        "partagé pour la synchronisation des tablettes.",
        "<b>Données personnelles</b> : l'intégration des fichiers MAJIC (propriétaires) suivrait le même "
        "modèle dans un schéma dédié, au niveau « restreinte », accessible aux seuls agents habilités.",
    ])
    H += [P("11. Limites", "h1")]
    H += puces([
        "Projet de démonstration réalisé à partir de données ouvertes : il n'engage ni la Ville ni la "
        "communauté de communes. Les attributs du patrimoine arboré sont simulés.",
        "Le zonage, les prescriptions et les servitudes sont ceux publiés au GPU à la date d'acquisition ; "
        "seuls les documents approuvés font foi.",
        "La carte web statique interroge le cadastre en direct (API Carto de l'IGN) : elle dépend de la "
        "disponibilité de ce service.",
    ])
    pdf.construire(DOCS_PDF / "01_Note_d_architecture.pdf", "Note d'architecture",
                   pdf.couverture("Socle SIG intercommunal open source", "Note d'architecture",
                                  "QGIS · PostgreSQL/PostGIS · QField · carte web",
                                  [("Territoire", f"{config.EPCI_NOM} (12 communes)"),
                                   ("Version", f"{pdf.VERSION} · {pdf.AUJOURDHUI}"),
                                   ("Auteur", config.AUTEUR)]), H)


# =============================================================================
# Charte de diffusion
# =============================================================================
def charte(c):
    f = c["fiches"]
    H = [P("1. Objet", "h1"),
         P("La présente charte fixe les règles de mise à disposition des données géographiques gérées "
           "par le service SIG mutualisé, à l'intérieur de la collectivité comme vers l'extérieur "
           "(administrés, bureaux d'études, partenaires publics, plateformes open data). Elle s'applique "
           "à toute extraction, quel que soit le format (fichier, carte, impression, flux)."),
         P("2. Principes", "h1")]
    H += puces([
        "<b>Ouverture par défaut</b> : les collectivités de plus de 3 500 habitants publient leurs données "
        "de référence (loi pour une République numérique, 2016), sous une licence homologuée.",
        "<b>Protection des personnes</b> : aucune donnée à caractère personnel n'est diffusée hors des cas "
        "prévus par la loi (RGPD, code des relations entre le public et l'administration).",
        "<b>Traçabilité</b> : toute remise à un tiers donne lieu à un bordereau et à une inscription au "
        "registre des diffusions.",
        "<b>Qualité</b> : chaque jeu remis est accompagné de sa fiche de métadonnées (date, source, licence, limites).",
    ])
    H += [P("3. Trois niveaux de diffusion", "h1"), tableau([
        ["Niveau", "Qui peut recevoir", "Conditions", "Exemples"],
        ["Ouverte", "Tout demandeur", "Licence du jeu (Licence Ouverte 2.0 ou ODbL), mention de la source",
         "Zonage des PLU, servitudes, adresses, inventaire arboré public"],
        ["Interne", "Services de la Ville et de la communauté de communes", "Usage de service ; vers un tiers, "
         "seule la version publique est remise", "Observations des agents, coûts d'intervention"],
        ["Restreinte", "Agents habilités, partenaires sous convention", "Convention ou acte d'engagement, "
         "finalité déclarée, durée de conservation", "Fichiers fonciers MAJIC (propriétaires)"],
    ], [2.2 * cm, 4 * cm, 5.6 * cm, 5.2 * cm]),
        P("4. Licences et mentions", "h1")]
    H += puces([
        "<b>Licence Ouverte 2.0 (Etalab)</b> : réutilisation libre, y compris commerciale, en mentionnant "
        "la source et la date de mise à jour. S'applique aux référentiels IGN, BAN, GPU, INPN.",
        "<b>Open Database License (ODbL)</b> : les données dérivées d'OpenStreetMap (positions des arbres) "
        "restent sous ODbL ; toute base dérivée diffusée doit l'être sous la même licence, avec la mention "
        "« © contributeurs OpenStreetMap ».",
        "Mention à reporter sur toute carte ou document : « Sources : [producteurs] ; traitement SIG "
        f"{config.EPCI_COURT}, [année] ».",
    ])
    H += [P("5. Données à caractère personnel", "h1"),
          P("Les fichiers fonciers (MAJIC) contiennent l'identité et l'adresse des propriétaires. Ils ne "
            "sont accessibles qu'aux agents habilités, pour des missions de service public identifiées "
            "(instruction, fiscalité, gestion foncière), après signature de l'acte d'engagement auprès de "
            "la DGFiP. Ils ne sont jamais remis à un tiers ; un administré peut obtenir un relevé de "
            "propriété le concernant auprès des services fiscaux. Les noms des agents et les "
            "observations libres saisies sur le terrain sont des informations internes : la vue "
            "publique de l'inventaire arboré les exclut."),
          P("6. Traitement d'une demande", "h1")]
    H += etapes([
        "<b>Réception</b> de la demande écrite : identité du demandeur, objet, périmètre, données souhaitées.",
        "<b>Qualification</b> : niveau de diffusion de chaque jeu (catalogue), finalité, éventuelle convention.",
        "<b>Extraction</b> avec l'outil dédié (scripts/extraction.py), qui applique automatiquement les "
        "niveaux, joint les métadonnées et produit le bordereau.",
        "<b>Validation</b> : visa du service SIG sur le bordereau, envoi de l'archive.",
        "<b>Registre</b> : la remise est inscrite dans metadonnees.journal_diffusion (date, demandeur, "
        "jeux, périmètre, convention).",
        "<b>Délai</b> : réponse sous un mois (code des relations entre le public et l'administration).",
    ])
    H += [P("7. Responsabilités", "h1")]
    H += puces(["<b>Service SIG</b> : tient le catalogue, qualifie les demandes, réalise les extractions, tient le registre.",
                "<b>Services producteurs</b> (urbanisme, espaces verts...) : valident le niveau de diffusion de leurs données.",
                "<b>Délégué à la protection des données</b> : est consulté pour toute demande touchant des données personnelles."])
    H += [PageBreak(), P("Annexe : niveau de diffusion des jeux du catalogue", "h1"),
          tableau([["Jeu de données", "Table", "Licence", "Niveau"]] +
                  [[r.titre, r.table_nom, r.licence, r.niveau_diffusion] for r in f.itertuples()],
                  [6 * cm, 4.8 * cm, 4.2 * cm, 2 * cm])]
    pdf.construire(DOCS_PDF / "02_Charte_de_diffusion.pdf", "Charte de diffusion des données",
                   pdf.couverture("Socle SIG intercommunal open source", "Charte de diffusion\ndes données",
                                  "Règles, niveaux, licences et procédure",
                                  [("Territoire", f"{config.EPCI_NOM}"),
                                   ("Version", f"{pdf.VERSION} · {pdf.AUJOURDHUI}"),
                                   ("Rédaction", config.AUTEUR)]), H)


# =============================================================================
# Fiches tutoriel
# =============================================================================
def fiches_tutoriel():
    H = [P("Fiche 1 · Consulter le SIG dans QGIS", "h1"),
         encadre("<b>Pour qui ?</b> Tout agent qui consulte le SIG (urbanisme, services techniques, accueil). "
                 "<b>Durée</b> : 10 minutes."),
         Spacer(1, 6), P("Première ouverture", "h2")]
    H += etapes(["Installer QGIS 3.34 LTR (version stable, mise à jour une fois par an).",
                 "Copier le fichier <i>pg_service.conf</i> fourni par le service SIG dans "
                 "<i>%APPDATA%\\postgresql\\.pg_service.conf</i>.",
                 "Ouvrir <i>sig_ccst_postgis.qgz</i>. À la première connexion, saisir ses identifiants et "
                 "cocher « Enregistrer » : ils sont stockés dans la base d'authentification chiffrée de QGIS.",
                 "Sans accès au serveur, ouvrir <i>sig_ccst.qgz</i> (même projet sur GeoPackage)."])
    H += [P("Les gestes courants", "h2")]
    H += puces([
        "<b>Changer de thème</b> : bouton « Gérer les thèmes de carte » (œil) du panneau Couches, puis "
        "Urbanisme, Servitudes et risques, Patrimoine arboré, Adressage...",
        "<b>Interroger un objet</b> : outil Identifier (Ctrl+Maj+I), puis clic sur la carte. Le formulaire "
        "d'un arbre montre aussi ses interventions.",
        "<b>Lire la fiche d'une parcelle</b> : Base de données › Gestionnaire BD › SQL : "
        "<i>SELECT urbanisme.fiche_parcelle('67462000030174');</i> ou, plus simplement, la carte web.",
        "<b>Rechercher une adresse</b> : <i>SELECT * FROM ref_adresse.rechercher('9 place d armes selestat');</i> "
        "(tolère accents et fautes de frappe).",
        "<b>Imprimer</b> : Projet › Mises en page : planches A3 prêtes, ou atlas communal (une page par commune).",
        "<b>Lire les métadonnées</b> : Propriétés de la couche › Métadonnées (source, licence, millésime, niveau de diffusion).",
    ])
    H += [encadre("<b>Bon réflexe</b> : avant de transmettre une donnée à l'extérieur, vérifier son niveau de "
                  "diffusion dans les métadonnées et passer par le service SIG (charte de diffusion).", pdf.ALERTE_PALE)]
    if (IMG / "qgis_urbanisme.png").exists():
        H += [Spacer(1, 8), figure(IMG / "qgis_urbanisme.png", "Thème « Urbanisme détaillé » : zonage, prescriptions, "
                                   "parcelles et adresses (certifiées en violet, non certifiées en orange).", max_hauteur=8.5 * cm)]

    H += [PageBreak(), P("Fiche 2 · Inventorier un arbre avec QField", "h1"),
          encadre("<b>Pour qui ?</b> Agents des espaces verts équipés d'une tablette ou d'un smartphone "
                  "(Android ou iOS). <b>Durée</b> : 2 minutes par arbre."),
          Spacer(1, 6), P("Préparer la tournée (au bureau)", "h2")]
    H += etapes(["Installer l'application QField (gratuite).",
                 "Copier le dossier <i>qfield/</i> (projet inventaire_arbres.qgz et son GeoPackage) sur "
                 "l'appareil, ou le synchroniser par QFieldCloud.",
                 "Ouvrir le projet : photo aérienne IGN en fond, arbres colorés selon leur état."])
    H += [P("Créer un arbre", "h2")]
    H += etapes(["Se placer au pied de l'arbre ; attendre une précision GNSS de quelques mètres.",
                 "Passer en mode saisie (crayon), choisir la couche Arbres, ajouter le point à la position GNSS.",
                 "Remplir les onglets : <b>Identification</b> (essence avec recherche par nom), "
                 "<b>Dimensions</b> (circonférence à 1,30 m), <b>État sanitaire</b> (état, risque, observations, photo).",
                 "Valider. Le numéro, la commune, la date, l'auteur et la précision sont remplis automatiquement."])
    H += [P("Enregistrer une intervention", "h2")]
    H += etapes(["Toucher l'arbre, ouvrir sa fiche, onglet <b>Interventions</b>, bouton « + ».",
                 "Choisir le type (diagnostic, taille, élagage, abattage...), la date et l'état constaté.",
                 "Un diagnostic met à jour l'état de l'arbre ; un abattage le retire de l'inventaire en place."])
    H += [P("Contrôles à la saisie", "h2")]
    H += puces(["Hauteur entre 0,5 et 50 m, circonférence entre 5 et 1 500 cm, année de plantation passée.",
                "Photo demandée (avertissement) pour un arbre dépérissant ou mort.",
                "Un arbre hors du territoire est refusé à la synchronisation."])
    H += [P("Synchroniser (retour au bureau)", "h2"),
          P("Avec QFieldCloud : bouton « Synchroniser ». Sans : récupérer le dossier et utiliser "
            "l'extension QFieldSync de QGIS (« Synchroniser depuis QField »). La base applique alors ses "
            "règles (numéro définitif, journal) et les arbres apparaissent dans tous les outils.")]
    if (IMG / "qgis_formulaire_arbre.png").exists():
        H += [figure(IMG / "qgis_formulaire_arbre.png", "Le formulaire de saisie, identique dans QGIS et QField : "
                     "onglet État sanitaire.", largeur=11 * cm)]
    if (IMG / "qgis_formulaire_interventions.png").exists():
        H += [figure(IMG / "qgis_formulaire_interventions.png", "Onglet Interventions : l'historique de l'arbre, "
                     "avec le formulaire de chaque intervention.", largeur=11 * cm)]

    H += [PageBreak(), P("Fiche 3 · Utiliser la carte web", "h1"),
          encadre("<b>Pour qui ?</b> Agents d'accueil, élus, partenaires. Aucune installation : un navigateur suffit."),
          Spacer(1, 6)]
    H += etapes([
        "<b>Rechercher</b> : taper une adresse dans la barre du haut, ou une référence cadastrale sous la "
        "forme <i>67462 03 174</i> (code INSEE, section, numéro), puis Entrée.",
        "<b>Lire la fiche parcelle</b> : zonage avec la part de la parcelle et le lien vers le règlement, "
        "prescriptions, informations (droit de préemption, bruit...), servitudes, zonages naturels, arbres.",
        "<b>Imprimer</b> la fiche : bouton « Imprimer la fiche ». Rappeler qu'elle n'a pas de valeur "
        "juridique : seul un certificat d'urbanisme fait foi.",
        "<b>Comparer les communes</b> : onglet Communes, choisir un indicateur (adresses certifiées, PPRI, "
        "Natura 2000...) ; cliquer une ligne du tableau centre la carte.",
        "<b>Trouver une donnée</b> : onglet Données, catalogue filtrable par niveau de diffusion, avec la "
        "fiche de métadonnées de chaque jeu.",
    ])
    if (IMG / "web_vue_generale.png").exists():
        H += [Spacer(1, 6), figure(IMG / "web_vue_generale.png", "La carte web : couches et légende à gauche, "
                                   "carte à droite.", max_hauteur=9 * cm)]
    pdf.construire(DOCS_PDF / "03_Fiches_tutoriel.pdf", "Fiches tutoriel",
                   pdf.couverture("Socle SIG intercommunal open source", "Fiches tutoriel",
                                  "QGIS · QField · carte web",
                                  [("Public", "agents de la Ville et de la communauté de communes"),
                                   ("Version", f"{pdf.VERSION} · {pdf.AUJOURDHUI}"),
                                   ("Rédaction", config.AUTEUR)]), H)


# =============================================================================
# Bordereau de livraison
# =============================================================================
def taille(chemin):
    if chemin.is_dir():
        octets = sum(f.stat().st_size for f in chemin.rglob("*") if f.is_file())
    else:
        octets = chemin.stat().st_size if chemin.exists() else 0
    return f"{octets / 1e6:,.1f} Mo".replace(",", " ").replace(".", ",") if octets > 1e5 else \
        f"{octets / 1e3:,.0f} Ko".replace(",", " ")


def bordereau_livraison():
    L = config.LIVRABLES
    lignes = [["Livrable", "Contenu", "Taille"]]
    for chemin, contenu in [
        ("01_Documents/01_Note_d_architecture.pdf", "Architecture, base, contrôles, correspondance ESRI, exploitation"),
        ("01_Documents/02_Charte_de_diffusion.pdf", "Niveaux de diffusion, licences, données personnelles, procédure"),
        ("01_Documents/03_Fiches_tutoriel.pdf", "QGIS, QField, carte web"),
        ("02_Base_PostGIS/sig_ccst.backup", "Sauvegarde complète (pg_restore)"),
        ("02_Base_PostGIS/sig_ccst_structure.sql", "Structure seule : schémas, tables, fonctions, vues"),
        ("03_Projets_QGIS/sig_ccst.qgz", "Projet de consultation (GeoPackage), 12 thèmes, 7 mises en page"),
        ("03_Projets_QGIS/sig_ccst.gpkg", "Données du projet portable"),
        ("03_Projets_QGIS/qfield", "Projet de saisie terrain QField et son GeoPackage"),
        ("04_Echanges/sig_ccst.gdb", "Géodatabase fichier pour ArcGIS (écrite par GDAL)"),
        ("04_Echanges/open_data", "Inventaire arboré public (GeoJSON, ODbL), indicateurs (CSV)"),
        ("05_Metadonnees", "Fiches ISO 19139, catalogue et dictionnaire des données (CSV)"),
        ("06_Cartes", "6 planches A3 (PDF et aperçus PNG)"),
        ("07_Atlas_communal/Atlas_communal.pdf", "Atlas A4, une page par commune"),
        ("08_Tableaux/controle_qualite_et_indicateurs.xlsx", "Contrôles qualité détaillés, indicateurs communaux"),
        ("09_Diffusion", "Exemple d'extraction pour un tiers, avec bordereau de diffusion"),
    ]:
        lignes.append([chemin, contenu, taille(L / chemin)])
    lignes.append(["../qgis/sig_ccst_postgis.qgz", "Projet de production connecté à PostGIS (service sig_ccst)",
                   taille(config.QGIS_DIR / "sig_ccst_postgis.qgz")])
    lignes.append(["../docs", "Carte web (GitHub Pages)", taille(config.DOCS)])
    H = [P("Bordereau de livraison", "h1"),
         P(f"Socle SIG intercommunal open source · {config.EPCI_NOM} · version {pdf.VERSION} · {pdf.AUJOURDHUI}"),
         tableau(lignes, [6.3 * cm, 8.4 * cm, 2.3 * cm]), Spacer(1, 10),
         P("Reconstruire l'ensemble", "h2"),
         code("pip install -r requirements.txt\npython scripts/run_all.py   # une dizaine de minutes"),
         P("Restaurer la base dans une instance PostgreSQL existante", "h2"),
         code("createdb sig_ccst\npsql -d sig_ccst -c \"CREATE EXTENSION postgis; CREATE EXTENSION pg_trgm; "
              "CREATE EXTENSION unaccent;\"\npg_restore -d sig_ccst --no-owner livrables/02_Base_PostGIS/sig_ccst.backup"),
         encadre("Projet de démonstration réalisé à partir de données ouvertes ; il n'engage ni la Ville ni la "
                 "communauté de communes. Attributs du patrimoine arboré simulés.", pdf.ALERTE_PALE)]
    pdf.construire(DOCS_PDF / "00_Bordereau_de_livraison.pdf", "Bordereau de livraison", None, H)


def main():
    DOCS_PDF.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    apercus_planches()
    try:
        captures_web()
    except Exception as err:  # navigateur absent ou service IGN indisponible
        log(f"  captures web non réalisées : {err}")
    schema_architecture()
    log("Exemple de diffusion à un tiers")
    import extraction
    extraction.main(["--reference", "DIF-EXEMPLE", "--demandeur", "Bureau d'études (exemple)",
                     "--objet", "Étude de requalification de la traversée de Châtenois",
                     "--communes", "67073", "--jeux", "zone_urba", "prescription_surf",
                     "sup_assiette_s", "zonage_naturel", "arbre", "intervention"])
    c = chiffres()
    log("Documents PDF")
    note_architecture(c)
    charte(c)
    fiches_tutoriel()
    bordereau_livraison()


if __name__ == "__main__":
    main()
