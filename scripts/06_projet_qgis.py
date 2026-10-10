"""Étape 6 - Projets QGIS (bureau et terrain), planches cartographiques et atlas.

Script PyQGIS, exécuté avec le Python de QGIS (run_all.py s'en charge) :
    "C:\\Program Files\\QGIS 3.34.12\\bin\\python-qgis-ltr.bat" scripts\\06_projet_qgis.py

Produit :
  - qgis/sig_ccst_postgis.qgz : projet de production connecté à PostGIS par un
    service (pg_service.conf), sans aucun mot de passe dans le projet
  - livrables/03_Projets_QGIS/sig_ccst.qgz : le même projet sur GeoPackage
  - livrables/03_Projets_QGIS/qfield/inventaire_arbres.qgz : saisie terrain (QField)
  - livrables/06_Cartes : planches A3 (PDF et PNG)
  - livrables/07_Atlas_communal : atlas A4, une page par commune
"""
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402

os.environ["PGSERVICEFILE"] = str(config.QGIS_DIR / "pg_service.conf")

from qgis.core import (  # noqa: E402
    Qgis, QgsApplication, QgsAttributeEditorContainer, QgsAttributeEditorField,
    QgsAttributeEditorRelation, QgsCategorizedSymbolRenderer, QgsCoordinateReferenceSystem,
    QgsDataSourceUri, QgsDefaultValue, QgsEditFormConfig, QgsEditorWidgetSetup,
    QgsFieldConstraints, QgsFillSymbol, QgsGraduatedSymbolRenderer, QgsHueSaturationFilter,
    QgsInvertedPolygonRenderer, QgsSingleSymbolRenderer,
    QgsLayerMetadata, QgsLayerTreeGroup, QgsLayerTreeLayer, QgsLayoutExporter,
    QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemMap, QgsLayoutItemPage,
    QgsLayoutItemPicture, QgsLayoutItemScaleBar, QgsLayoutItemShape, QgsLayoutMeasurement,
    QgsLayoutPoint, QgsLayoutSize, QgsLegendStyle, QgsLineSymbol, QgsLinePatternFillSymbolLayer,
    QgsMapThemeCollection, QgsMarkerSymbol, QgsPalLayerSettings, QgsPrintLayout, QgsProject,
    QgsPointXY, QgsProperty, QgsRasterLayer, QgsRectangle, QgsRelation, QgsRendererCategory,
    QgsRendererRange, QgsRuleBasedRenderer, QgsSimpleFillSymbolLayer, QgsSymbolLayer,
    QgsTextBufferSettings, QgsTextFormat, QgsUnitTypes, QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import QDateTime, Qt  # noqa: E402
from qgis.PyQt.QtGui import QColor, QFont  # noqa: E402

app = QgsApplication([], False)
app.initQgis()

POLICE = "Segoe UI"
MM = QgsUnitTypes.LayoutMillimeters
CRS = QgsCoordinateReferenceSystem("EPSG:2154")
SVG = Path(QgsApplication.svgPaths()[-1]) if QgsApplication.svgPaths() else None

PROJETS = config.LIVRABLES / "03_Projets_QGIS"
CARTES = config.LIVRABLES / "06_Cartes"
ATLAS = config.LIVRABLES / "07_Atlas_communal"
GPKG = PROJETS / "sig_ccst.gpkg"
GPKG_QFIELD = PROJETS / "qfield" / "inventaire_arbres.gpkg"

TEAL = "#1f4e5a"

# couche -> (schéma, table, clé, géométrie) dans PostGIS
PG = {
    "epci": ("ref_admin", "epci", "siren", "geom"),
    "commune": ("ref_admin", "commune", "code_insee", "geom"),
    "indicateurs_commune": ("ref_admin", "mv_indicateurs_commune", "code_insee", "geom"),
    "parcelle": ("ref_cadastre", "parcelle", "idu", "geom"),
    "adresse": ("ref_adresse", "adresse", "cle_interop", "geom"),
    "batiment": ("ref_topo", "batiment", "cleabs", "geom"),
    "troncon_route": ("ref_topo", "troncon_route", "cleabs", "geom"),
    "troncon_hydro": ("ref_topo", "troncon_hydro", "cleabs", "geom"),
    "surface_hydro": ("ref_topo", "surface_hydro", "cleabs", "geom"),
    "equipement": ("ref_topo", "equipement", "cleabs", "geom"),
    "cimetiere": ("ref_topo", "cimetiere", "cleabs", "geom"),
    "terrain_sport": ("ref_topo", "terrain_sport", "cleabs", "geom"),
    "doc_urba": ("urbanisme", "doc_urba", "code_insee", None),
    "zone_urba": ("urbanisme", "zone_urba", "gid", "geom"),
    "prescription_surf": ("urbanisme", "prescription_surf", "gid", "geom"),
    "prescription_lin": ("urbanisme", "prescription_lin", "gid", "geom"),
    "info_surf": ("urbanisme", "info_surf", "gid", "geom"),
    "sup_assiette_s": ("servitudes", "v_assiette_s", "gid", "geom"),
    "sup_generateur_s": ("servitudes", "v_generateur_s", "gid", "geom"),
    "zonage_naturel": ("environnement", "zonage_naturel", "gid", "geom"),
    "arbre": ("espaces_verts", "arbre", "id", "geom"),
    "intervention": ("espaces_verts", "intervention", "id", None),
    "arbre_prioritaire": ("espaces_verts", "v_arbre_prioritaire", "id", "geom"),
    "arbre_diagnostic": ("espaces_verts", "v_arbre_diagnostic_a_programmer", "id", "geom"),
    "liste_essence": ("espaces_verts", "liste_essence", "code", None),
    "liste_etat_sanitaire": ("espaces_verts", "liste_etat_sanitaire", "code", None),
    "liste_stade_dev": ("espaces_verts", "liste_stade_dev", "code", None),
    "liste_implantation": ("espaces_verts", "liste_implantation", "code", None),
    "liste_risque": ("espaces_verts", "liste_risque", "code", None),
    "liste_type_intervention": ("espaces_verts", "liste_type_intervention", "code", None),
    "type_prescription": ("urbanisme", "type_prescription", "code", None),
    "controle_zonage_chevauchement": ("controle", "v_zonage_chevauchement", "gid", "geom"),
    "controle_parcelle_hors_zonage": ("controle", "v_parcelle_hors_zonage", "idu", "geom"),
    "controle_adresse_non_certifiee": ("controle", "v_adresse_non_certifiee", "cle_interop", "geom"),
    "controle_batiment_sans_adresse": ("controle", "v_batiment_sans_adresse", "cleabs", "geom"),
    "controle_arbre_doublon": ("controle", "v_arbre_doublon", "numero_a", "geom"),
    "controle_arbre_incomplet": ("controle", "v_arbre_incomplet", "numero", "geom"),
}


def log(msg):
    print(f"[PyQGIS] {msg}", flush=True)


# =============================================================================
# Sources de données
# =============================================================================
class Source:
    """Fabrique de couches : GeoPackage (portable) ou PostGIS (production)."""

    def __init__(self, mode, gpkg=None):
        self.mode, self.gpkg = mode, gpkg

    def couche(self, nom, titre):
        if self.mode == "gpkg":
            lyr = QgsVectorLayer(f"{self.gpkg}|layername={nom}", titre, "ogr")
        else:
            schema, table, cle, geom = PG[nom]
            uri = QgsDataSourceUri()
            uri.setConnection(config.PG_SERVICE, "", "", "")
            uri.setDataSource(schema, table, geom or "", "", cle)
            if geom:
                uri.setSrid("2154")
            lyr = QgsVectorLayer(uri.uri(False), titre, "postgres")
        if not lyr.isValid():
            raise RuntimeError(f"Couche invalide : {nom} ({self.mode})")
        return lyr


def xyz(couche_ign, titre, fmt="image/png", style="normal"):
    url = ("https://data.geopf.fr/wmts?SERVICE%3DWMTS%26REQUEST%3DGetTile%26VERSION%3D1.0.0"
           f"%26LAYER%3D{couche_ign}%26STYLE%3D{style}%26TILEMATRIXSET%3DPM%26FORMAT%3D{fmt}"
           "%26TILEMATRIX%3D%7Bz%7D%26TILEROW%3D%7By%7D%26TILECOL%3D%7Bx%7D")
    lyr = QgsRasterLayer(f"type=xyz&url={url}&zmax=19&zmin=0&http-header:referer=",
                         titre, "wms")
    return lyr


def fond_gris(lyr, opacite=0.55):
    lyr.hueSaturationFilter().setGrayscaleMode(QgsHueSaturationFilter.GrayscaleLuminosity)
    lyr.brightnessFilter().setBrightness(25)
    lyr.brightnessFilter().setContrast(-15)
    lyr.renderer().setOpacity(opacite)
    return lyr


# =============================================================================
# Symbologie
# =============================================================================
def remplissage(couleur="transparent", contour="transparent", largeur=0.26, style_contour="solid"):
    sym = QgsFillSymbol.createSimple({
        "color": couleur, "outline_color": contour, "outline_width": str(largeur),
        "outline_style": style_contour if contour != "transparent" else "no",
        "style": "solid" if couleur != "transparent" else "no"})
    return sym


def hachures(couleur, angle=45, ecart=2.0, largeur=0.3, contour=None, contour_largeur=0.4,
             fond=None):
    sym = remplissage(fond or "transparent", contour or couleur, contour_largeur)
    hach = QgsLinePatternFillSymbolLayer()
    hach.setLineAngle(angle)
    hach.setDistance(ecart)
    hach.setLineWidth(largeur)
    hach.setColor(QColor(couleur))
    hach.subSymbol().setColor(QColor(couleur))
    hach.subSymbol().setWidth(largeur)
    sym.appendSymbolLayer(hach)
    return sym


def ligne(couleur, largeur=0.4, style="solid"):
    return QgsLineSymbol.createSimple({"line_color": couleur, "line_width": str(largeur),
                                       "line_style": style, "capstyle": "round",
                                       "joinstyle": "round"})


def point(couleur, taille=2.0, forme="circle", contour="#ffffff", contour_largeur=0.2):
    return QgsMarkerSymbol.createSimple({"name": forme, "color": couleur, "size": str(taille),
                                         "outline_color": contour,
                                         "outline_width": str(contour_largeur)})


def categories(lyr, champ, items):
    cats = [QgsRendererCategory(v, sym, lib) for v, lib, sym in items]
    lyr.setRenderer(QgsCategorizedSymbolRenderer(champ, cats))


def regles(lyr, items, sinon=None):
    racine = QgsRuleBasedRenderer.Rule(None)
    for lib, expr, sym in items:
        racine.appendChild(QgsRuleBasedRenderer.Rule(sym, 0, 0, expr, lib))
    if sinon:
        lib, sym = sinon
        r = QgsRuleBasedRenderer.Rule(sym, 0, 0, "", lib)
        r.setIsElse(True)
        racine.appendChild(r)
    lyr.setRenderer(QgsRuleBasedRenderer(racine))


def etiquettes(lyr, expr, taille=8.0, couleur="#333333", gras=False, tampon=True,
               echelle_max=None, placement=None, italique=False):
    s = QgsPalLayerSettings()
    s.fieldName = expr
    s.isExpression = True
    fmt = QgsTextFormat()
    font = QFont(POLICE)
    font.setBold(gras)
    font.setItalic(italique)
    fmt.setFont(font)
    fmt.setSize(taille)
    fmt.setColor(QColor(couleur))
    if tampon:
        b = QgsTextBufferSettings()
        b.setEnabled(True)
        b.setSize(0.8)
        b.setColor(QColor(255, 255, 255, 220))
        fmt.setBuffer(b)
    s.setFormat(fmt)
    if placement is not None:
        s.placement = placement
    if echelle_max:
        s.scaleVisibility = True
        s.minimumScale = echelle_max  # échelle la plus "dézoomée" où l'étiquette s'affiche
        s.maximumScale = 1
    lyr.setLabeling(QgsVectorLayerSimpleLabeling(s))
    lyr.setLabelsEnabled(True)


def visible_sous(lyr, echelle):
    lyr.setScaleBasedVisibility(True)
    lyr.setMinimumScale(echelle)
    lyr.setMaximumScale(1)


COULEURS_ZONES = [
    ("U", "Zone urbaine (U)", "#e0614f"),
    ("AUc", "Zone à urbaniser ouverte (AUc)", "#f29b46"),
    ("AUs", "Zone à urbaniser fermée (AUs)", "#f7c98b"),
    ("A", "Zone agricole (A)", "#f3e27a"),
    ("N", "Zone naturelle et forestière (N)", "#7cb56b"),
]
COULEURS_SUP = [
    ("PM1", "PM1 - Plans de prévention des risques (PPRI)", "#2c6fbb", "hach", 135),
    ("AC1", "AC1 - Abords des monuments historiques", "#8e44ad", "hach", 45),
    ("AC2", "AC2 - Sites inscrits et classés", "#d35f9a", "hach", 0),
    ("AC3", "AC3 - Réserve naturelle", "#2e7d32", "contour", 0),
    ("A4", "A4 - Berges de cours d'eau non domaniaux", "#5dade2", "contour", 0),
    ("I4", "I4 - Lignes électriques", "#e67e22", "contour", 0),
    ("T1", "T1 - Voies ferrées", "#555555", "contour", 0),
    ("PM2", "PM2 - Installations classées", "#c0392b", "hach", 90),
]
COULEURS_NATURE = [
    ("SIC", "Natura 2000 - Directive Habitats (ZSC)", "#2e8b57", "hach", 45),
    ("ZPS", "Natura 2000 - Directive Oiseaux (ZPS)", "#6b8e23", "hach", 135),
    ("ZNIEFF1", "ZNIEFF de type I", "#c9b400", "plein", 0),
    ("ZNIEFF2", "ZNIEFF de type II", "#e8d97a", "contour", 0),
    ("RNR", "Réserve naturelle régionale", "#1b5e20", "plein", 0),
    ("APB", "Arrêté de protection de biotope", "#00897b", "plein", 0),
]
ETATS = [("bon", "Bon", "#2b8a3e"), ("moyen", "Moyen", "#94c47d"),
         ("surveiller", "À surveiller", "#f2c94c"), ("deperissant", "Dépérissant", "#e8590c"),
         ("mort", "Mort ou dangereux", "#a61e4d")]


def style_zonage(lyr, opacite=0.75, etiq=True):
    items = [(code, lib, remplissage(QColor(c).name(), QColor(c).darker(140).name(), 0.2))
             for code, lib, c in COULEURS_ZONES]
    categories(lyr, "typezone", items)
    lyr.setOpacity(opacite)
    if etiq:
        etiquettes(lyr, '"libelle"', 7.5, "#3b2a26", gras=True, echelle_max=15000)


def style_sup(lyr):
    items = []
    for code, lib, c, mode, angle in COULEURS_SUP:
        if mode == "hach":
            sym = hachures(c, angle, 2.2, 0.25, contour=c, contour_largeur=0.35)
        else:
            sym = remplissage("transparent", c, 0.6)
        items.append((f"\"suptype\" = '{code}'", lib, sym))
    regles(lyr, [(lib, expr, sym) for expr, lib, sym in items],
           sinon=("Autres servitudes", remplissage("transparent", "#7f8c8d", 0.3, "dash")))


def style_nature(lyr):
    items = []
    for code, lib, c, mode, angle in COULEURS_NATURE:
        if mode == "hach":
            sym = hachures(c, angle, 2.5, 0.3, contour=c, contour_largeur=0.4)
        elif mode == "plein":
            col = QColor(c)
            col.setAlpha(110)
            sym = remplissage(col.name(QColor.HexArgb), c, 0.4)
        else:
            sym = remplissage("transparent", c, 0.7, "dash")
        items.append((code, lib, sym))
    categories(lyr, "type_zonage", items)


def symbole_arbre(couleur):
    sym = point(couleur, 2.4, "circle", "#ffffff", 0.25)
    sym.setDataDefinedSize(QgsProperty.fromExpression(
        'scale_linear(coalesce("circonference_cm", 80), 20, 420, 1.8, 4.6)'))
    return sym


def style_arbres(lyr):
    items = [(f"{lib}", f"\"statut\" = 'en_place' AND \"etat_sanitaire\" = '{code}'",
              symbole_arbre(c)) for code, lib, c in ETATS]
    etoile = point("transparent", 5.2, "star", "#1f4e5a", 0.45)
    items.append(("Arbre remarquable", "\"statut\" = 'en_place' AND \"remarquable\"", etoile))
    items.append(("Abattu, remplacement à programmer", "\"statut\" = 'abattu'",
                  point("#7f7f7f", 2.2, "cross2", "#7f7f7f", 0.5)))
    regles(lyr, items)
    etiquettes(lyr, '"numero"', 6.5, "#1f4e5a", echelle_max=1500)


def style_prioritaires(lyr):
    regles(lyr, [
        ("Priorité 1 : sécurisation immédiate", '"priorite" = 1', point("transparent", 6.5, "circle", "#c92a2a", 0.8)),
        ("Priorité 2 : intervention sous 6 mois", '"priorite" = 2', point("transparent", 5.5, "circle", "#f08c00", 0.6)),
        ("Priorité 3 : surveillance renforcée", '"priorite" = 3', point("transparent", 4.5, "circle", "#fab005", 0.4)),
    ])


def anomalie(lyr, couleur="#e03131"):
    lyr.setRenderer(QgsRuleBasedRenderer(point(couleur, 3.2, "x", couleur, 0.6)))


# =============================================================================
# Métadonnées des couches (depuis le catalogue)
# =============================================================================
def lire_catalogue():
    chemin = config.LIVRABLES / "05_Metadonnees" / "catalogue_des_donnees.csv"
    if not chemin.exists():
        return {}
    with open(chemin, encoding="utf-8-sig") as f:
        return {r["table_nom"]: r for r in csv.DictReader(f, delimiter=";")}


CATALOGUE = lire_catalogue()


def metadonnees(lyr, nom):
    schema, table = PG.get(nom, (None, None, None, None))[:2]
    fiche = CATALOGUE.get(f"{schema}.{table}")
    if not fiche:
        return
    md = QgsLayerMetadata()
    md.setIdentifier(fiche["identifiant"])
    md.setTitle(fiche["titre"])
    md.setAbstract(fiche["resume"])
    md.setLanguage("FRE")
    md.setKeywords({"Mots-clés": [k.strip() for k in fiche["mots_cles"].split(";") if k.strip()],
                    "Thème INSPIRE": [fiche["theme_inspire"]]})
    md.setLicenses([fiche["licence"]])
    md.setRights([f"Diffusion : {fiche['niveau_diffusion']}"
                  + (f" ({fiche['motif_restriction']})" if fiche["motif_restriction"] else "")])
    md.setHistory([f"Producteur : {fiche['producteur']}", f"Millésime : {fiche['millesime']}",
                   f"Intégration : {fiche['date_integration']}"])
    md.setCrs(CRS)
    lyr.setMetadata(md)


# =============================================================================
# Formulaires de saisie (bureau et QField)
# =============================================================================
def widget(lyr, champ, type_, config_=None):
    idx = lyr.fields().indexOf(champ)
    if idx >= 0:
        lyr.setEditorWidgetSetup(idx, QgsEditorWidgetSetup(type_, config_ or {}))
    return idx


def liste(lyr, champ, liste_lyr, valeur="libelle", nul=True):
    widget(lyr, champ, "ValueRelation", {
        "Layer": liste_lyr.id(), "LayerName": liste_lyr.name(), "LayerProviderName":
        liste_lyr.providerType(), "LayerSource": liste_lyr.source(), "Key": "code",
        "Value": valeur, "AllowNull": nul, "OrderByValue": valeur != "libelle",
        "UseCompleter": valeur == "nom_francais", "AllowMulti": False, "NofColumns": 1})


def alias(lyr, alias_):
    for champ, a in alias_.items():
        idx = lyr.fields().indexOf(champ)
        if idx >= 0:
            lyr.setFieldAlias(idx, a)


def defaut(lyr, champ, expr, maj=False):
    idx = lyr.fields().indexOf(champ)
    if idx >= 0:
        lyr.setDefaultValueDefinition(idx, QgsDefaultValue(expr, maj))


def contrainte(lyr, champ, expr, message, forte=True):
    idx = lyr.fields().indexOf(champ)
    if idx < 0:
        return
    force = (QgsFieldConstraints.ConstraintStrengthHard if forte
             else QgsFieldConstraints.ConstraintStrengthSoft)
    lyr.setConstraintExpression(idx, expr, message)
    lyr.setFieldConstraint(idx, QgsFieldConstraints.ConstraintExpression, force)


def formulaire(lyr, onglets, lecture_seule=(), relation=None):
    cfg = lyr.editFormConfig()
    try:
        cfg.setLayout(Qgis.AttributeFormLayout.DragAndDrop)
    except AttributeError:
        cfg.setLayout(QgsEditFormConfig.TabLayout)
    racine = cfg.invisibleRootContainer()
    racine.clear()
    for titre, champs in onglets:
        onglet = QgsAttributeEditorContainer(titre, racine)
        try:  # onglet (QGIS >= 3.32) plutôt que bloc repliable
            onglet.setType(Qgis.AttributeEditorContainerType.Tab)
        except AttributeError:
            onglet.setIsGroupBox(False)
        for champ in champs:
            if champ == "@relation" and relation is not None:
                el = QgsAttributeEditorRelation(relation, onglet)
                el.setLabel("Interventions")
                onglet.addChildElement(el)
                continue
            idx = lyr.fields().indexOf(champ)
            if idx >= 0:
                onglet.addChildElement(QgsAttributeEditorField(champ, idx, onglet))
        racine.addChildElement(onglet)
    for champ in lecture_seule:
        idx = lyr.fields().indexOf(champ)
        if idx >= 0:
            cfg.setReadOnly(idx, True)
    lyr.setEditFormConfig(cfg)


def configurer_saisie(projet, arbre, intervention, listes, commune_lyr):
    """Formulaires, listes de valeurs, contrôles et valeurs par défaut."""
    rel = QgsRelation()
    rel.setId("intervention_arbre")
    rel.setName("Interventions")
    rel.setReferencingLayer(intervention.id())
    rel.setReferencedLayer(arbre.id())
    rel.addFieldPair("arbre_id", "id")
    rel.setStrength(QgsRelation.Composition)
    projet.relationManager().addRelation(rel)

    alias(arbre, {
        "numero": "N° d'arbre", "code_insee": "Commune (INSEE)", "essence": "Essence",
        "implantation": "Implantation", "stade_dev": "Stade de développement",
        "hauteur_m": "Hauteur (m)", "circonference_cm": "Circonférence à 1,30 m (cm)",
        "annee_plantation": "Année de plantation", "etat_sanitaire": "État sanitaire",
        "risque": "Niveau de risque", "remarquable": "Arbre remarquable",
        "date_diagnostic": "Dernier diagnostic", "statut": "Statut", "observations": "Observations",
        "photo": "Photo", "precision_m": "Précision GNSS (m)", "source_geom": "Origine de la position",
        "source_attributs": "Origine des attributs", "date_creation": "Créé le",
        "auteur_creation": "Créé par", "date_maj": "Modifié le", "auteur_maj": "Modifié par"})
    liste(arbre, "essence", listes["liste_essence"], "nom_francais", nul=False)
    liste(arbre, "implantation", listes["liste_implantation"])
    liste(arbre, "stade_dev", listes["liste_stade_dev"])
    liste(arbre, "etat_sanitaire", listes["liste_etat_sanitaire"])
    liste(arbre, "risque", listes["liste_risque"])
    widget(arbre, "statut", "ValueMap", {"map": [{"En place": "en_place"}, {"Abattu": "abattu"},
                                                 {"À planter": "a_planter"}]})
    widget(arbre, "remarquable", "CheckBox", {"CheckedState": "", "UncheckedState": ""})
    widget(arbre, "hauteur_m", "Range", {"Min": 0.5, "Max": 50, "Step": 0.5, "Precision": 1,
                                         "Style": "SpinBox", "AllowNull": True})
    widget(arbre, "circonference_cm", "Range", {"Min": 5, "Max": 1500, "Step": 5,
                                                "Style": "SpinBox", "AllowNull": True})
    widget(arbre, "date_diagnostic", "DateTime", {"calendar_popup": True, "allow_null": True,
                                                  "display_format": "dd/MM/yyyy",
                                                  "field_format": "yyyy-MM-dd", "field_iso_format": False})
    widget(arbre, "observations", "TextEdit", {"IsMultiline": True, "UseHtml": False})
    widget(arbre, "photo", "ExternalResource", {
        "DocumentViewer": 1, "DocumentViewerHeight": 0, "DocumentViewerWidth": 0,
        "FileWidget": True, "FileWidgetButton": True, "RelativeStorage": 1, "StorageMode": 0,
        "FileWidgetFilter": "Images (*.jpg *.jpeg *.png)"})
    for champ in ("id", "osm_id", "fid"):
        widget(arbre, champ, "Hidden")

    # valeurs par défaut : identifiant, commune déduite de la position (hors
    # connexion dans QField), précision GNSS, traçabilité. La base recalcule la
    # commune et le numéro à la synchronisation (déclencheur).
    defaut(arbre, "id", "uuid('WithoutBraces')")
    defaut(arbre, "code_insee", "overlay_within('Communes', \"code_insee\")[0]", maj=True)
    defaut(arbre, "precision_m", "round(@position_horizontal_accuracy, 2)")
    defaut(arbre, "source_geom", "if(@position_horizontal_accuracy IS NOT NULL, 'gps', 'saisie')")
    defaut(arbre, "source_attributs", "'saisie'")
    defaut(arbre, "statut", "'en_place'")
    defaut(arbre, "essence", "'Indetermine'")
    defaut(arbre, "remarquable", "false")
    defaut(arbre, "date_creation", "now()")
    defaut(arbre, "auteur_creation", "coalesce(@cloud_username, @user_account_name)")
    defaut(arbre, "date_maj", "now()", maj=True)
    defaut(arbre, "auteur_maj", "coalesce(@cloud_username, @user_account_name)", maj=True)

    contrainte(arbre, "hauteur_m", '"hauteur_m" IS NULL OR "hauteur_m" BETWEEN 0.5 AND 50',
               "Hauteur entre 0,5 et 50 m")
    contrainte(arbre, "circonference_cm",
               '"circonference_cm" IS NULL OR "circonference_cm" BETWEEN 5 AND 1500',
               "Circonférence entre 5 et 1 500 cm")
    contrainte(arbre, "annee_plantation",
               '"annee_plantation" IS NULL OR "annee_plantation" BETWEEN 1700 AND year(now())',
               "Année de plantation entre 1700 et l'année en cours")
    contrainte(arbre, "photo",
               "\"etat_sanitaire\" NOT IN ('deperissant', 'mort') OR \"photo\" IS NOT NULL",
               "Photo recommandée pour un arbre dépérissant ou mort", forte=False)
    contrainte(arbre, "risque", "\"etat_sanitaire\" <> 'mort' OR \"risque\" = 'eleve'",
               "Un arbre mort est à risque élevé", forte=False)

    formulaire(arbre, [
        ("Identification", ["numero", "essence", "implantation", "remarquable", "statut"]),
        ("Dimensions", ["stade_dev", "hauteur_m", "circonference_cm", "annee_plantation"]),
        ("État sanitaire", ["etat_sanitaire", "risque", "date_diagnostic", "observations", "photo"]),
        ("Interventions", ["@relation"]),
        ("Traçabilité", ["code_insee", "precision_m", "source_geom", "source_attributs",
                         "date_creation", "auteur_creation", "date_maj", "auteur_maj"]),
    ], lecture_seule=["numero", "code_insee", "precision_m", "source_geom", "source_attributs",
                      "date_creation", "auteur_creation", "date_maj", "auteur_maj"], relation=rel)
    arbre.setDisplayExpression(
        "coalesce(\"numero\", 'Nouvel arbre') || ' - ' || "
        "attribute(get_feature('Listes - essences', 'code', \"essence\"), 'nom_francais')")
    arbre.setMapTipTemplate(
        "<b>[% \"numero\" %]</b><br>"
        "[% attribute(get_feature('Listes - essences', 'code', \"essence\"), 'nom_francais') %]<br>"
        "État : [% attribute(get_feature('Listes - états sanitaires', 'code', \"etat_sanitaire\"), 'libelle') %]<br>"
        "Hauteur : [% \"hauteur_m\" %] m, circonférence : [% \"circonference_cm\" %] cm<br>"
        "Dernier diagnostic : [% format_date(\"date_diagnostic\", 'dd/MM/yyyy') %]")
    # QField : nommage des photos prises sur le terrain
    arbre.setCustomProperty("QFieldSync/attachment_naming",
                            '{"photo": "\'DCIM/arbre_\' || format_date(now(), \'yyyyMMdd_hhmmss\') || \'.jpg\'"}')

    alias(intervention, {"arbre_id": "Arbre", "type_intervention": "Type d'intervention",
                         "date_intervention": "Date", "intervenant": "Intervenant",
                         "cout_ht": "Coût (€ HT)", "etat_constate": "État constaté",
                         "commentaire": "Commentaire"})
    widget(intervention, "arbre_id", "RelationReference", {
        "Relation": rel.id(), "AllowAddFeatures": False, "ShowForm": False,
        "ShowOpenFormButton": True, "MapIdentification": True, "ReadOnly": False})
    liste(intervention, "type_intervention", listes["liste_type_intervention"], nul=False)
    liste(intervention, "etat_constate", listes["liste_etat_sanitaire"])
    widget(intervention, "intervenant", "ValueMap", {"map": [
        {"Régie espaces verts": "Régie espaces verts"},
        {"Prestataire élagage (marché à bons de commande)": "Prestataire élagage (marché à bons de commande)"}]})
    widget(intervention, "date_intervention", "DateTime", {
        "calendar_popup": True, "allow_null": False, "display_format": "dd/MM/yyyy",
        "field_format": "yyyy-MM-dd", "field_iso_format": False})
    widget(intervention, "cout_ht", "Range", {"Min": 0, "Max": 100000, "Step": 10, "Precision": 2,
                                              "Style": "SpinBox", "AllowNull": True})
    widget(intervention, "commentaire", "TextEdit", {"IsMultiline": True, "UseHtml": False})
    for champ in ("id", "fid", "date_creation", "auteur_creation"):
        widget(intervention, champ, "Hidden")
    defaut(intervention, "id", "uuid('WithoutBraces')")
    defaut(intervention, "date_intervention", "to_date(now())")
    defaut(intervention, "intervenant", "'Régie espaces verts'")
    defaut(intervention, "date_creation", "now()")
    defaut(intervention, "auteur_creation", "coalesce(@cloud_username, @user_account_name)")
    intervention.setDisplayExpression(
        "format_date(\"date_intervention\", 'dd/MM/yyyy') || ' - ' || "
        "attribute(get_feature('Listes - types d''intervention', 'code', \"type_intervention\"), 'libelle')")
    return rel


# =============================================================================
# Projet de consultation (bureau)
# =============================================================================
def ajouter(projet, groupe, lyr, visible=True, replie=True):
    projet.addMapLayer(lyr, False)
    noeud = groupe.addLayer(lyr)
    noeud.setItemVisibilityChecked(visible)
    noeud.setExpanded(not replie)
    return lyr


def projet_consultation(source, chemin, titre):
    log(f"Projet {chemin.name} ({source.mode})")
    projet = QgsProject.instance()
    projet.clear()
    projet.setCrs(CRS)
    projet.setTitle(titre)
    md = projet.metadata()
    md.setTitle(titre)
    md.setAuthor(config.AUTEUR)
    md.setAbstract("Socle SIG intercommunal open source (QGIS, PostgreSQL/PostGIS, QField) : "
                   "référentiels, urbanisme, servitudes, environnement et inventaire du "
                   "patrimoine arboré. Projet de démonstration, étude indépendante.")
    md.setCreationDateTime(QDateTime.currentDateTime())
    md.setLanguage("FRE")
    projet.setMetadata(md)
    projet.writeEntry("Paths", "/Absolute", False)
    racine = projet.layerTreeRoot()

    def c(nom, titre_):
        lyr = source.couche(nom, titre_)
        metadonnees(lyr, nom)
        return lyr

    g_hab = racine.addGroup("Habillage des cartes")  # voiles dessinés au-dessus de tout
    g_metier = racine.addGroup("Patrimoine arboré")
    g_urba = racine.addGroup("Urbanisme et servitudes")
    g_env = racine.addGroup("Environnement")
    g_ref = racine.addGroup("Référentiels")
    g_ctrl = racine.addGroup("Contrôle qualité")
    g_ind = racine.addGroup("Indicateurs")
    g_listes = racine.addGroup("Listes de valeurs")
    g_fonds = racine.addGroup("Fonds de plan")

    L = {}
    # --- patrimoine arboré
    L["prior"] = ajouter(projet, g_metier, c("arbre_prioritaire", "Arbres prioritaires"), False)
    style_prioritaires(L["prior"])
    L["diag"] = ajouter(projet, g_metier, c("arbre_diagnostic", "Diagnostics à programmer"), False)
    L["diag"].setRenderer(QgsRuleBasedRenderer(point("transparent", 4.0, "square", "#5c7cfa", 0.5)))
    L["arbre"] = ajouter(projet, g_metier, c("arbre", "Arbres"), True, replie=False)
    style_arbres(L["arbre"])
    L["intervention"] = ajouter(projet, g_metier, c("intervention", "Interventions"), True)

    # --- urbanisme et servitudes
    L["sup_gen"] = ajouter(projet, g_urba, c("sup_generateur_s", "Monuments et sites protégés (générateurs)"), False)
    # seuls les monuments sont dessinés : les autres générateurs (PPRI, réserve) doublent leur assiette
    regles(L["sup_gen"], [("Monument historique", "\"suptype\" = 'AC1'", remplissage("#8e44ad", "#5b2c6f", 0.3))])
    L["sup"] = ajouter(projet, g_urba, c("sup_assiette_s", "Servitudes d'utilité publique"), False)
    style_sup(L["sup"])
    L["info"] = ajouter(projet, g_urba, c("info_surf", "Informations (DPU, bruit, SIS...)"), False)
    L["info"].setRenderer(QgsRuleBasedRenderer(remplissage("transparent", "#6c757d", 0.35, "dot")))
    L["presc_l"] = ajouter(projet, g_urba, c("prescription_lin", "Prescriptions linéaires"), False)
    L["presc_l"].setRenderer(QgsRuleBasedRenderer(ligne("#2f9e44", 0.7, "dash")))
    L["presc"] = ajouter(projet, g_urba, c("prescription_surf", "Prescriptions surfaciques"), False)
    regles(L["presc"], [
        ("Espace boisé classé", "\"typepsc\" = '01'", hachures("#2b8a3e", 45, 1.6, 0.3, "#2b8a3e", 0.5)),
        ("Secteur de risques ou de nuisances", "\"typepsc\" = '02'", hachures("#1c7ed6", 135, 2.0, 0.25, "#1c7ed6", 0.4)),
        ("Emplacement réservé", "\"typepsc\" = '05'", hachures("#e8590c", 0, 1.5, 0.25, "#e8590c", 0.5)),
        ("Patrimoine bâti ou paysager protégé", "\"typepsc\" = '07'", remplissage("#b2f2bb", "#2f9e44", 0.3)),
        ("Orientation d'aménagement (OAP)", "\"typepsc\" = '18'", remplissage("transparent", "#862e9c", 0.8, "dash")),
    ], sinon=("Autre prescription", remplissage("transparent", "#495057", 0.3, "dot")))
    L["zone"] = ajouter(projet, g_urba, c("zone_urba", "Zonage des PLU"), True)
    style_zonage(L["zone"], 0.55)
    L["doc"] = ajouter(projet, g_urba, c("doc_urba", "Documents d'urbanisme"), True)

    # --- environnement
    L["nature"] = ajouter(projet, g_env, c("zonage_naturel", "Zonages du patrimoine naturel"), False)
    style_nature(L["nature"])

    # --- référentiels
    L["adresse"] = ajouter(projet, g_ref, c("adresse", "Adresses (BAN)"), True)
    regles(L["adresse"], [("Adresse certifiée", '"certification_commune"', point("#5f3dc4", 1.6, "circle", "#ffffff", 0.15)),
                          ("Adresse non certifiée", 'NOT "certification_commune"', point("#f59f00", 1.6, "circle", "#ffffff", 0.15))])
    etiquettes(L["adresse"], "\"numero\" || coalesce(\"rep\", '')", 6.5, "#5f3dc4", echelle_max=2500)
    visible_sous(L["adresse"], 10000)
    L["parcelle"] = ajouter(projet, g_ref, c("parcelle", "Parcelles cadastrales"), True)
    L["parcelle"].setRenderer(QgsRuleBasedRenderer(remplissage("transparent", "#8d8d8d", 0.15)))
    etiquettes(L["parcelle"], "ltrim(\"numero\", '0')", 6.5, "#6d6d6d", tampon=False, echelle_max=2500)
    visible_sous(L["parcelle"], 12000)
    L["batiment"] = ajouter(projet, g_ref, c("batiment", "Bâtiments"), True)
    L["batiment"].setRenderer(QgsRuleBasedRenderer(remplissage("#d9cfc4", "#a89a8c", 0.1)))
    visible_sous(L["batiment"], 30000)
    L["equip"] = ajouter(projet, g_ref, c("equipement", "Équipements et sites d'intérêt"), False)
    L["equip"].setRenderer(QgsRuleBasedRenderer(remplissage("#eee3f4", "#9c7bb5", 0.25)))
    etiquettes(L["equip"], '"toponyme"', 7, "#6a3d8f", italique=True, echelle_max=8000)
    L["cimetiere"] = ajouter(projet, g_ref, c("cimetiere", "Cimetières"), False)
    L["cimetiere"].setRenderer(QgsRuleBasedRenderer(hachures("#868e96", 90, 1.5, 0.2, "#868e96", 0.3, "#e9ecef")))
    L["sport"] = ajouter(projet, g_ref, c("terrain_sport", "Terrains de sport"), False)
    L["sport"].setRenderer(QgsRuleBasedRenderer(remplissage("#d3f9d8", "#69db7c", 0.2)))
    L["route"] = ajouter(projet, g_ref, c("troncon_route", "Voirie"), True)
    regles(L["route"], [
        ("Route principale", "\"importance\" IN ('1', '2')", ligne("#c9822b", 0.9)),
        ("Route secondaire", "\"importance\" IN ('3', '4')", ligne("#9c9c9c", 0.5)),
    ], sinon=("Desserte locale", ligne("#c6c6c6", 0.25)))
    L["hydro_s"] = ajouter(projet, g_ref, c("surface_hydro", "Surfaces en eau"), True)
    L["hydro_s"].setRenderer(QgsRuleBasedRenderer(remplissage("#a5d8ff", "#74c0fc", 0.1)))
    L["hydro"] = ajouter(projet, g_ref, c("troncon_hydro", "Cours d'eau"), True)
    regles(L["hydro"], [("Ill", "\"cpx_toponyme_de_cours_d_eau\" = 'l''Ill'", ligne("#339af0", 1.0))],
           sinon=("Autres cours d'eau", ligne("#74c0fc", 0.4)))
    L["commune"] = ajouter(projet, g_ref, c("commune", "Communes"), True)
    L["commune"].setRenderer(QgsRuleBasedRenderer(remplissage("transparent", "#495057", 0.6, "dash")))
    etiquettes(L["commune"], '"nom"', 9, "#343a40", gras=True,
               placement=Qgis.LabelPlacement.OverPoint if hasattr(Qgis, "LabelPlacement") else None)
    L["epci"] = ajouter(projet, g_ref, c("epci", "Périmètre intercommunal"), True)
    L["epci"].setRenderer(QgsRuleBasedRenderer(remplissage("transparent", TEAL, 1.2)))
    # voile blanc hors du territoire : met en valeur l'intercommunalité sur les planches
    L["masque"] = ajouter(projet, g_hab, c("epci", "Hors territoire (voile)"), False)
    L["masque"].setRenderer(QgsInvertedPolygonRenderer(
        QgsSingleSymbolRenderer(remplissage("#ffffff", "transparent"))))
    L["masque"].setOpacity(0.6)

    # --- contrôle qualité
    for nom, titre_, coul in [
        ("controle_zonage_chevauchement", "Chevauchements de zones", "#e03131"),
        ("controle_parcelle_hors_zonage", "Parcelles hors zonage", "#e03131"),
        ("controle_batiment_sans_adresse", "Logements sans adresse", "#d6336c"),
        ("controle_adresse_non_certifiee", "Adresses non certifiées", "#f59f00"),
        ("controle_arbre_doublon", "Arbres en doublon", "#e03131"),
        ("controle_arbre_incomplet", "Fiches arbre incomplètes", "#f76707"),
    ]:
        L[nom] = ajouter(projet, g_ctrl, c(nom, titre_), False)
        anomalie(L[nom], coul)
    g_ctrl.setItemVisibilityChecked(False)

    # --- indicateurs (pour les planches et l'atlas)
    L["ind_adr"] = ajouter(projet, g_ind, c("indicateurs_commune", "Adresses certifiées (%)"), False)
    plages = [(0, 10, "Moins de 10 %", "#c92a2a"), (10, 40, "10 à 40 %", "#f08c00"),
              (40, 70, "40 à 70 %", "#fcc419"), (70, 99.9, "70 à 99 %", "#94d82d"),
              (99.9, 100.1, "100 %", "#2b8a3e")]
    rangs = [QgsRendererRange(a, b, remplissage(col, "#ffffff", 0.4), lib) for a, b, lib, col in plages]
    L["ind_adr"].setRenderer(QgsGraduatedSymbolRenderer("adresses_certifiees_pct", rangs))
    L["ind_adr"].setOpacity(0.85)
    etiquettes(L["ind_adr"], "\"nom\" || '\\n' || format_number(\"adresses_certifiees_pct\", 0) || ' %'",
               8, "#212529", gras=True)
    L["ind_doc"] = ajouter(projet, g_ind, c("indicateurs_commune", "Communes sans document au GPU"), False)
    regles(L["ind_doc"], [("Document d'urbanisme non publié sur le GPU", "\"document_urbanisme\" = 'Non publié'",
                           hachures("#868e96", 45, 1.6, 0.3, "#495057", 0.4, "#f1f3f5"))])
    L["voile_atlas"] = ajouter(projet, g_hab, c("indicateurs_commune", "Hors commune (voile atlas)"), False)
    regles(L["voile_atlas"], [("Autres communes", "\"code_insee\" <> attribute(@atlas_feature, 'code_insee')",
                               remplissage("#ffffff", "transparent"))])
    L["voile_atlas"].setOpacity(0.55)
    L["ind_loc"] = ajouter(projet, g_ind, c("indicateurs_commune", "Localisation (atlas)"), False)
    regles(L["ind_loc"], [("Commune de la page", "\"code_insee\" = attribute(@atlas_feature, 'code_insee')",
                           remplissage("#e8590c", "#ffffff", 0.3))],
           sinon=("Autres communes", remplissage("#dee2e6", "#ffffff", 0.3)))
    g_ind.setItemVisibilityChecked(False)

    # --- listes de valeurs (tables sans géométrie)
    titres_listes = {"liste_essence": "Listes - essences", "liste_etat_sanitaire": "Listes - états sanitaires",
                     "liste_stade_dev": "Listes - stades", "liste_implantation": "Listes - implantations",
                     "liste_risque": "Listes - risques", "liste_type_intervention": "Listes - types d'intervention"}
    listes = {nom: ajouter(projet, g_listes, c(nom, t)) for nom, t in titres_listes.items()}
    g_listes.setExpanded(False)

    # --- fonds de plan IGN
    L["plan"] = ajouter(projet, g_fonds, xyz("GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2", "Plan IGN"), True)
    L["plan_gris"] = ajouter(projet, g_fonds, fond_gris(xyz("GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2",
                                                             "Plan IGN (gris)")), False)
    L["ortho"] = ajouter(projet, g_fonds, xyz("ORTHOIMAGERY.ORTHOPHOTOS", "Photographies aériennes (IGN)",
                                              "image/jpeg"), False)
    for g in (g_ctrl, g_ind, g_listes, g_env, g_hab):
        g.setExpanded(False)

    # Les listes et la commune servent aux expressions des formulaires
    L["commune"].setName("Communes")
    configurer_saisie(projet, L["arbre"], L["intervention"], listes, L["commune"])
    themes(projet, L)
    mises_en_page(projet, L)
    emprise = L["epci"].extent()
    emprise.grow(800)
    projet.viewSettings().setDefaultViewExtent(
        __import__("qgis.core", fromlist=["QgsReferencedRectangle"]).QgsReferencedRectangle(emprise, CRS))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if not projet.write(str(chemin)):
        raise RuntimeError(f"Écriture impossible : {chemin}")
    return projet, L


# =============================================================================
# Thèmes de carte (une combinaison de couches par usage)
# =============================================================================
def themes(projet, L):
    coll = projet.mapThemeCollection()
    racine = projet.layerTreeRoot()
    modele = __import__("qgis.core", fromlist=["QgsLayerTreeModel"]).QgsLayerTreeModel(racine)
    base_ref = ["epci", "masque", "commune", "hydro", "hydro_s", "route"]
    definitions = {
        "Territoire": base_ref + ["batiment", "plan_gris"],
        "Urbanisme": base_ref + ["zone", "batiment", "parcelle", "plan_gris"],
        "Urbanisme détaillé": base_ref + ["zone", "presc", "presc_l", "batiment", "parcelle", "adresse", "plan_gris"],
        "Servitudes et risques": base_ref + ["sup", "sup_gen", "batiment", "plan_gris"],
        "Patrimoine naturel": base_ref + ["nature", "plan_gris"],
        "Patrimoine arboré": ["epci", "commune", "arbre", "prior", "batiment", "route", "hydro", "hydro_s", "plan_gris"],
        "Patrimoine arboré (photo)": ["arbre", "prior", "ortho"],
        "Adressage": ["epci", "masque", "ind_adr", "controle_batiment_sans_adresse", "route", "hydro", "plan_gris"],
        "Documents d'urbanisme": base_ref + ["zone", "ind_doc", "plan_gris"],
        "Atlas commune": ["epci", "commune", "voile_atlas", "zone", "batiment", "route", "hydro", "hydro_s", "arbre", "plan_gris"],
        "Atlas localisation": ["ind_loc", "epci"],
        "Contrôle qualité": base_ref + ["zone", "controle_zonage_chevauchement", "controle_parcelle_hors_zonage",
                                        "controle_batiment_sans_adresse", "controle_arbre_doublon",
                                        "controle_arbre_incomplet", "batiment", "plan_gris"],
    }
    etat_initial = {lyr.id(): racine.findLayer(lyr.id()).isVisible() for lyr in projet.mapLayers().values()
                    if racine.findLayer(lyr.id())}
    for nom, cles in definitions.items():
        ids = {L[k].id() for k in cles}
        for noeud in racine.findLayers():
            noeud.setItemVisibilityChecked(noeud.layerId() in ids)
        for groupe in racine.findGroups(True) if hasattr(racine, "findGroups") else []:
            groupe.setItemVisibilityChecked(True)
        for g in racine.children():
            if isinstance(g, QgsLayerTreeGroup):
                g.setItemVisibilityChecked(True)
        coll.insert(nom, QgsMapThemeCollection.createThemeFromCurrentState(racine, modele))
    # retour à l'état de consultation par défaut
    for noeud in racine.findLayers():
        noeud.setItemVisibilityChecked(etat_initial.get(noeud.layerId(), False))
    for g in racine.children():
        if isinstance(g, QgsLayerTreeGroup):
            g.setItemVisibilityChecked(g.name() not in ("Contrôle qualité", "Indicateurs", "Habillage des cartes"))


# =============================================================================
# Mises en page : planches A3 et atlas A4
# =============================================================================
def texte(lay, contenu, x, y, w, h, taille=9, couleur="#343a40", gras=False, police=POLICE,
          alignement=Qt.AlignLeft, valign=Qt.AlignTop):
    lbl = QgsLayoutItemLabel(lay)
    lbl.setText(contenu)
    fmt = QgsTextFormat()
    f = QFont(police)
    f.setBold(gras)
    fmt.setFont(f)
    fmt.setSize(taille)
    fmt.setColor(QColor(couleur))
    lbl.setTextFormat(fmt)
    lbl.setHAlign(alignement)
    lbl.setVAlign(valign)
    lbl.attemptMove(QgsLayoutPoint(x, y, MM))
    lbl.attemptResize(QgsLayoutSize(w, h, MM))
    lay.addLayoutItem(lbl)
    return lbl


def rectangle(lay, x, y, w, h, couleur):
    r = QgsLayoutItemShape(lay)
    r.setShapeType(QgsLayoutItemShape.Rectangle)
    r.setSymbol(remplissage(couleur, "transparent"))
    r.attemptMove(QgsLayoutPoint(x, y, MM))
    r.attemptResize(QgsLayoutSize(w, h, MM))
    lay.addLayoutItem(r)
    return r


def ajuster(emprise, largeur_mm, hauteur_mm):
    """Agrandit l'emprise pour qu'elle ait le rapport largeur/hauteur du cadre."""
    e = QgsRectangle(emprise)
    rapport = largeur_mm / hauteur_mm
    if e.width() / e.height() > rapport:
        h = e.width() / rapport
        c = e.center().y()
        e.setYMinimum(c - h / 2)
        e.setYMaximum(c + h / 2)
    else:
        w = e.height() * rapport
        c = e.center().x()
        e.setXMinimum(c - w / 2)
        e.setXMaximum(c + w / 2)
    return e


def carte(lay, theme, emprise, x, y, w, h, cadre=True):
    m = QgsLayoutItemMap(lay)
    m.attemptMove(QgsLayoutPoint(x, y, MM))
    m.attemptResize(QgsLayoutSize(w, h, MM))
    m.setFollowVisibilityPreset(True)
    m.setFollowVisibilityPresetName(theme)
    m.setCrs(CRS)
    m.setExtent(ajuster(emprise, w, h))
    m.setFrameEnabled(cadre)
    m.setFrameStrokeColor(QColor("#adb5bd"))
    m.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, MM))
    lay.addLayoutItem(m)
    return m


def legende(lay, carte_, couches, x, y, w, h=None, titre="Légende", taille=8):
    leg = QgsLayoutItemLegend(lay)
    leg.setTitle(titre)
    leg.setLinkedMap(carte_)
    leg.setAutoUpdateModel(False)
    groupe = leg.model().rootGroup()
    groupe.clear()
    for lyr, nom in couches:
        n = groupe.addLayer(lyr)
        if nom:  # libellé propre à la légende, sans renommer la couche du projet
            n.setCustomProperty("legend/title-label", nom)
    leg.setLegendFilterByMapEnabled(True)
    leg.setSymbolWidth(6)
    leg.setSymbolHeight(4)
    for style, t, g in ((QgsLegendStyle.Title, taille + 3, True), (QgsLegendStyle.Group, taille + 1, True),
                        (QgsLegendStyle.Subgroup, taille + 0.5, True), (QgsLegendStyle.SymbolLabel, taille, False)):
        f = QFont(POLICE)
        f.setBold(g)
        fmt = QgsTextFormat()
        fmt.setFont(f)
        fmt.setSize(t)
        fmt.setColor(QColor("#343a40"))
        leg.rstyle(style).setTextFormat(fmt)
    leg.setWrapString("|")
    leg.attemptMove(QgsLayoutPoint(x, y, MM))
    if h:
        leg.setResizeToContents(False)
        leg.attemptResize(QgsLayoutSize(w, h, MM))
    lay.addLayoutItem(leg)
    leg.updateLegend()
    return leg


def echelle_nord(lay, carte_, x, y):
    sb = QgsLayoutItemScaleBar(lay)
    sb.setLinkedMap(carte_)
    sb.setStyle("Line Ticks Up")
    sb.applyDefaultSize(QgsUnitTypes.DistanceKilometers)
    sb.setUnitLabel("km")
    sb.setNumberOfSegmentsLeft(0)
    sb.setNumberOfSegments(2)
    fmt = QgsTextFormat()
    fmt.setFont(QFont(POLICE))
    fmt.setSize(8)
    sb.setTextFormat(fmt)
    sb.attemptMove(QgsLayoutPoint(x, y, MM))
    lay.addLayoutItem(sb)
    nord = QgsLayoutItemPicture(lay)
    for chemin in QgsApplication.svgPaths():
        svg = Path(chemin) / "arrows" / "NorthArrow_02.svg"
        if svg.exists():
            nord.setPicturePath(str(svg))
            break
    nord.attemptMove(QgsLayoutPoint(x + 62, y - 4, MM))
    nord.attemptResize(QgsLayoutSize(9, 12, MM))
    lay.addLayoutItem(nord)


SOURCES = ("Sources : IGN (ADMIN EXPRESS, BD TOPO, Parcellaire Express, Plan IGN), "
           "Base Adresse Nationale, Géoportail de l'Urbanisme, INPN, © contributeurs "
           "OpenStreetMap (ODbL). Données métier simulées pour la démonstration.")


def planche(projet, nom, titre, sous_titre, theme, emprise, couches_legende, commentaire):
    lay = QgsPrintLayout(projet)
    lay.initializeDefaults()
    lay.setName(nom)
    lay.pageCollection().page(0).setPageSize("A3", QgsLayoutItemPage.Landscape)
    rectangle(lay, 0, 0, 420, 22, TEAL)
    texte(lay, titre, 10, 4, 330, 10, 20, "#ffffff", True)
    texte(lay, sous_titre, 10, 13.5, 330, 7, 10.5, "#cfe3e8")
    texte(lay, config.EPCI_NOM, 300, 7, 112, 8, 10, "#ffffff", True, alignement=Qt.AlignRight)
    m = carte(lay, theme, emprise, 8, 28, 292, 261)
    legende(lay, m, couches_legende, 308, 28, 104)
    rectangle(lay, 308, 196, 104, 0.4, "#ced4da")
    texte(lay, commentaire, 308, 200, 104, 52, 8.5, "#343a40")
    echelle_nord(lay, m, 308, 258)
    texte(lay, SOURCES, 308, 274, 104, 16, 6, "#868e96")
    texte(lay, f"Réalisation : {config.AUTEUR}, octobre 2026 · Projet de démonstration "
          f"(étude indépendante) · QGIS {Qgis.version().split('-')[0]} · Lambert-93",
          8, 291, 292, 5, 6, "#868e96")
    projet.layoutManager().addLayout(lay)
    return lay


def fmt_nb(v, dec=0):
    try:
        return f"{float(v):,.{dec}f}".replace(",", "\u202f").replace(".", ",")
    except (TypeError, ValueError):
        return "-"


def mises_en_page(projet, L):
    ind = {f["code_insee"]: f for f in L["ind_adr"].getFeatures()}
    epci = L["epci"].extent()
    epci.grow(600)
    pop = sum(f["population"] or 0 for f in ind.values())
    sans_doc = [f["nom"] for f in ind.values() if f["document_urbanisme"] == "Non publié"]
    adr = sum(f["nb_adresses"] or 0 for f in ind.values())
    cert = sum((f["nb_adresses"] or 0) * (f["adresses_certifiees_pct"] or 0) / 100 for f in ind.values())
    sans_adr = sum(f["logements_sans_adresse"] or 0 for f in ind.values())
    sel = ind.get(config.VILLE_CENTRE)
    arbres = [f for f in L["arbre"].getFeatures() if f["statut"] == "en_place"]
    degrades = sum(1 for f in arbres if f["etat_sanitaire"] in ("deperissant", "mort"))
    prio1 = sum(1 for f in L["prior"].getFeatures() if f["priorite"] == 1)

    planche(projet, "P01 Territoire", "Le territoire intercommunal",
            "12 communes entre le piémont vosgien et le Ried de l'Ill", "Territoire", epci,
            [(L["epci"], "Périmètre intercommunal"), (L["commune"], "Limites communales"),
             (L["route"], "Voirie"), (L["hydro"], "Cours d'eau"), (L["batiment"], "Bâti")],
            f"{fmt_nb(pop)} habitants (population légale 2023) dont {fmt_nb(sel['population'])} à "
            f"Sélestat, ville-centre. Le territoire s'étend des crêtes du massif vosgien "
            f"(La Vancelle, Dieffenthal, Kintzheim) jusqu'aux prairies inondables du Ried de "
            f"l'Ill (Muttersholtz, Ebersmunster), traversé par l'Ill et le Giessen.")
    planche(projet, "P02 Urbanisme", "Documents d'urbanisme et zonage",
            "Zonage des PLU en vigueur publiés sur le Géoportail de l'Urbanisme", "Documents d'urbanisme", epci,
            [(L["zone"], "Zonage des PLU"), (L["ind_doc"], ""), (L["commune"], "Limites communales")],
            f"9 communes sur 12 disposent d'un PLU publié au standard CNIG sur le Géoportail "
            f"de l'Urbanisme. {', '.join(sorted(sans_doc))} n'y ont pas de document "
            f"publié : la publication sur le GPU conditionne pourtant le caractère exécutoire "
            f"des documents depuis 2020. Un accompagnement des communes pour la numérisation "
            f"au standard CNIG est à prévoir.")
    planche(projet, "P03 Servitudes", "Servitudes d'utilité publique et risques",
            "Assiettes des SUP publiées au Géoportail de l'Urbanisme", "Servitudes et risques", epci,
            [(L["sup"], "Servitudes d'utilité publique"), (L["sup_gen"], ""), (L["commune"], "Limites communales")],
            "Les plans de prévention du risque inondation (PPRI de l'Ill, du Giessen et de la "
            "Fecht) couvrent une large part du Ried. Les abords des monuments historiques "
            "(Haut-Koenigsbourg, centre ancien de Sélestat, châteaux de l'Ortenbourg et du "
            "Ramstein) encadrent les autorisations d'urbanisme : ces assiettes alimentent la "
            "fiche parcelle utilisée pour l'instruction (ADS).")
    planche(projet, "P04 Patrimoine naturel", "Patrimoine naturel",
            "Natura 2000, ZNIEFF, réserve naturelle et arrêtés de biotope", "Patrimoine naturel", epci,
            [(L["nature"], "Zonages du patrimoine naturel"), (L["commune"], "Limites communales")],
            "Le Ried de l'Ill concentre les enjeux : sites Natura 2000 (directives Habitats et "
            "Oiseaux), ZNIEFF et réserve naturelle régionale du Ried de Sélestat (Ill*Wald), "
            "gérée par la Ville. Ces zonages sont croisés automatiquement avec chaque parcelle "
            "dans la fiche de renseignements.")
    # patrimoine arboré : emprise des arbres de Sélestat
    centre = QgsPointXY(1030100, 6804900)  # centre-ville de Sélestat (Lambert-93)
    em_arbres = QgsRectangle()
    for f in arbres:
        if f.geometry().asPoint().distance(centre) < 1800:
            em_arbres.combineExtentWith(f.geometry().boundingBox())
    em_arbres.grow(200)
    planche(projet, "P05 Patrimoine arbore", "Patrimoine arboré de Sélestat",
            "Inventaire, état sanitaire et priorités d'intervention", "Patrimoine arboré", em_arbres,
            [(L["arbre"], "Arbres (taille selon la circonférence)"), (L["prior"], "Priorités d'intervention")],
            f"{fmt_nb(len(arbres))} arbres inventoriés sur le territoire, dont {degrades} "
            f"dépérissants ou morts et {prio1} à sécuriser en priorité. Positions issues "
            f"d'OpenStreetMap, attributs simulés : l'inventaire se complète sur le terrain "
            f"avec QField, et la base met à jour l'état de l'arbre à chaque diagnostic.")
    planche(projet, "P06 Adressage", "Qualité de l'adressage",
            "Certification des adresses par les communes (Base Adresse Locale)", "Adressage", epci,
            [(L["ind_adr"], "Adresses certifiées par la commune"),
             (L["controle_batiment_sans_adresse"], "Logement sans adresse à moins de 30 m")],
            f"{fmt_nb(cert / adr * 100 if adr else 0)} % des {fmt_nb(adr)} adresses sont "
            f"certifiées par leur commune. Depuis la loi 3DS (2022), chaque commune est "
            f"responsable de son adressage. {fmt_nb(sans_adr)} bâtiments d'habitation n'ont "
            f"aucune adresse à moins de 30 m : une liste de vérification est fournie aux "
            f"communes pour compléter leur Base Adresse Locale.")
    atlas(projet, L)


def atlas(projet, L):
    lay = QgsPrintLayout(projet)
    lay.initializeDefaults()
    lay.setName("Atlas communal")
    lay.pageCollection().page(0).setPageSize("A4", QgsLayoutItemPage.Portrait)
    at = lay.atlas()
    at.setCoverageLayer(L["ind_loc"])
    at.setEnabled(True)
    at.setPageNameExpression('"nom"')
    at.setSortFeatures(True)
    at.setSortExpression('"nom"')
    at.setFilenameExpression("'atlas_' || \"code_insee\"")

    rectangle(lay, 0, 0, 210, 26, TEAL)
    texte(lay, '[% "nom" %]', 10, 4, 150, 12, 22, "#ffffff", True)
    texte(lay, "Fiche d'identité SIG · [% \"code_insee\" %] · " + config.EPCI_NOM, 10, 16, 170, 7, 9.5, "#cfe3e8")
    m = carte(lay, "Atlas commune", L["epci"].extent(), 10, 32, 190, 150)
    m.setAtlasDriven(True)
    m.setAtlasScalingMode(QgsLayoutItemMap.Auto)
    m.setAtlasMargin(0.06)
    loc = carte(lay, "Atlas localisation", ajuster(L["epci"].extent(), 38, 34), 162, 32, 38, 34)
    loc.setBackgroundColor(QColor(255, 255, 255, 230))
    echelle_nord(lay, m, 12, 170)

    colonne1 = (
        "TERRITOIRE\n"
        "Population : [% format_number(\"population\", 0) %] habitants\n"
        "Superficie : [% format_number(\"surface_ha\", 0) %] ha · [% \"densite_hab_km2\" %] hab./km²\n"
        "Bâtiments : [% format_number(\"nb_batiments\", 0) %] · logements : [% format_number(\"nb_logements\", 0) %]\n"
        "Parcelles cadastrales : [% format_number(\"nb_parcelles\", 0) %]\n\n"
        "URBANISME\n"
        "Document : [% \"document_urbanisme\" %][% if(\"date_approbation\" IS NOT NULL, ' approuvé le ' || format_date(\"date_approbation\", 'dd/MM/yyyy'), ' sur le GPU') %]\n"
        "Zones U : [% coalesce(format_number(\"zone_u_ha\", 0), '-') %] ha · AU : [% coalesce(format_number(\"zone_au_ha\", 0), '-') %] ha\n"
        "Zones A : [% coalesce(format_number(\"zone_a_ha\", 0), '-') %] ha · N : [% coalesce(format_number(\"zone_n_ha\", 0), '-') %] ha\n"
    )
    colonne2 = (
        "ADRESSAGE\n"
        "Adresses : [% format_number(\"nb_adresses\", 0) %], dont [% format_number(\"adresses_certifiees_pct\", 0) %] % certifiées\n"
        "Logements sans adresse proche : [% \"logements_sans_adresse\" %]\n\n"
        "ENVIRONNEMENT ET RISQUES\n"
        "Natura 2000 : [% format_number(\"natura2000_pct\", 0) %] % · ZNIEFF : [% format_number(\"znieff_pct\", 0) %] %\n"
        "Zone réglementée par un PPRI : [% format_number(\"ppri_pct\", 0) %] % du territoire\n"
        "Monuments historiques : [% \"nb_monuments_historiques\" %]\n\n"
        "ÉQUIPEMENTS ET PATRIMOINE ARBORÉ\n"
        "Établissements scolaires : [% \"nb_etablissements_scolaires\" %] · sport : [% \"nb_equipements_sportifs\" %]\n"
        "Arbres inventoriés : [% \"nb_arbres\" %] (dont [% \"nb_arbres_degrades\" %] dégradés)\n"
    )
    texte(lay, colonne1, 10, 189, 92, 82, 8.5)
    texte(lay, colonne2, 106, 189, 96, 82, 8.5)
    leg = legende(lay, m, [(L["zone"], "Zonage du PLU"), (L["arbre"], "Arbres")], 10, 246, 190,
                  titre="", taille=7)
    leg.setSymbolHeight(3.2)
    leg.setColumnCount(3)
    leg.setSplitLayer(True)
    leg.setLegendFilterByMapEnabled(False)
    texte(lay, SOURCES, 10, 282, 190, 8, 6, "#868e96")
    texte(lay, "Page [% @atlas_featurenumber %] / [% @atlas_totalfeatures %] · Projet de démonstration (étude indépendante)",
          10, 289, 190, 5, 6, "#868e96")
    projet.layoutManager().addLayout(lay)


def exporter(projet):
    CARTES.mkdir(parents=True, exist_ok=True)
    ATLAS.mkdir(parents=True, exist_ok=True)
    for lay in projet.layoutManager().printLayouts():
        exp = QgsLayoutExporter(lay)
        if lay.atlas().enabled():
            pdf = QgsLayoutExporter.PdfExportSettings()
            pdf.dpi = 150
            res, err = QgsLayoutExporter.exportToPdf(lay.atlas(), str(ATLAS / "Atlas_communal.pdf"), pdf)
            log(f"  atlas : {'ok' if res == QgsLayoutExporter.Success else err}")
            continue
        base = lay.name().replace(" ", "_")
        pdf = QgsLayoutExporter.PdfExportSettings()
        pdf.dpi = 200
        # PDF seulement : les aperçus PNG sont tirés des PDF à l'étape 7 (l'export
        # image de QGIS sans interface bloque sur le chargement des tuiles IGN)
        res = exp.exportToPdf(str(CARTES / f"{base}.pdf"), pdf)
        log(f"  {lay.name()} : {'ok' if res == QgsLayoutExporter.Success else res}")


# =============================================================================
# Projet QField (saisie terrain)
# =============================================================================
def projet_qfield():
    chemin = PROJETS / "qfield" / "inventaire_arbres.qgz"
    log(f"Projet QField {chemin.name}")
    projet = QgsProject.instance()
    projet.clear()
    projet.setCrs(CRS)
    projet.setTitle("Inventaire du patrimoine arboré - saisie terrain")
    projet.writeEntry("Paths", "/Absolute", False)
    src = Source("gpkg", GPKG_QFIELD)
    racine = projet.layerTreeRoot()
    g_saisie = racine.addGroup("Saisie")
    g_fond = racine.addGroup("Repères")
    g_listes = racine.addGroup("Listes de valeurs")
    g_img = racine.addGroup("Fonds de plan")

    arbre = ajouter(projet, g_saisie, src.couche("arbre", "Arbres"), True, replie=False)
    style_arbres(arbre)
    inter = ajouter(projet, g_saisie, src.couche("intervention", "Interventions"), True)
    adr = ajouter(projet, g_fond, src.couche("adresse", "Adresses"), True)
    adr.setRenderer(QgsRuleBasedRenderer(point("#5f3dc4", 1.4)))
    etiquettes(adr, "\"numero\" || coalesce(\"rep\", '')", 7, "#5f3dc4", echelle_max=2000)
    visible_sous(adr, 5000)
    parc = ajouter(projet, g_fond, src.couche("parcelle", "Parcelles"), True)
    parc.setRenderer(QgsRuleBasedRenderer(remplissage("transparent", "#e9ecef", 0.25)))
    visible_sous(parc, 5000)
    bat = ajouter(projet, g_fond, src.couche("batiment", "Bâtiments"), False)
    bat.setRenderer(QgsRuleBasedRenderer(remplissage("#d9cfc4", "#a89a8c", 0.1)))
    route = ajouter(projet, g_fond, src.couche("troncon_route", "Voirie"), False)
    route.setRenderer(QgsRuleBasedRenderer(ligne("#adb5bd", 0.3)))
    com = ajouter(projet, g_fond, src.couche("commune", "Communes"), True)
    com.setRenderer(QgsRuleBasedRenderer(remplissage("transparent", "#ffffff", 0.8, "dash")))
    for lyr in (adr, parc, bat, route, com):
        lyr.setReadOnly(True)
        lyr.setCustomProperty("QFieldSync/action", "copy")
    titres_listes = {"liste_essence": "Listes - essences", "liste_etat_sanitaire": "Listes - états sanitaires",
                     "liste_stade_dev": "Listes - stades", "liste_implantation": "Listes - implantations",
                     "liste_risque": "Listes - risques", "liste_type_intervention": "Listes - types d'intervention"}
    listes = {}
    for nom, t in titres_listes.items():
        listes[nom] = ajouter(projet, g_listes, src.couche(nom, t), False)
        listes[nom].setReadOnly(True)
    for lyr in (arbre, inter):
        lyr.setCustomProperty("QFieldSync/action", "offline")
    ortho = ajouter(projet, g_img, xyz("ORTHOIMAGERY.ORTHOPHOTOS", "Photographies aériennes (IGN)", "image/jpeg"), True)
    ajouter(projet, g_img, xyz("GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2", "Plan IGN"), False)
    ortho.setOpacity(0.9)
    configurer_saisie(projet, arbre, inter, listes, com)
    g_listes.setExpanded(False)
    # accrochage sur les arbres existants pour éviter les doublons
    snap = projet.snappingConfig()
    snap.setEnabled(True)
    snap.setMode(Qgis.SnappingMode.AllLayers if hasattr(Qgis, "SnappingMode") else 2)
    snap.setTolerance(8)
    projet.setSnappingConfig(snap)
    emprise = QgsRectangle()
    for f in arbre.getFeatures():
        emprise.combineExtentWith(f.geometry().boundingBox())
    emprise.grow(150)
    from qgis.core import QgsReferencedRectangle
    projet.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(emprise, CRS))
    if not projet.write(str(chemin)):
        raise RuntimeError(f"Écriture impossible : {chemin}")


def main():
    projet, _ = projet_consultation(Source("gpkg", GPKG), PROJETS / "sig_ccst.qgz",
                                    "SIG intercommunal - CC de Sélestat (GeoPackage)")
    if os.environ.get("SANS_EXPORT") != "1":
        log("Export des planches et de l'atlas")
        exporter(projet)
    try:
        projet_consultation(Source("postgis"), config.QGIS_DIR / "sig_ccst_postgis.qgz",
                            "SIG intercommunal - CC de Sélestat (PostGIS)")
    except RuntimeError as err:  # instance PostgreSQL arrêtée : le projet PostGIS est sauté
        log(f"Projet PostGIS non généré : {err}")
    projet_qfield()
    log("Terminé")


if __name__ == "__main__":
    main()
    app.exitQgis()
