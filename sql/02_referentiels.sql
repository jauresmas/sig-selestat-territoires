-- =============================================================================
-- Socle SIG intercommunal - 02. Intégrité des référentiels
-- Exécuté après chaque chargement des référentiels (scripts/01_base_postgis.py).
-- Clés primaires et index spatiaux sont posés par le script de chargement ;
-- ce fichier ajoute les relations entre tables et les index de recherche.
-- =============================================================================

-- Relations : chaque objet est rattaché à une commune du territoire
ALTER TABLE ref_cadastre.parcelle
    ADD CONSTRAINT parcelle_commune_fk FOREIGN KEY (code_insee)
    REFERENCES ref_admin.commune (code_insee);
ALTER TABLE ref_adresse.adresse
    ADD CONSTRAINT adresse_commune_fk FOREIGN KEY (code_insee)
    REFERENCES ref_admin.commune (code_insee);
ALTER TABLE urbanisme.doc_urba
    ADD CONSTRAINT doc_urba_commune_fk FOREIGN KEY (code_insee)
    REFERENCES ref_admin.commune (code_insee);
ALTER TABLE urbanisme.zone_urba
    ADD CONSTRAINT zone_urba_doc_fk FOREIGN KEY (code_insee)
    REFERENCES urbanisme.doc_urba (code_insee);

-- Contrôles de domaine sur les référentiels (standard CNIG)
ALTER TABLE urbanisme.zone_urba
    ADD CONSTRAINT zone_urba_typezone_ck
    CHECK (typezone IN ('U', 'AUc', 'AUs', 'A', 'N', 'Nh', 'Ah'));

-- Index attributaires pour les recherches courantes
CREATE INDEX IF NOT EXISTS parcelle_code_insee_idx ON ref_cadastre.parcelle (code_insee);
CREATE INDEX IF NOT EXISTS parcelle_section_idx    ON ref_cadastre.parcelle (code_insee, section, numero);
CREATE INDEX IF NOT EXISTS adresse_code_insee_idx  ON ref_adresse.adresse (code_insee);
CREATE INDEX IF NOT EXISTS adresse_voie_trgm_idx   ON ref_adresse.adresse
    USING gin (lower(nom_voie) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS zone_urba_code_insee_idx ON urbanisme.zone_urba (code_insee);
CREATE INDEX IF NOT EXISTS batiment_usage_idx      ON ref_topo.batiment (usage_1);

-- Recherche d'adresse tolérante aux fautes : utilisée par QGIS (localisateur)
-- et par les agents ("rue du marechal foch" retrouve "Rue du Maréchal Foch")
CREATE OR REPLACE FUNCTION ref_adresse.rechercher(p_texte text, p_limite int DEFAULT 10)
RETURNS TABLE (cle_interop text, adresse text, commune text, score real, geom geometry)
LANGUAGE sql STABLE AS $$
    SELECT a.cle_interop,
           concat_ws(' ', a.numero::text || coalesce(a.rep, ''), a.nom_voie) AS adresse,
           a.nom_commune,
           similarity(lower(unaccent(concat_ws(' ', a.numero, a.nom_voie, a.nom_commune))),
                      lower(unaccent(p_texte))) AS score,
           a.geom
    FROM ref_adresse.adresse a
    WHERE lower(unaccent(concat_ws(' ', a.numero, a.nom_voie, a.nom_commune)))
          % lower(unaccent(p_texte))
    ORDER BY score DESC
    LIMIT p_limite
$$;
COMMENT ON FUNCTION ref_adresse.rechercher(text, int) IS
    'Recherche approchée d''adresse (trigrammes, sans accents). Exemple : SELECT * FROM ref_adresse.rechercher(''9 place d armes selestat'')';

-- Nomenclature nationale des servitudes d'utilité publique (catégories présentes
-- ou fréquentes en Alsace) : donne un libellé lisible aux codes du GPU
DROP TABLE IF EXISTS servitudes.categorie_sup;
CREATE TABLE servitudes.categorie_sup (
    code    text PRIMARY KEY,
    libelle text NOT NULL,
    famille text NOT NULL
);
INSERT INTO servitudes.categorie_sup VALUES
    ('AC1', 'Monuments historiques (abords et immeubles protégés)', 'Patrimoine culturel'),
    ('AC2', 'Sites inscrits et classés',                            'Patrimoine culturel'),
    ('AC3', 'Réserves naturelles',                                  'Patrimoine naturel'),
    ('AC4', 'Sites patrimoniaux remarquables',                      'Patrimoine culturel'),
    ('AS1', 'Périmètres de protection des captages d''eau potable',  'Salubrité et sécurité publiques'),
    ('A4',  'Passage dans le lit ou sur les berges de cours d''eau non domaniaux', 'Ressources naturelles'),
    ('A5',  'Canalisations publiques d''eau et d''assainissement',   'Ressources naturelles'),
    ('EL7', 'Alignement des voies publiques',                       'Équipement'),
    ('I3',  'Canalisations de transport de gaz',                    'Énergie'),
    ('I4',  'Lignes électriques',                                   'Énergie'),
    ('I1',  'Canalisations de transport d''hydrocarbures',           'Énergie'),
    ('PM1', 'Plans de prévention des risques naturels (PPRN)',      'Salubrité et sécurité publiques'),
    ('PM2', 'Installations classées et sites de stockage de déchets', 'Salubrité et sécurité publiques'),
    ('PM3', 'Plans de prévention des risques technologiques (PPRT)', 'Salubrité et sécurité publiques'),
    ('PT1', 'Protection des centres radioélectriques contre les perturbations', 'Télécommunications'),
    ('PT2', 'Protection des transmissions radioélectriques contre les obstacles', 'Télécommunications'),
    ('T1',  'Voies ferrées',                                        'Transport'),
    ('T5',  'Servitudes aéronautiques de dégagement',               'Transport'),
    ('T7',  'Servitudes aéronautiques hors dégagement',             'Transport');
COMMENT ON TABLE servitudes.categorie_sup IS 'Nomenclature des catégories de servitudes d''utilité publique';

-- Libellé lisible d'une servitude : "PM1_PPRI_Giessen_Selestat_ass" -> "PPRI Giessen Selestat"
CREATE OR REPLACE FUNCTION servitudes.nom_lisible(p_nom text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT trim(replace(regexp_replace(p_nom, '^[A-Za-z0-9]+_|_(ass|abor|gen|per|pro)$', '', 'g'),
                        '_', ' '))
$$;

-- Vues de consultation des servitudes, avec libellés
CREATE OR REPLACE VIEW servitudes.v_assiette_s AS
SELECT s.gid, s.suptype, k.libelle AS categorie_libelle, k.famille,
       servitudes.nom_lisible(coalesce(nullif(s.nomsuplitt, ''), s.nomass)) AS objet,
       s.typeass, s.modegeoass, s.idgen, s.fichier, s.geom
FROM servitudes.sup_assiette_s s
LEFT JOIN servitudes.categorie_sup k ON k.code = s.suptype;

CREATE OR REPLACE VIEW servitudes.v_generateur_s AS
SELECT g.gid, g.suptype, k.libelle AS categorie_libelle,
       servitudes.nom_lisible(g.nomgen) AS objet, g.typegen, g.idgen, g.geom
FROM servitudes.sup_generateur_s g
LEFT JOIN servitudes.categorie_sup k ON k.code = g.suptype;

-- Nomenclatures CNIG des prescriptions et informations des PLU (codes présents
-- sur le territoire) : libellés communs à toutes les communes
DROP TABLE IF EXISTS urbanisme.type_prescription;
CREATE TABLE urbanisme.type_prescription (code text PRIMARY KEY, libelle text NOT NULL);
INSERT INTO urbanisme.type_prescription VALUES
    ('01', 'Espace boisé classé'),
    ('02', 'Secteur de risques ou de nuisances (constructibilité limitée)'),
    ('03', 'Secteur de mixité sociale'),
    ('05', 'Emplacement réservé'),
    ('07', 'Patrimoine bâti ou paysager à protéger'),
    ('15', 'Règle d''implantation (marge de recul)'),
    ('16', 'Bâtiment pouvant changer de destination, STECAL'),
    ('18', 'Orientation d''aménagement et de programmation (OAP)'),
    ('19', 'Secteur protégé pour la richesse du sol ou du sous-sol'),
    ('22', 'Diversité commerciale à préserver'),
    ('24', 'Cheminement piéton ou cyclable à conserver'),
    ('99', 'Autre prescription');

DROP TABLE IF EXISTS urbanisme.type_information;
CREATE TABLE urbanisme.type_information (code text PRIMARY KEY, libelle text NOT NULL);
INSERT INTO urbanisme.type_information VALUES
    ('02', 'Zone d''aménagement concerté (ZAC)'),
    ('03', 'Espace naturel sensible'),
    ('04', 'Droit de préemption urbain'),
    ('12', 'Périmètre d''études (sursis à statuer)'),
    ('14', 'Secteur affecté par le bruit des infrastructures'),
    ('19', 'Zonage d''assainissement et réseaux'),
    ('20', 'Règlement local de publicité'),
    ('25', 'Secteur de protection contre les nuisances'),
    ('30', 'Projet urbain partenarial'),
    ('32', 'Secteur de taxe d''aménagement'),
    ('37', 'Forêt relevant du régime forestier'),
    ('38', 'Secteur d''information sur les sols (SIS)'),
    ('42', 'Clôtures, démolitions ou ravalements soumis à autorisation'),
    ('99', 'Autre information');
