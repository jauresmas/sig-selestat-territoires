-- =============================================================================
-- Socle SIG intercommunal - 01. Extensions, rôles et schémas
-- À exécuter en superutilisateur sur la base sig_ccst.
-- Le script est rejouable : il ne recrée que ce qui manque.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- recherche approchée (adresses, voies)
CREATE EXTENSION IF NOT EXISTS unaccent;  -- comparaisons sans accents

-- -----------------------------------------------------------------------------
-- Rôles
--   sig_admin   : administrateur du SIG, propriétaire de tous les objets
--   sig_editeur : agents qui saisissent les données métier (bureau ou QField)
--   sig_lecteur : agents qui consultent le SIG (QGIS, visualiseur interne)
--   sig_public  : diffusion externe (carte web, open data), schéma diffusion seul
-- Les rôles de groupe ne se connectent pas ; les comptes nominatifs en héritent.
-- Les mots de passe ne figurent jamais dans les scripts : ils sont définis par
-- l'administrateur avec \password, et stockés côté QGIS dans la base
-- d'authentification chiffrée (authcfg).
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN SELECT * FROM (VALUES
        ('sig_admin',   true),
        ('sig_editeur', false),
        ('sig_lecteur', false),
        ('sig_public',  false),
        -- comptes nominatifs de démonstration
        ('u_espaces_verts', true),
        ('u_urbanisme',     true),
        ('u_web',           true)
    ) AS t(nom, connexion)
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.nom) THEN
            EXECUTE format('CREATE ROLE %I %s', r.nom,
                           CASE WHEN r.connexion THEN 'LOGIN' ELSE 'NOLOGIN' END);
        END IF;
    END LOOP;
END $$;

GRANT sig_lecteur TO sig_editeur;         -- un éditeur peut aussi consulter
GRANT sig_editeur TO u_espaces_verts;
GRANT sig_lecteur TO u_urbanisme;
GRANT sig_public  TO u_web;

COMMENT ON ROLE sig_admin   IS 'Administrateur du SIG : propriétaire des schémas, intégration des référentiels';
COMMENT ON ROLE sig_editeur IS 'Saisie des données métier (espaces verts), au bureau ou sur le terrain avec QField';
COMMENT ON ROLE sig_lecteur IS 'Consultation de l''ensemble des données internes';
COMMENT ON ROLE sig_public  IS 'Diffusion externe : lecture du seul schéma diffusion';

ALTER DATABASE sig_ccst OWNER TO sig_admin;
REVOKE ALL ON DATABASE sig_ccst FROM PUBLIC;
GRANT CONNECT ON DATABASE sig_ccst TO sig_lecteur, sig_public;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- -----------------------------------------------------------------------------
-- Schémas : un schéma par famille de données, pour lire la base d'un coup d'oeil
-- et donner des droits par bloc.
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS ref_admin    AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS ref_cadastre AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS ref_adresse  AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS ref_topo     AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS urbanisme    AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS servitudes   AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS environnement AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS espaces_verts AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS metadonnees  AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS controle     AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS diffusion    AUTHORIZATION sig_admin;
CREATE SCHEMA IF NOT EXISTS import       AUTHORIZATION sig_admin;

COMMENT ON SCHEMA ref_admin     IS 'Référentiel : limites administratives (IGN ADMIN EXPRESS COG)';
COMMENT ON SCHEMA ref_cadastre  IS 'Référentiel : parcellaire cadastral (IGN Parcellaire Express, DGFiP)';
COMMENT ON SCHEMA ref_adresse   IS 'Référentiel : adresses (Base Adresse Nationale)';
COMMENT ON SCHEMA ref_topo      IS 'Référentiel : bâti, voirie, hydrographie, équipements (IGN BD TOPO)';
COMMENT ON SCHEMA urbanisme     IS 'Documents d''urbanisme au standard CNIG (Géoportail de l''Urbanisme)';
COMMENT ON SCHEMA servitudes    IS 'Servitudes d''utilité publique (Géoportail de l''Urbanisme)';
COMMENT ON SCHEMA environnement IS 'Zonages du patrimoine naturel (INPN)';
COMMENT ON SCHEMA espaces_verts IS 'Données métier : inventaire et gestion du patrimoine arboré';
COMMENT ON SCHEMA metadonnees   IS 'Catalogue des données, journal des intégrations';
COMMENT ON SCHEMA controle      IS 'Vues de contrôle qualité (une ligne = une anomalie)';
COMMENT ON SCHEMA diffusion     IS 'Vues publiées à l''extérieur (carte web, open data) : aucune donnée sensible';
COMMENT ON SCHEMA import        IS 'Tables de transit pour l''intégration (réservé à l''administrateur)';

-- -----------------------------------------------------------------------------
-- Droits par bloc, y compris sur les tables créées plus tard (DEFAULT PRIVILEGES)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    s text;
BEGIN
    FOREACH s IN ARRAY ARRAY['ref_admin', 'ref_cadastre', 'ref_adresse', 'ref_topo',
                             'urbanisme', 'servitudes', 'environnement', 'espaces_verts',
                             'metadonnees', 'controle']
    LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO sig_lecteur', s);
        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO sig_lecteur', s);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE sig_admin IN SCHEMA %I '
                       'GRANT SELECT ON TABLES TO sig_lecteur', s);
    END LOOP;
END $$;

-- Saisie métier : les éditeurs écrivent dans espaces_verts, sans pouvoir
-- modifier la structure ni les listes de valeurs (droits retirés plus loin).
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA espaces_verts TO sig_editeur;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA espaces_verts TO sig_editeur;
ALTER DEFAULT PRIVILEGES FOR ROLE sig_admin IN SCHEMA espaces_verts
    GRANT INSERT, UPDATE, DELETE ON TABLES TO sig_editeur;
ALTER DEFAULT PRIVILEGES FOR ROLE sig_admin IN SCHEMA espaces_verts
    GRANT USAGE ON SEQUENCES TO sig_editeur;

-- Diffusion : le public ne voit que le schéma diffusion
GRANT USAGE ON SCHEMA diffusion TO sig_public, sig_lecteur;
ALTER DEFAULT PRIVILEGES FOR ROLE sig_admin IN SCHEMA diffusion
    GRANT SELECT ON TABLES TO sig_public, sig_lecteur;

-- -----------------------------------------------------------------------------
-- Catalogue : une fiche par jeu de données (profil INSPIRE / ISO 19115 simplifié)
-- Les fiches XML ISO 19139 et le catalogue de la carte web sont générés
-- à partir de cette table (scripts/04_metadonnees.py).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadonnees.fiche (
    identifiant      uuid PRIMARY KEY,
    table_nom        text UNIQUE NOT NULL,   -- schema.table dans la base
    titre            text NOT NULL,
    resume           text NOT NULL,
    theme_inspire    text,
    mots_cles        text[],
    producteur       text NOT NULL,
    gestionnaire     text NOT NULL,
    licence          text NOT NULL,
    niveau_diffusion text NOT NULL CHECK (niveau_diffusion IN ('ouverte', 'interne', 'restreinte')),
    motif_restriction text,
    source_url       text,
    millesime        text,
    date_integration date NOT NULL DEFAULT current_date,
    frequence_maj    text,
    echelle          text,
    nb_objets        integer,
    emprise          geometry(Polygon, 2154),
    CHECK (niveau_diffusion = 'ouverte' OR motif_restriction IS NOT NULL)
);
COMMENT ON TABLE metadonnees.fiche IS 'Catalogue des jeux de données du SIG (une fiche par table)';
COMMENT ON COLUMN metadonnees.fiche.niveau_diffusion IS
    'ouverte : diffusable à tous (open data) ; interne : agents de la collectivité ; restreinte : convention ou habilitation nécessaire';

CREATE TABLE IF NOT EXISTS metadonnees.journal_integration (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_integration timestamptz NOT NULL DEFAULT now(),
    table_nom   text NOT NULL,
    nb_objets   integer NOT NULL,
    source      text,
    script      text,
    utilisateur text NOT NULL DEFAULT current_user
);
COMMENT ON TABLE metadonnees.journal_integration IS 'Historique des intégrations de données (une ligne par chargement)';
ALTER TABLE metadonnees.fiche OWNER TO sig_admin;
ALTER TABLE metadonnees.journal_integration OWNER TO sig_admin;
GRANT SELECT ON metadonnees.fiche, metadonnees.journal_integration TO sig_lecteur;

-- Registre des diffusions : chaque extraction remise à un tiers y est tracée
-- (qui, quoi, sur quel périmètre, sous quelle licence ou convention)
CREATE TABLE IF NOT EXISTS metadonnees.journal_diffusion (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_diffusion timestamptz NOT NULL DEFAULT now(),
    demandeur     text NOT NULL,
    objet         text NOT NULL,
    destinataire  text NOT NULL CHECK (destinataire IN ('externe', 'interne')),
    communes      text[] NOT NULL,
    jeux          text[] NOT NULL,
    convention    text,
    fichier       text NOT NULL,
    utilisateur   text NOT NULL DEFAULT current_user
);
COMMENT ON TABLE metadonnees.journal_diffusion IS 'Registre des extractions remises à des tiers (scripts/extraction.py)';
ALTER TABLE metadonnees.journal_diffusion OWNER TO sig_admin;
GRANT SELECT ON metadonnees.journal_diffusion TO sig_lecteur;
