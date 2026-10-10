-- =============================================================================
-- Socle SIG intercommunal - 03. Données métier : patrimoine arboré
-- Modèle de saisie partagé par QGIS (bureau) et QField (terrain).
--   - listes de valeurs dans des tables (modifiables sans toucher au code)
--   - identifiants UUID : pas de conflit quand plusieurs agents saisissent
--     hors connexion puis synchronisent
--   - règles de gestion portées par la base (déclencheurs), donc appliquées
--     quel que soit l'outil de saisie
--   - journal de toutes les modifications (qui, quand, avant/après)
-- =============================================================================

SET search_path = espaces_verts, public;

-- -----------------------------------------------------------------------------
-- Listes de valeurs
-- -----------------------------------------------------------------------------
CREATE TABLE liste_etat_sanitaire (
    code     text PRIMARY KEY,
    libelle  text NOT NULL,
    ordre    smallint NOT NULL,
    couleur  text NOT NULL
);
INSERT INTO liste_etat_sanitaire VALUES
    ('bon',         'Bon',                      1, '#2b8a3e'),
    ('moyen',       'Moyen',                    2, '#94c47d'),
    ('surveiller',  'À surveiller',             3, '#f2c94c'),
    ('deperissant', 'Dépérissant',              4, '#e8590c'),
    ('mort',        'Mort ou dangereux',        5, '#a61e4d');

CREATE TABLE liste_stade_dev (
    code    text PRIMARY KEY,
    libelle text NOT NULL,
    ordre   smallint NOT NULL
);
INSERT INTO liste_stade_dev VALUES
    ('jeune',     'Jeune (moins de 10 ans)', 1),
    ('adulte',    'Adulte',                  2),
    ('mature',    'Mature',                  3),
    ('senescent', 'Sénescent',               4);

CREATE TABLE liste_implantation (
    code    text PRIMARY KEY,
    libelle text NOT NULL
);
INSERT INTO liste_implantation VALUES
    ('alignement', 'Alignement de voirie'),
    ('isole',      'Arbre isolé'),
    ('parc',       'Parc, square ou jardin public'),
    ('groupe',     'Groupe ou bosquet'),
    ('equipement', 'Abords d''équipement (école, stade, cimetière)');

CREATE TABLE liste_risque (
    code    text PRIMARY KEY,
    libelle text NOT NULL,
    ordre   smallint NOT NULL
);
INSERT INTO liste_risque VALUES
    ('faible', 'Faible', 1),
    ('modere', 'Modéré', 2),
    ('eleve',  'Élevé',  3);

CREATE TABLE liste_type_intervention (
    code      text PRIMARY KEY,
    libelle   text NOT NULL,
    cout_ref  numeric(8, 2)   -- coût moyen de référence (€ HT), pour les estimations
);
INSERT INTO liste_type_intervention VALUES
    ('diagnostic',  'Diagnostic sanitaire (VTA)',   60),
    ('taille',      'Taille d''entretien',          180),
    ('formation',   'Taille de formation',          90),
    ('elagage',     'Élagage (sécurisation)',       350),
    ('haubanage',   'Haubanage',                    450),
    ('traitement',  'Traitement (lutte biologique)', 120),
    ('abattage',    'Abattage',                     650),
    ('dessouchage', 'Dessouchage',                  250),
    ('plantation',  'Plantation',                   400);

CREATE TABLE liste_essence (
    code           text PRIMARY KEY,   -- nom scientifique
    genre          text NOT NULL,
    nom_francais   text NOT NULL,
    type_feuillage text NOT NULL CHECK (type_feuillage IN ('feuillu', 'conifere')),
    allergisant    boolean NOT NULL DEFAULT false,  -- potentiel allergisant (RNSA)
    envahissante   boolean NOT NULL DEFAULT false   -- espèce exotique envahissante (à ne plus planter)
);
INSERT INTO liste_essence VALUES
    ('Tilia cordata',          'Tilia',      'Tilleul à petites feuilles', 'feuillu', true),
    ('Tilia platyphyllos',     'Tilia',      'Tilleul à grandes feuilles', 'feuillu', true),
    ('Tilia x europaea',       'Tilia',      'Tilleul commun',             'feuillu', true),
    ('Platanus x hispanica',   'Platanus',   'Platane commun',             'feuillu', true),
    ('Acer platanoides',       'Acer',       'Érable plane',               'feuillu', true),
    ('Acer pseudoplatanus',    'Acer',       'Érable sycomore',            'feuillu', true),
    ('Acer campestre',         'Acer',       'Érable champêtre',           'feuillu', true),
    ('Carpinus betulus',       'Carpinus',   'Charme commun',              'feuillu', true),
    ('Fraxinus excelsior',     'Fraxinus',   'Frêne commun',               'feuillu', true),
    ('Aesculus hippocastanum', 'Aesculus',   'Marronnier d''Inde',          'feuillu', false),
    ('Quercus robur',          'Quercus',    'Chêne pédonculé',            'feuillu', true),
    ('Betula pendula',         'Betula',     'Bouleau verruqueux',         'feuillu', true),
    ('Prunus avium',           'Prunus',     'Merisier',                   'feuillu', false),
    ('Prunus serrulata',       'Prunus',     'Cerisier du Japon',          'feuillu', false),
    ('Robinia pseudoacacia',   'Robinia',    'Robinier faux-acacia',       'feuillu', false),
    ('Celtis australis',       'Celtis',     'Micocoulier de Provence',    'feuillu', false),
    ('Sophora japonica',       'Styphnolobium', 'Sophora du Japon',        'feuillu', false),
    ('Liquidambar styraciflua','Liquidambar','Copalme d''Amérique',         'feuillu', false),
    ('Ginkgo biloba',          'Ginkgo',     'Ginkgo',                     'feuillu', false),
    ('Juglans regia',          'Juglans',    'Noyer commun',               'feuillu', false),
    ('Malus domestica',        'Malus',      'Pommier',                    'feuillu', false),
    ('Salix alba',             'Salix',      'Saule blanc',                'feuillu', true),
    ('Populus nigra',          'Populus',    'Peuplier noir',              'feuillu', true),
    ('Pinus nigra',            'Pinus',      'Pin noir',                   'conifere', false),
    ('Pinus sylvestris',       'Pinus',      'Pin sylvestre',              'conifere', false),
    ('Taxus baccata',          'Taxus',      'If commun',                  'conifere', false),
    ('Alnus x spaethii',       'Alnus',      'Aulne de Spaeth',            'feuillu', true),
    ('Fagus sylvatica',        'Fagus',      'Hêtre commun',               'feuillu', true),
    ('Tilia tomentosa',        'Tilia',      'Tilleul argenté',            'feuillu', true),
    ('Magnolia x soulangeana', 'Magnolia',   'Magnolia de Soulange',       'feuillu', false),
    ('Koelreuteria paniculata','Koelreuteria','Savonnier',                 'feuillu', false),
    ('Salix babylonica',       'Salix',      'Saule pleureur',             'feuillu', true),
    ('Paulownia tomentosa',    'Paulownia',  'Paulownia',                  'feuillu', false),
    ('Ailanthus altissima',    'Ailanthus',  'Ailante glanduleux',         'feuillu', false),
    ('Cedrus atlantica',       'Cedrus',     'Cèdre de l''Atlas',           'conifere', false),
    ('Indetermine',            'Indéterminé','Essence à déterminer',       'feuillu', false);

-- Espèces exotiques envahissantes (liste régionale Grand Est) : à signaler, ne plus planter
UPDATE liste_essence SET envahissante = true
WHERE code IN ('Ailanthus altissima', 'Robinia pseudoacacia');

COMMENT ON TABLE liste_essence IS 'Référentiel des essences (nom scientifique, nom français, potentiel allergisant, caractère envahissant)';

-- -----------------------------------------------------------------------------
-- Arbres
-- -----------------------------------------------------------------------------
CREATE SEQUENCE seq_numero_arbre;

CREATE TABLE arbre (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    numero           text UNIQUE,                 -- ARB-<insee>-<n>, attribué par la base
    code_insee       text REFERENCES ref_admin.commune (code_insee),
    essence          text NOT NULL DEFAULT 'Indetermine' REFERENCES liste_essence (code),
    implantation     text REFERENCES liste_implantation (code),
    stade_dev        text REFERENCES liste_stade_dev (code),
    hauteur_m        numeric(4, 1) CHECK (hauteur_m BETWEEN 0.5 AND 50),
    circonference_cm integer CHECK (circonference_cm BETWEEN 5 AND 1500),
    annee_plantation integer CHECK (annee_plantation BETWEEN 1700 AND 2100),
    etat_sanitaire   text REFERENCES liste_etat_sanitaire (code),
    risque           text REFERENCES liste_risque (code),
    remarquable      boolean NOT NULL DEFAULT false,
    date_diagnostic  date,
    statut           text NOT NULL DEFAULT 'en_place'
                     CHECK (statut IN ('en_place', 'abattu', 'a_planter')),
    observations     text,
    photo            text,                         -- chemin relatif (DCIM/...)
    precision_m      numeric(5, 2),               -- précision GNSS au moment du relevé (QField)
    source_geom      text NOT NULL DEFAULT 'saisie',
    source_attributs text NOT NULL DEFAULT 'saisie',
    osm_id           bigint,
    date_creation    timestamptz NOT NULL DEFAULT now(),
    auteur_creation  text NOT NULL DEFAULT current_user,
    date_maj         timestamptz,
    auteur_maj       text,
    geom             geometry(Point, 2154) NOT NULL
);
CREATE INDEX arbre_geom_idx ON arbre USING gist (geom);
CREATE INDEX arbre_code_insee_idx ON arbre (code_insee);
CREATE INDEX arbre_etat_idx ON arbre (etat_sanitaire);

COMMENT ON TABLE arbre IS 'Inventaire du patrimoine arboré communal et intercommunal (un point par arbre)';
COMMENT ON COLUMN arbre.numero IS 'Identifiant lisible attribué automatiquement : ARB-<code INSEE>-<numéro>';
COMMENT ON COLUMN arbre.code_insee IS 'Commune, déduite de la position par la base (ne pas saisir)';
COMMENT ON COLUMN arbre.circonference_cm IS 'Circonférence du tronc mesurée à 1,30 m du sol';
COMMENT ON COLUMN arbre.date_diagnostic IS 'Date du dernier diagnostic sanitaire, mise à jour par les interventions de type diagnostic';
COMMENT ON COLUMN arbre.precision_m IS 'Précision horizontale du positionnement GNSS (m), renseignée automatiquement par QField';
COMMENT ON COLUMN arbre.source_geom IS 'Origine de la position : saisie, osm (OpenStreetMap, ODbL), gps';
COMMENT ON COLUMN arbre.source_attributs IS 'Origine des attributs : saisie, osm, simulation (jeu de démonstration)';

-- Règles de gestion appliquées à chaque saisie, quel que soit l'outil
CREATE OR REPLACE FUNCTION tg_arbre_avant() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- 1. la commune se déduit de la position
    SELECT c.code_insee INTO NEW.code_insee
    FROM ref_admin.commune c
    WHERE ST_Intersects(c.geom, NEW.geom)
    LIMIT 1;
    IF NEW.code_insee IS NULL THEN
        RAISE EXCEPTION 'Arbre hors du territoire intercommunal (X=%, Y=%)',
            round(ST_X(NEW.geom)), round(ST_Y(NEW.geom))
            USING HINT = 'Vérifier la position du point ou la projection (Lambert-93)';
    END IF;

    -- 2. numéro lisible attribué à la création
    IF TG_OP = 'INSERT' AND NEW.numero IS NULL THEN
        NEW.numero := 'ARB-' || NEW.code_insee || '-'
                      || lpad(nextval('espaces_verts.seq_numero_arbre')::text, 5, '0');
    END IF;

    -- 3. cohérences
    IF NEW.annee_plantation > extract(year FROM current_date) THEN
        RAISE EXCEPTION 'Année de plantation dans le futur : %', NEW.annee_plantation;
    END IF;
    IF NEW.etat_sanitaire = 'mort' AND NEW.risque IS DISTINCT FROM 'eleve' THEN
        NEW.risque := 'eleve';   -- un arbre mort est toujours à risque élevé
    END IF;

    -- 4. traçabilité
    IF TG_OP = 'UPDATE' THEN
        NEW.date_creation   := OLD.date_creation;
        NEW.auteur_creation := OLD.auteur_creation;
        NEW.date_maj        := now();
        NEW.auteur_maj      := coalesce(nullif(NEW.auteur_maj, OLD.auteur_maj), current_user);
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER arbre_avant
    BEFORE INSERT OR UPDATE ON arbre
    FOR EACH ROW EXECUTE FUNCTION tg_arbre_avant();

-- -----------------------------------------------------------------------------
-- Interventions (une ligne par opération sur un arbre)
-- -----------------------------------------------------------------------------
CREATE TABLE intervention (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    arbre_id          uuid NOT NULL REFERENCES arbre (id) ON DELETE CASCADE,
    type_intervention text NOT NULL REFERENCES liste_type_intervention (code),
    date_intervention date NOT NULL,
    intervenant       text NOT NULL DEFAULT 'Régie espaces verts',
    cout_ht           numeric(10, 2) CHECK (cout_ht >= 0),
    etat_constate     text REFERENCES liste_etat_sanitaire (code),
    commentaire       text,
    date_creation     timestamptz NOT NULL DEFAULT now(),
    auteur_creation   text NOT NULL DEFAULT current_user
);
CREATE INDEX intervention_arbre_idx ON intervention (arbre_id);
COMMENT ON TABLE intervention IS 'Historique des interventions sur les arbres (diagnostic, taille, abattage...)';

-- Une intervention met à jour la fiche de l'arbre
CREATE OR REPLACE FUNCTION tg_intervention_apres() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.type_intervention = 'abattage' THEN
        UPDATE espaces_verts.arbre SET statut = 'abattu' WHERE id = NEW.arbre_id;
    ELSIF NEW.type_intervention = 'plantation' THEN
        UPDATE espaces_verts.arbre
        SET statut = 'en_place', stade_dev = 'jeune',
            annee_plantation = extract(year FROM NEW.date_intervention)
        WHERE id = NEW.arbre_id;
    END IF;
    IF NEW.etat_constate IS NOT NULL THEN
        UPDATE espaces_verts.arbre
        SET etat_sanitaire = NEW.etat_constate,
            date_diagnostic = greatest(coalesce(date_diagnostic, NEW.date_intervention),
                                       NEW.date_intervention)
        WHERE id = NEW.arbre_id;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER intervention_apres
    AFTER INSERT ON intervention
    FOR EACH ROW EXECUTE FUNCTION tg_intervention_apres();

-- -----------------------------------------------------------------------------
-- Journal des modifications (audit)
-- -----------------------------------------------------------------------------
CREATE TABLE journal (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_nom   text NOT NULL,
    objet_id    uuid NOT NULL,
    operation   text NOT NULL,
    date_op     timestamptz NOT NULL DEFAULT now(),
    utilisateur text NOT NULL DEFAULT current_user,
    avant       jsonb,
    apres       jsonb
);
CREATE INDEX journal_objet_idx ON journal (objet_id);
COMMENT ON TABLE journal IS 'Journal des créations, modifications et suppressions (alimenté par déclencheur)';

CREATE OR REPLACE FUNCTION tg_journal() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = espaces_verts, public AS $$
BEGIN
    INSERT INTO espaces_verts.journal (table_nom, objet_id, operation, avant, apres)
    VALUES (TG_TABLE_NAME,
            CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END,
            TG_OP,
            CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) - 'geom' END,
            CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) - 'geom' END);
    RETURN NULL;
END $$;

CREATE TRIGGER arbre_journal AFTER INSERT OR UPDATE OR DELETE ON arbre
    FOR EACH ROW EXECUTE FUNCTION tg_journal();
CREATE TRIGGER intervention_journal AFTER INSERT OR UPDATE OR DELETE ON intervention
    FOR EACH ROW EXECUTE FUNCTION tg_journal();

-- -----------------------------------------------------------------------------
-- Vues de consultation
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_arbre AS
SELECT a.id, a.numero, a.code_insee, c.nom AS commune,
       a.essence, e.nom_francais, e.genre, e.allergisant, e.envahissante,
       a.implantation, i.libelle AS implantation_libelle,
       a.stade_dev, a.hauteur_m, a.circonference_cm, a.annee_plantation,
       a.etat_sanitaire, s.libelle AS etat_libelle, s.ordre AS etat_ordre,
       a.risque, a.remarquable, a.date_diagnostic, a.statut,
       der.date_intervention AS derniere_intervention,
       der.type_intervention AS dernier_type_intervention,
       (a.date_diagnostic IS NULL
        OR a.date_diagnostic < current_date - interval '3 years') AS diagnostic_a_refaire,
       a.source_geom, a.source_attributs, a.geom
FROM arbre a
JOIN ref_admin.commune c USING (code_insee)
JOIN liste_essence e ON e.code = a.essence
LEFT JOIN liste_implantation i ON i.code = a.implantation
LEFT JOIN liste_etat_sanitaire s ON s.code = a.etat_sanitaire
LEFT JOIN LATERAL (
    SELECT date_intervention, type_intervention
    FROM intervention WHERE arbre_id = a.id
    ORDER BY date_intervention DESC LIMIT 1
) der ON true
WHERE a.statut = 'en_place';
COMMENT ON VIEW v_arbre IS 'Arbres en place avec libellés, dernière intervention et besoin de diagnostic';

-- Priorités d'intervention : ce que l'équipe doit traiter en premier
CREATE OR REPLACE VIEW v_arbre_prioritaire AS
SELECT v.*,
       CASE
           WHEN v.etat_sanitaire = 'mort' OR (v.risque = 'eleve' AND v.etat_ordre >= 4) THEN 1
           WHEN v.etat_sanitaire = 'deperissant' OR v.risque = 'eleve' THEN 2
           ELSE 3
       END AS priorite
FROM v_arbre v
WHERE v.etat_sanitaire IN ('mort', 'deperissant', 'surveiller') OR v.risque = 'eleve';
COMMENT ON VIEW v_arbre_prioritaire IS 'Arbres à traiter : 1 = sécurisation immédiate, 2 = sous 6 mois, 3 = surveillance renforcée';

-- Programme de diagnostics : arbres jamais diagnostiqués ou depuis plus de 3 ans
CREATE OR REPLACE VIEW v_arbre_diagnostic_a_programmer AS
SELECT v.*, coalesce(current_date - v.date_diagnostic, 9999) AS jours_depuis_diagnostic
FROM v_arbre v
WHERE v.diagnostic_a_refaire;
COMMENT ON VIEW v_arbre_diagnostic_a_programmer IS 'Arbres à inscrire au prochain programme de diagnostic sanitaire';

CREATE OR REPLACE VIEW v_synthese_commune AS
SELECT c.code_insee, c.nom AS commune,
       count(a.id) AS nb_arbres,
       count(a.id) FILTER (WHERE a.remarquable) AS nb_remarquables,
       count(a.id) FILTER (WHERE a.etat_sanitaire IN ('deperissant', 'mort')) AS nb_degrades,
       round(100.0 * count(a.id) FILTER (WHERE a.etat_sanitaire IN ('deperissant', 'mort'))
             / nullif(count(a.id), 0), 1) AS part_degrades_pct,
       count(DISTINCT a.essence) AS nb_essences,
       (SELECT coalesce(sum(i.cout_ht), 0) FROM intervention i
        JOIN arbre a2 ON a2.id = i.arbre_id
        WHERE a2.code_insee = c.code_insee
          AND i.date_intervention >= date_trunc('year', current_date)) AS cout_annee_en_cours
FROM ref_admin.commune c
LEFT JOIN arbre a ON a.code_insee = c.code_insee AND a.statut = 'en_place'
GROUP BY c.code_insee, c.nom;

-- Droits : les éditeurs saisissent arbres et interventions, mais ne touchent
-- ni aux listes de valeurs ni au journal (qui reste en lecture seule).
GRANT SELECT ON ALL TABLES IN SCHEMA espaces_verts TO sig_lecteur;
GRANT INSERT, UPDATE, DELETE ON arbre, intervention TO sig_editeur;
REVOKE INSERT, UPDATE, DELETE ON liste_etat_sanitaire, liste_stade_dev, liste_implantation,
    liste_risque, liste_type_intervention, liste_essence, journal FROM sig_editeur;
GRANT USAGE ON SEQUENCE seq_numero_arbre TO sig_editeur;

RESET search_path;
