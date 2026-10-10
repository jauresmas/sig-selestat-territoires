"""Étape 4 - Métadonnées : fiches ISO 19139, dictionnaire des données, catalogue.

À partir de la table metadonnees.fiche (alimentée par le catalogue) :
  - une fiche XML ISO 19115/19139 par jeu de données, conforme au profil
    INSPIRE : moissonnable par un catalogue GeoNetwork (GéoGrandEst, CIGAL...)
  - le dictionnaire des données (une ligne par champ, avec les commentaires
    posés dans la base à l'étape 1)
  - le catalogue de la carte web (JSON)
"""
import json
from datetime import date

import pandas as pd
from jinja2 import Template

import config
from outils import log, pg_lire

# Thème INSPIRE -> catégorie ISO 19115 (MD_TopicCategoryCode)
CATEGORIES_ISO = {
    "Unités administratives": "boundaries",
    "Parcelles cadastrales": "planningCadastre",
    "Adresses": "location",
    "Bâtiments": "structure",
    "Réseaux de transport": "transportation",
    "Hydrographie": "inlandWaters",
    "Services d'utilité publique et services publics": "utilitiesCommunication",
    "Usage des sols": "planningCadastre",
    "Zones de gestion, de restriction ou de réglementation et unités de déclaration": "planningCadastre",
    "Sites protégés": "environment",
    "Répartition des espèces": "biota",
}

TEMPLATE = Template("""<?xml version="1.0" encoding="UTF-8"?>
<gmd:MD_Metadata xmlns:gmd="http://www.isotc211.org/2005/gmd" xmlns:gco="http://www.isotc211.org/2005/gco"
  xmlns:gml="http://www.opengis.net/gml" xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <gmd:fileIdentifier><gco:CharacterString>{{ f.identifiant }}</gco:CharacterString></gmd:fileIdentifier>
  <gmd:language><gmd:LanguageCode codeList="http://www.loc.gov/standards/iso639-2/" codeListValue="fre">fre</gmd:LanguageCode></gmd:language>
  <gmd:characterSet><gmd:MD_CharacterSetCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#MD_CharacterSetCode" codeListValue="utf8"/></gmd:characterSet>
  <gmd:hierarchyLevel><gmd:MD_ScopeCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#MD_ScopeCode" codeListValue="dataset"/></gmd:hierarchyLevel>
  <gmd:contact>{{ contact("pointOfContact") }}</gmd:contact>
  <gmd:dateStamp><gco:Date>{{ aujourdhui }}</gco:Date></gmd:dateStamp>
  <gmd:metadataStandardName><gco:CharacterString>ISO 19115:2003/19139</gco:CharacterString></gmd:metadataStandardName>
  <gmd:metadataStandardVersion><gco:CharacterString>1.0</gco:CharacterString></gmd:metadataStandardVersion>
  <gmd:referenceSystemInfo><gmd:MD_ReferenceSystem><gmd:referenceSystemIdentifier><gmd:RS_Identifier>
    <gmd:code><gco:CharacterString>EPSG:2154</gco:CharacterString></gmd:code>
    <gmd:codeSpace><gco:CharacterString>EPSG</gco:CharacterString></gmd:codeSpace>
  </gmd:RS_Identifier></gmd:referenceSystemIdentifier></gmd:MD_ReferenceSystem></gmd:referenceSystemInfo>
  <gmd:identificationInfo><gmd:MD_DataIdentification>
    <gmd:citation><gmd:CI_Citation>
      <gmd:title><gco:CharacterString>{{ f.titre|e }} - {{ territoire|e }}</gco:CharacterString></gmd:title>
      <gmd:date><gmd:CI_Date><gmd:date><gco:Date>{{ f.date_integration }}</gco:Date></gmd:date>
        <gmd:dateType><gmd:CI_DateTypeCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#CI_DateTypeCode" codeListValue="revision"/></gmd:dateType>
      </gmd:CI_Date></gmd:date>
      <gmd:identifier><gmd:MD_Identifier><gmd:code><gco:CharacterString>{{ f.table_nom }}</gco:CharacterString></gmd:code></gmd:MD_Identifier></gmd:identifier>
    </gmd:CI_Citation></gmd:citation>
    <gmd:abstract><gco:CharacterString>{{ f.resume|e }}</gco:CharacterString></gmd:abstract>
    <gmd:pointOfContact>{{ contact("custodian") }}</gmd:pointOfContact>
    <gmd:pointOfContact><gmd:CI_ResponsibleParty>
      <gmd:organisationName><gco:CharacterString>{{ f.producteur|e }}</gco:CharacterString></gmd:organisationName>
      <gmd:role><gmd:CI_RoleCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#CI_RoleCode" codeListValue="originator"/></gmd:role>
    </gmd:CI_ResponsibleParty></gmd:pointOfContact>
    <gmd:resourceMaintenance><gmd:MD_MaintenanceInformation>
      <gmd:maintenanceAndUpdateFrequency><gmd:MD_MaintenanceFrequencyCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#MD_MaintenanceFrequencyCode" codeListValue="{{ frequence }}"/></gmd:maintenanceAndUpdateFrequency>
      <gmd:maintenanceNote><gco:CharacterString>Mise à jour : {{ f.frequence_maj|e }}</gco:CharacterString></gmd:maintenanceNote>
    </gmd:MD_MaintenanceInformation></gmd:resourceMaintenance>
    {% if f.theme_inspire %}<gmd:descriptiveKeywords><gmd:MD_Keywords>
      <gmd:keyword><gco:CharacterString>{{ f.theme_inspire|e }}</gco:CharacterString></gmd:keyword>
      <gmd:thesaurusName><gmd:CI_Citation>
        <gmd:title><gco:CharacterString>GEMET - INSPIRE themes, version 1.0</gco:CharacterString></gmd:title>
        <gmd:date><gmd:CI_Date><gmd:date><gco:Date>2008-06-01</gco:Date></gmd:date>
          <gmd:dateType><gmd:CI_DateTypeCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#CI_DateTypeCode" codeListValue="publication"/></gmd:dateType>
        </gmd:CI_Date></gmd:date>
      </gmd:CI_Citation></gmd:thesaurusName>
    </gmd:MD_Keywords></gmd:descriptiveKeywords>{% endif %}
    <gmd:descriptiveKeywords><gmd:MD_Keywords>
      {% for m in mots_cles %}<gmd:keyword><gco:CharacterString>{{ m|e }}</gco:CharacterString></gmd:keyword>
      {% endfor %}<gmd:keyword><gco:CharacterString>{{ territoire|e }}</gco:CharacterString></gmd:keyword>
    </gmd:MD_Keywords></gmd:descriptiveKeywords>
    <gmd:resourceConstraints><gmd:MD_Constraints>
      <gmd:useLimitation><gco:CharacterString>{{ f.licence|e }}</gco:CharacterString></gmd:useLimitation>
    </gmd:MD_Constraints></gmd:resourceConstraints>
    <gmd:resourceConstraints><gmd:MD_LegalConstraints>
      <gmd:accessConstraints><gmd:MD_RestrictionCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#MD_RestrictionCode" codeListValue="otherRestrictions"/></gmd:accessConstraints>
      <gmd:otherConstraints><gco:CharacterString>{{ acces|e }}</gco:CharacterString></gmd:otherConstraints>
    </gmd:MD_LegalConstraints></gmd:resourceConstraints>
    <gmd:spatialRepresentationType><gmd:MD_SpatialRepresentationTypeCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#MD_SpatialRepresentationTypeCode" codeListValue="vector"/></gmd:spatialRepresentationType>
    {% if denominateur %}<gmd:spatialResolution><gmd:MD_Resolution><gmd:equivalentScale><gmd:MD_RepresentativeFraction>
      <gmd:denominator><gco:Integer>{{ denominateur }}</gco:Integer></gmd:denominator>
    </gmd:MD_RepresentativeFraction></gmd:equivalentScale></gmd:MD_Resolution></gmd:spatialResolution>{% endif %}
    <gmd:language><gmd:LanguageCode codeList="http://www.loc.gov/standards/iso639-2/" codeListValue="fre">fre</gmd:LanguageCode></gmd:language>
    <gmd:characterSet><gmd:MD_CharacterSetCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#MD_CharacterSetCode" codeListValue="utf8"/></gmd:characterSet>
    <gmd:topicCategory><gmd:MD_TopicCategoryCode>{{ categorie }}</gmd:MD_TopicCategoryCode></gmd:topicCategory>
    {% if bbox %}<gmd:extent><gmd:EX_Extent><gmd:geographicElement><gmd:EX_GeographicBoundingBox>
      <gmd:westBoundLongitude><gco:Decimal>{{ bbox[0] }}</gco:Decimal></gmd:westBoundLongitude>
      <gmd:eastBoundLongitude><gco:Decimal>{{ bbox[2] }}</gco:Decimal></gmd:eastBoundLongitude>
      <gmd:southBoundLatitude><gco:Decimal>{{ bbox[1] }}</gco:Decimal></gmd:southBoundLatitude>
      <gmd:northBoundLatitude><gco:Decimal>{{ bbox[3] }}</gco:Decimal></gmd:northBoundLatitude>
    </gmd:EX_GeographicBoundingBox></gmd:geographicElement></gmd:EX_Extent></gmd:extent>{% endif %}
  </gmd:MD_DataIdentification></gmd:identificationInfo>
  <gmd:distributionInfo><gmd:MD_Distribution>
    <gmd:distributionFormat><gmd:MD_Format>
      <gmd:name><gco:CharacterString>GeoPackage</gco:CharacterString></gmd:name>
      <gmd:version><gco:CharacterString>1.3</gco:CharacterString></gmd:version>
    </gmd:MD_Format></gmd:distributionFormat>
    <gmd:distributionFormat><gmd:MD_Format>
      <gmd:name><gco:CharacterString>PostgreSQL/PostGIS ({{ f.table_nom }})</gco:CharacterString></gmd:name>
      <gmd:version><gco:CharacterString>PostgreSQL 15 / PostGIS 3.5</gco:CharacterString></gmd:version>
    </gmd:MD_Format></gmd:distributionFormat>
    {% if f.source_url %}<gmd:transferOptions><gmd:MD_DigitalTransferOptions><gmd:onLine><gmd:CI_OnlineResource>
      <gmd:linkage><gmd:URL>{{ f.source_url|e }}</gmd:URL></gmd:linkage>
      <gmd:protocol><gco:CharacterString>WWW:LINK</gco:CharacterString></gmd:protocol>
      <gmd:name><gco:CharacterString>Source des données</gco:CharacterString></gmd:name>
    </gmd:CI_OnlineResource></gmd:onLine></gmd:MD_DigitalTransferOptions></gmd:transferOptions>{% endif %}
  </gmd:MD_Distribution></gmd:distributionInfo>
  <gmd:dataQualityInfo><gmd:DQ_DataQuality>
    <gmd:scope><gmd:DQ_Scope><gmd:level><gmd:MD_ScopeCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#MD_ScopeCode" codeListValue="dataset"/></gmd:level></gmd:DQ_Scope></gmd:scope>
    <gmd:report><gmd:DQ_DomainConsistency><gmd:result><gmd:DQ_ConformanceResult>
      <gmd:specification><gmd:CI_Citation>
        <gmd:title><gco:CharacterString>Règlement (UE) n° 1089/2010 de la Commission du 23 novembre 2010 portant modalités d'application de la directive 2007/2/CE en ce qui concerne l'interopérabilité des séries et des services de données géographiques</gco:CharacterString></gmd:title>
        <gmd:date><gmd:CI_Date><gmd:date><gco:Date>2010-12-08</gco:Date></gmd:date>
          <gmd:dateType><gmd:CI_DateTypeCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#CI_DateTypeCode" codeListValue="publication"/></gmd:dateType>
        </gmd:CI_Date></gmd:date>
      </gmd:CI_Citation></gmd:specification>
      <gmd:explanation><gco:CharacterString>Conformité non évaluée</gco:CharacterString></gmd:explanation>
      <gmd:pass gco:nilReason="unknown"/>
    </gmd:DQ_ConformanceResult></gmd:result></gmd:DQ_DomainConsistency></gmd:report>
    <gmd:lineage><gmd:LI_Lineage><gmd:statement><gco:CharacterString>{{ genealogie|e }}</gco:CharacterString></gmd:statement></gmd:LI_Lineage></gmd:lineage>
  </gmd:DQ_DataQuality></gmd:dataQualityInfo>
</gmd:MD_Metadata>
""")

CONTACT = Template("""<gmd:CI_ResponsibleParty>
      <gmd:individualName><gco:CharacterString>{{ auteur|e }}</gco:CharacterString></gmd:individualName>
      <gmd:organisationName><gco:CharacterString>SIG intercommunal - projet de démonstration (étude indépendante)</gco:CharacterString></gmd:organisationName>
      <gmd:contactInfo><gmd:CI_Contact><gmd:onlineResource><gmd:CI_OnlineResource>
        <gmd:linkage><gmd:URL>{{ url }}</gmd:URL></gmd:linkage>
      </gmd:CI_OnlineResource></gmd:onlineResource></gmd:CI_Contact></gmd:contactInfo>
      <gmd:role><gmd:CI_RoleCode codeList="http://standards.iso.org/iso/19139/resources/gmxCodelists.xml#CI_RoleCode" codeListValue="{{ role }}"/></gmd:role>
    </gmd:CI_ResponsibleParty>""")


def frequence_iso(texte):
    t = (texte or "").lower()
    for cle, code in (("continue", "continual"), ("quotid", "daily"), ("hebdo", "weekly"),
                      ("trimes", "quarterly"), ("semes", "biannually"), ("annu", "annually"),
                      ("procédure", "asNeeded")):
        if cle in t:
            return code
    return "unknown"


def genealogie(f):
    base = (f"Données intégrées le {f['date_integration']} dans la base PostgreSQL/PostGIS "
            f"intercommunale (table {f['table_nom']}) par la chaîne de traitement "
            "scripts/run_all.py : interrogation du flux de diffusion officiel, sélection sur le "
            "territoire, reprojection en Lambert-93, normalisation des noms de champs, contrôle "
            "des géométries et des doublons.")
    if f["table_nom"].startswith("espaces_verts"):
        base = ("Positions des arbres issues d'OpenStreetMap (© contributeurs OpenStreetMap, "
                "ODbL). Attributs (essence lorsque OSM ne la renseigne pas, dimensions, état "
                "sanitaire, interventions) simulés de façon reproductible pour la démonstration. "
                "Mises à jour prévues par saisie terrain avec QField, règles de gestion "
                "appliquées par déclencheurs PostgreSQL.")
    return base + (f" Source : {f['source_url']}." if f["source_url"] else "")


def dictionnaire():
    return pg_lire("""
        SELECT c.table_schema || '.' || c.table_name AS table_nom, c.ordinal_position AS ordre,
               c.column_name AS champ,
               CASE WHEN c.data_type = 'USER-DEFINED' THEN c.udt_name ELSE c.data_type END AS type,
               c.is_nullable = 'NO' AS obligatoire,
               col_description((quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass,
                               c.ordinal_position) AS description
        FROM information_schema.columns c
        JOIN metadonnees.fiche f ON f.table_nom = c.table_schema || '.' || c.table_name
        ORDER BY 1, 2""", geom=None)


def main():
    dossier = config.LIVRABLES / "05_Metadonnees"
    xml_dir = dossier / "iso19139"
    xml_dir.mkdir(parents=True, exist_ok=True)
    fiches = pg_lire("""SELECT f.*, ST_Transform(f.emprise, 4326) AS bbox4326
                        FROM metadonnees.fiche f ORDER BY table_nom""", geom="bbox4326")
    log(f"Fiches ISO 19139 : {len(fiches)}")
    territoire = config.EPCI_NOM
    for _, f in fiches.iterrows():
        bbox = None if f["bbox4326"] is None else [round(v, 5) for v in f["bbox4326"].bounds]
        acces = ("Pas de restriction d'accès public" if f["niveau_diffusion"] == "ouverte"
                 else f"Accès {f['niveau_diffusion']} : {f['motif_restriction']}")
        echelle = (f["echelle"] or "").replace(" ", "").replace(" ", "")
        denom = echelle.split(":")[1] if ":" in echelle else None
        xml = TEMPLATE.render(
            f=f, territoire=territoire, aujourdhui=date.today().isoformat(),
            contact=lambda role: CONTACT.render(auteur=config.AUTEUR, url=config.CONTACT_URL, role=role),
            frequence=frequence_iso(f["frequence_maj"]), mots_cles=list(f["mots_cles"] or []),
            acces=acces, denominateur=denom, bbox=bbox, genealogie=genealogie(f),
            categorie=CATEGORIES_ISO.get(f["theme_inspire"], "planningCadastre"))
        (xml_dir / f"{f['table_nom'].replace('.', '__')}.xml").write_text(xml, encoding="utf-8")

    cat = pd.DataFrame(fiches.drop(columns=["emprise", "bbox4326"]))
    cat["mots_cles"] = cat["mots_cles"].map(lambda m: "; ".join(m or []))
    cat["identifiant"] = cat["identifiant"].astype(str)
    cat.to_csv(dossier / "catalogue_des_donnees.csv", index=False, sep=";", encoding="utf-8-sig")
    dico = dictionnaire()
    dico.to_csv(dossier / "dictionnaire_des_donnees.csv", index=False, sep=";", encoding="utf-8-sig")
    log(f"  dictionnaire : {len(dico)} champs, dont {dico['description'].notna().sum()} décrits")

    web = cat[["identifiant", "table_nom", "titre", "resume", "theme_inspire", "producteur",
               "licence", "niveau_diffusion", "motif_restriction", "millesime",
               "frequence_maj", "nb_objets", "source_url"]].copy()
    web["identifiant"] = web["identifiant"].astype(str)
    web["date_integration"] = cat["date_integration"].astype(str)
    (config.DOCS / "data").mkdir(parents=True, exist_ok=True)
    (config.DOCS / "data" / "catalogue.json").write_text(
        json.dumps(web.where(web.notna(), None).to_dict("records"), ensure_ascii=False, indent=1),
        encoding="utf-8")
    log(f"  -> {dossier.relative_to(config.ROOT)} et docs/data/catalogue.json")


if __name__ == "__main__":
    main()
