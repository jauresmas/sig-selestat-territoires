"""Étape 6 bis - Captures du projet QGIS pour la documentation (PyQGIS, sans écran).

Rend le formulaire de saisie d'un arbre (tel qu'il s'affiche dans QGIS et QField)
et une vue de carte du projet, pour les fiches tutoriel et le README.
"""
import faulthandler
import os
import sys
from pathlib import Path

faulthandler.enable()
sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402

from qgis.core import (QgsApplication, QgsFeatureRequest, QgsMapRendererParallelJob,  # noqa: E402
                       QgsMapSettings, QgsProject, QgsRectangle)
from qgis.gui import QgsAttributeEditorContext, QgsAttributeForm, QgsGui  # noqa: E402
from qgis.PyQt.QtCore import QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402

FORMULAIRES = os.environ.get("CAPTURE_FORMULAIRES") == "1"  # nécessite une session graphique
app = QgsApplication([], FORMULAIRES)
app.initQgis()
if FORMULAIRES:
    QgsGui.editorWidgetRegistry().initEditors()  # widgets des formulaires
IMG = config.DOCS / "img"
IMG.mkdir(parents=True, exist_ok=True)


def formulaire(arbre, onglet, fichier, taille=(560, 640)):
    req = QgsFeatureRequest().setFilterExpression(
        "\"etat_sanitaire\" = 'deperissant' AND \"code_insee\" = '67462' AND \"observations\" IS NOT NULL")
    f = next(arbre.getFeatures(req))
    form = QgsAttributeForm(arbre, f, QgsAttributeEditorContext())
    form.resize(*taille)
    from qgis.PyQt.QtWidgets import QTabWidget
    for tabs in form.findChildren(QTabWidget):
        for i in range(tabs.count()):
            if tabs.tabText(i) == onglet:
                tabs.setCurrentIndex(i)
    form.show()
    app.processEvents()
    form.grab().save(str(IMG / fichier))
    form.close()
    print(f"[captures] {fichier}")


def vue(projet, theme, emprise, fichier, taille=(1400, 900)):
    ms = QgsMapSettings()
    ms.setLayers(projet.mapThemeCollection().mapThemeVisibleLayers(theme))
    ms.setLayerStyleOverrides(projet.mapThemeCollection().mapThemeStyleOverrides(theme))
    ms.setDestinationCrs(projet.crs())
    ms.setExtent(emprise)
    ms.setOutputSize(QSize(*taille))
    ms.setBackgroundColor(QColor("white"))
    ms.setOutputDpi(110)
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    job.renderedImage().save(str(IMG / fichier))
    print(f"[captures] {fichier}")


def main():
    projet = QgsProject.instance()
    projet.read(str(config.LIVRABLES / "03_Projets_QGIS" / "sig_ccst.qgz"))
    arbre = projet.mapLayersByName("Arbres")[0]
    if FORMULAIRES:
        formulaire(arbre, "État sanitaire", "qgis_formulaire_arbre.png")
        formulaire(arbre, "Interventions", "qgis_formulaire_interventions.png")
    # centre ancien de Sélestat
    vue(projet, "Patrimoine arboré", QgsRectangle(1029450, 6804300, 1030850, 6805200),
        "qgis_patrimoine_arbore.png")
    vue(projet, "Urbanisme détaillé", QgsRectangle(1029450, 6804300, 1030850, 6805200),
        "qgis_urbanisme.png")


if __name__ == "__main__":
    main()
    app.exitQgis()
