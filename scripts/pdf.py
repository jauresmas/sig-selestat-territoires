"""Mise en forme commune des documents PDF (reportlab) : polices, styles, gabarits."""
from datetime import date
from pathlib import Path

import matplotlib
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Table, TableStyle)

import config
from outils import log

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
        "octobre", "novembre", "décembre"]
AUJOURDHUI = f"{MOIS[date.today().month - 1]} {date.today().year}"
VERSION = "1.0"
ACCENT = colors.HexColor("#1f4e5a")
ACCENT_PALE = colors.HexColor("#d9e8eb")
GRIS = colors.HexColor("#4f5a60")
GRIS_CLAIR = colors.HexColor("#e2e6e8")
FOND = colors.HexColor("#f4f6f6")
ALERTE_PALE = colors.HexColor("#fff4e0")


def polices():
    win = Path("C:/Windows/Fonts")
    if (win / "segoeui.ttf").exists():
        fichiers = (win / "segoeui.ttf", win / "segoeuib.ttf", win / "segoeuii.ttf")
    else:  # repli multiplateforme : DejaVu, livrée avec matplotlib
        d = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        fichiers = (d / "DejaVuSans.ttf", d / "DejaVuSans-Bold.ttf", d / "DejaVuSans-Oblique.ttf")
    for nom, f in zip(("Texte", "Texte-Gras", "Texte-Italique"), fichiers):
        pdfmetrics.registerFont(TTFont(nom, str(f)))
    pdfmetrics.registerFontFamily("Texte", normal="Texte", bold="Texte-Gras", italic="Texte-Italique",
                                  boldItalic="Texte-Gras")


polices()
ST = {
    "corps": ParagraphStyle("corps", fontName="Texte", fontSize=9.5, leading=14.2, alignment=TA_JUSTIFY,
                            spaceAfter=6, textColor=colors.HexColor("#1d2327")),
    "h1": ParagraphStyle("h1", fontName="Texte-Gras", fontSize=15, leading=19, textColor=ACCENT,
                         spaceBefore=4, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Texte-Gras", fontSize=11, leading=14, textColor=colors.black,
                         spaceBefore=8, spaceAfter=5),
    "puce": ParagraphStyle("puce", fontName="Texte", fontSize=9.5, leading=14, leftIndent=12,
                           bulletIndent=2, spaceAfter=2),
    "etape": ParagraphStyle("etape", fontName="Texte", fontSize=9.5, leading=14, leftIndent=18,
                            bulletIndent=0, spaceAfter=4),
    "legende": ParagraphStyle("legende", fontName="Texte-Italique", fontSize=8, leading=10.5,
                              textColor=GRIS, spaceBefore=3, spaceAfter=10),
    "cellule": ParagraphStyle("cellule", fontName="Texte", fontSize=8.3, leading=10.8),
    "cellule_g": ParagraphStyle("cellule_g", fontName="Texte-Gras", fontSize=8.3, leading=10.8,
                                textColor=colors.white),
    "encadre": ParagraphStyle("encadre", fontName="Texte", fontSize=9.3, leading=13.5),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8.2, leading=10.8, backColor=FOND,
                           borderPadding=6, leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=8),
}


def P(texte, style="corps"):
    return Paragraph(texte, ST[style])


def puces(items):
    return [Paragraph(t, ST["puce"], bulletText="•") for t in items]


def etapes(items):
    return [Paragraph(t, ST["etape"], bulletText=f"{i}.") for i, t in enumerate(items, start=1)]


def code(texte):
    return Paragraph(texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                     .replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), ST["code"])


def tableau(lignes, largeurs, entete=True):
    data = [[Paragraph(str(c), ST["cellule_g" if (entete and i == 0) else "cellule"]) for c in ligne]
            for i, ligne in enumerate(lignes)]
    t = Table(data, colWidths=largeurs, repeatRows=1 if entete else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LINEBELOW", (0, 0), (-1, -1), 0.4, GRIS_CLAIR),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if entete:
        style.append(("BACKGROUND", (0, 0), (-1, 0), ACCENT))
    t.setStyle(TableStyle(style))
    return t


def encadre(texte, couleur=ACCENT_PALE, largeur=17 * cm):
    t = Table([[Paragraph(texte, ST["encadre"])]], colWidths=[largeur])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), couleur),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def figure(chemin_png, legende, largeur=17 * cm, max_hauteur=None):
    """Insère une vignette JPEG allégée (1 800 px) de la figure."""
    vignettes = config.INTERIM / "vignettes"
    vignettes.mkdir(parents=True, exist_ok=True)
    cible = vignettes / (Path(chemin_png).stem + ".jpg")
    with PILImage.open(chemin_png) as im:
        im = im.convert("RGB")
        im.thumbnail((1800, 1800))
        im.save(cible, quality=86, optimize=True)
        w, h = im.size
    hauteur = largeur * h / w
    if max_hauteur and hauteur > max_hauteur:
        largeur, hauteur = largeur * max_hauteur / hauteur, max_hauteur
    return KeepTogether([Image(str(cible), width=largeur, height=hauteur), P(legende, "legende")])


def gabarit(titre_doc):
    def pages(canv, doc):
        canv.saveState()
        canv.setStrokeColor(GRIS_CLAIR)
        canv.setLineWidth(0.5)
        canv.line(2 * cm, A4[1] - 1.4 * cm, A4[0] - 2 * cm, A4[1] - 1.4 * cm)
        canv.setFont("Texte", 7.5)
        canv.setFillColor(GRIS)
        canv.drawString(2 * cm, A4[1] - 1.2 * cm, titre_doc)
        canv.drawRightString(A4[0] - 2 * cm, A4[1] - 1.2 * cm, f"{config.EPCI_NOM} · v{VERSION}")
        canv.line(2 * cm, 1.4 * cm, A4[0] - 2 * cm, 1.4 * cm)
        canv.drawString(2 * cm, 1.0 * cm,
                        f"{config.AUTEUR} · {AUJOURDHUI} · projet de démonstration, document non officiel")
        canv.drawRightString(A4[0] - 2 * cm, 1.0 * cm, f"{doc.page}")
        canv.restoreState()
    return pages


def couverture(surtitre, titre, sous_titre, lignes):
    def dessiner(canv, doc):
        canv.saveState()
        canv.setFillColor(ACCENT)
        canv.rect(0, A4[1] * 0.42, A4[0], A4[1] * 0.58, fill=1, stroke=0)
        canv.setFillColor(colors.white)
        canv.setFont("Texte", 11)
        canv.drawString(2.2 * cm, A4[1] - 3.2 * cm, surtitre.upper())
        canv.setFont("Texte-Gras", 27)
        y = A4[1] - 7 * cm
        for ligne in titre.split("\n"):
            canv.drawString(2.2 * cm, y, ligne)
            y -= 1.15 * cm
        canv.setFillColor(ACCENT_PALE)
        canv.setFont("Texte", 13)
        canv.drawString(2.2 * cm, y - 0.4 * cm, sous_titre)
        canv.setFont("Texte", 10.5)
        y = A4[1] * 0.42 - 1.8 * cm
        for lib, val in lignes:
            canv.setFillColor(GRIS)
            canv.drawString(2.2 * cm, y, lib)
            canv.setFillColor(colors.black)
            canv.drawString(7.2 * cm, y, val)
            y -= 0.75 * cm
        canv.setFont("Texte-Italique", 8.5)
        canv.setFillColor(GRIS)
        canv.drawString(2.2 * cm, 2.2 * cm, "Projet de démonstration réalisé à partir de données ouvertes. "
                                            "Ce document n'engage ni la Ville ni la communauté de communes.")
        canv.restoreState()
    return dessiner


def construire(chemin, titre_doc, couv, histoire, sujet=None):
    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm, title=titre_doc,
                            author=config.AUTEUR, subject=sujet or f"SIG intercommunal - {config.EPCI_NOM}")
    if couv:
        doc.build([PageBreak()] + histoire, onFirstPage=couv, onLaterPages=gabarit(titre_doc))
    else:
        doc.build(histoire, onFirstPage=gabarit(titre_doc), onLaterPages=gabarit(titre_doc))
    log(f"  {Path(chemin).name}")
