--
-- PostgreSQL database dump
--

-- Dumped from database version 15.10
-- Dumped by pg_dump version 15.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: controle; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA controle;


--
-- Name: SCHEMA controle; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA controle IS 'Vues de contrôle qualité (une ligne = une anomalie)';


--
-- Name: diffusion; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA diffusion;


--
-- Name: SCHEMA diffusion; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA diffusion IS 'Vues publiées à l''extérieur (carte web, open data) : aucune donnée sensible';


--
-- Name: environnement; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA environnement;


--
-- Name: SCHEMA environnement; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA environnement IS 'Zonages du patrimoine naturel (INPN)';


--
-- Name: espaces_verts; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA espaces_verts;


--
-- Name: SCHEMA espaces_verts; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA espaces_verts IS 'Données métier : inventaire et gestion du patrimoine arboré';


--
-- Name: import; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA import;


--
-- Name: SCHEMA import; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA import IS 'Tables de transit pour l''intégration (réservé à l''administrateur)';


--
-- Name: metadonnees; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA metadonnees;


--
-- Name: SCHEMA metadonnees; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA metadonnees IS 'Catalogue des données, journal des intégrations';


--
-- Name: ref_admin; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ref_admin;


--
-- Name: SCHEMA ref_admin; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA ref_admin IS 'Référentiel : limites administratives (IGN ADMIN EXPRESS COG)';


--
-- Name: ref_adresse; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ref_adresse;


--
-- Name: SCHEMA ref_adresse; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA ref_adresse IS 'Référentiel : adresses (Base Adresse Nationale)';


--
-- Name: ref_cadastre; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ref_cadastre;


--
-- Name: SCHEMA ref_cadastre; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA ref_cadastre IS 'Référentiel : parcellaire cadastral (IGN Parcellaire Express, DGFiP)';


--
-- Name: ref_topo; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ref_topo;


--
-- Name: SCHEMA ref_topo; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA ref_topo IS 'Référentiel : bâti, voirie, hydrographie, équipements (IGN BD TOPO)';


--
-- Name: servitudes; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA servitudes;


--
-- Name: SCHEMA servitudes; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA servitudes IS 'Servitudes d''utilité publique (Géoportail de l''Urbanisme)';


--
-- Name: urbanisme; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA urbanisme;


--
-- Name: SCHEMA urbanisme; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA urbanisme IS 'Documents d''urbanisme au standard CNIG (Géoportail de l''Urbanisme)';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: unaccent; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;


--
-- Name: EXTENSION unaccent; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION unaccent IS 'text search dictionary that removes accents';


--
-- Name: tg_arbre_avant(); Type: FUNCTION; Schema: espaces_verts; Owner: -
--

CREATE FUNCTION espaces_verts.tg_arbre_avant() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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


--
-- Name: tg_intervention_apres(); Type: FUNCTION; Schema: espaces_verts; Owner: -
--

CREATE FUNCTION espaces_verts.tg_intervention_apres() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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


--
-- Name: tg_journal(); Type: FUNCTION; Schema: espaces_verts; Owner: -
--

CREATE FUNCTION espaces_verts.tg_journal() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'espaces_verts', 'public'
    AS $$
BEGIN
    INSERT INTO espaces_verts.journal (table_nom, objet_id, operation, avant, apres)
    VALUES (TG_TABLE_NAME,
            CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END,
            TG_OP,
            CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) - 'geom' END,
            CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) - 'geom' END);
    RETURN NULL;
END $$;


--
-- Name: rechercher(text, integer); Type: FUNCTION; Schema: ref_adresse; Owner: -
--

CREATE FUNCTION ref_adresse.rechercher(p_texte text, p_limite integer DEFAULT 10) RETURNS TABLE(cle_interop text, adresse text, commune text, score real, geom public.geometry)
    LANGUAGE sql STABLE
    AS $$
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


--
-- Name: FUNCTION rechercher(p_texte text, p_limite integer); Type: COMMENT; Schema: ref_adresse; Owner: -
--

COMMENT ON FUNCTION ref_adresse.rechercher(p_texte text, p_limite integer) IS 'Recherche approchée d''adresse (trigrammes, sans accents). Exemple : SELECT * FROM ref_adresse.rechercher(''9 place d armes selestat'')';


--
-- Name: nom_lisible(text); Type: FUNCTION; Schema: servitudes; Owner: -
--

CREATE FUNCTION servitudes.nom_lisible(p_nom text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $_$
    SELECT trim(replace(regexp_replace(p_nom, '^[A-Za-z0-9]+_|_(ass|abor|gen|per|pro)$', '', 'g'),
                        '_', ' '))
$_$;


--
-- Name: fiche_parcelle(text); Type: FUNCTION; Schema: urbanisme; Owner: -
--

CREATE FUNCTION urbanisme.fiche_parcelle(p_idu text) RETURNS jsonb
    LANGUAGE sql STABLE
    AS $$
WITH p AS (
    SELECT pa.*, ST_Buffer(pa.geom, -0.5) AS g, ST_Area(pa.geom) AS surf
    FROM ref_cadastre.parcelle pa WHERE pa.idu = p_idu
)
SELECT jsonb_build_object(
    'idu', p.idu,
    'commune', c.nom,
    'code_insee', p.code_insee,
    'section', p.section,
    'numero', p.numero,
    'contenance_m2', p.contenance,
    'surface_sig_m2', round(p.surf::numeric),
    'document_urbanisme', (
        SELECT jsonb_build_object('type', d.typedoc, 'identifiant', d.idurba,
                                  'approbation', d.datappro, 'procedure', d.nomproc)
        FROM urbanisme.doc_urba d WHERE d.code_insee = p.code_insee),
    'zonage', (
        SELECT jsonb_agg(jsonb_build_object(
                   'zone', z.libelle, 'libelle', z.libelong, 'type', z.typezone,
                   'part_pct', round((100 * ST_Area(ST_Intersection(z.geom, p.geom)) / p.surf)::numeric, 1),
                   'reglement', coalesce(z.url_reglement, z.nomfic))
               ORDER BY ST_Area(ST_Intersection(z.geom, p.geom)) DESC)
        FROM urbanisme.zone_urba z
        WHERE z.code_insee = p.code_insee AND ST_Intersects(z.geom, p.g)),
    'prescriptions', (
        SELECT jsonb_agg(DISTINCT jsonb_build_object('type', coalesce(t.libelle, x.typepsc),
                                                     'libelle', x.libelle))
        FROM (SELECT typepsc, libelle, geom FROM urbanisme.prescription_surf
              UNION ALL SELECT typepsc, libelle, geom FROM urbanisme.prescription_lin
              UNION ALL SELECT typepsc, libelle, geom FROM urbanisme.prescription_pct) x
        LEFT JOIN urbanisme.type_prescription t ON t.code = x.typepsc
        WHERE ST_Intersects(x.geom, p.g)),
    'informations', (
        SELECT jsonb_agg(DISTINCT jsonb_build_object('type', coalesce(t.libelle, i.typeinf),
                                                     'libelle', i.libelle))
        FROM urbanisme.info_surf i
        LEFT JOIN urbanisme.type_information t ON t.code = i.typeinf
        WHERE ST_Intersects(i.geom, p.g)),
    'servitudes', (
        SELECT jsonb_agg(DISTINCT jsonb_build_object(
                   'categorie', s.suptype,
                   'libelle', coalesce(k.libelle, s.suptype),
                   'objet', servitudes.nom_lisible(coalesce(nullif(s.nomsuplitt, ''), s.nomass))))
        FROM servitudes.sup_assiette_s s
        LEFT JOIN servitudes.categorie_sup k ON k.code = s.suptype
        WHERE ST_Intersects(s.geom, p.g)),
    'patrimoine_naturel', (
        SELECT jsonb_agg(DISTINCT jsonb_build_object('type', n.libelle_type, 'nom', n.nom))
        FROM environnement.zonage_naturel n WHERE ST_Intersects(n.geom, p.g)),
    'adresses', (
        SELECT jsonb_agg(DISTINCT concat_ws(' ', a.numero::text || coalesce(a.rep, ''), a.nom_voie))
        FROM ref_adresse.adresse a
        WHERE a.cad_parcelles LIKE '%' || p.idu || '%' OR ST_Within(a.geom, p.geom)),
    'batiments', (SELECT count(*) FROM ref_topo.batiment b WHERE ST_Intersects(b.geom, p.g)),
    'arbres_inventories', (SELECT count(*) FROM espaces_verts.arbre t
                           WHERE t.statut = 'en_place' AND ST_Within(t.geom, p.geom)),
    'avertissement', 'Document d''information sans valeur juridique. Seul un certificat d''urbanisme fait foi.'
)
FROM p JOIN ref_admin.commune c ON c.code_insee = p.code_insee
$$;


--
-- Name: FUNCTION fiche_parcelle(p_idu text); Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON FUNCTION urbanisme.fiche_parcelle(p_idu text) IS 'Renseignements d''urbanisme d''une parcelle au format JSON (zonage, prescriptions, SUP, environnement, adresses)';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: adresse; Type: TABLE; Schema: ref_adresse; Owner: -
--

CREATE TABLE ref_adresse.adresse (
    cle_interop text NOT NULL,
    id_fantoir text,
    numero bigint,
    rep text,
    nom_voie text,
    nom_ld text,
    code_postal text,
    code_insee text,
    nom_commune text,
    type_position text,
    source_position text,
    source_nom_voie text,
    certification_commune boolean,
    cad_parcelles text,
    geom public.geometry(Point,2154)
);


--
-- Name: TABLE adresse; Type: COMMENT; Schema: ref_adresse; Owner: -
--

COMMENT ON TABLE ref_adresse.adresse IS 'Adresses - Points adresses de la Base Adresse Nationale : numéro, voie, position, parcelle de rattachement et certification par la commune.';


--
-- Name: COLUMN adresse.cle_interop; Type: COMMENT; Schema: ref_adresse; Owner: -
--

COMMENT ON COLUMN ref_adresse.adresse.cle_interop IS 'Clé d''interopérabilité de l''adresse (BAN)';


--
-- Name: COLUMN adresse.numero; Type: COMMENT; Schema: ref_adresse; Owner: -
--

COMMENT ON COLUMN ref_adresse.adresse.numero IS 'Numéro (parcelle ou adresse)';


--
-- Name: COLUMN adresse.rep; Type: COMMENT; Schema: ref_adresse; Owner: -
--

COMMENT ON COLUMN ref_adresse.adresse.rep IS 'Indice de répétition (bis, ter...)';


--
-- Name: COLUMN adresse.nom_voie; Type: COMMENT; Schema: ref_adresse; Owner: -
--

COMMENT ON COLUMN ref_adresse.adresse.nom_voie IS 'Nom de la voie';


--
-- Name: COLUMN adresse.code_insee; Type: COMMENT; Schema: ref_adresse; Owner: -
--

COMMENT ON COLUMN ref_adresse.adresse.code_insee IS 'Code officiel géographique de la commune (INSEE)';


--
-- Name: COLUMN adresse.certification_commune; Type: COMMENT; Schema: ref_adresse; Owner: -
--

COMMENT ON COLUMN ref_adresse.adresse.certification_commune IS 'Adresse certifiée par la commune dans sa Base Adresse Locale';


--
-- Name: COLUMN adresse.cad_parcelles; Type: COMMENT; Schema: ref_adresse; Owner: -
--

COMMENT ON COLUMN ref_adresse.adresse.cad_parcelles IS 'Parcelles cadastrales de rattachement (identifiants séparés par |)';


--
-- Name: COLUMN adresse.geom; Type: COMMENT; Schema: ref_adresse; Owner: -
--

COMMENT ON COLUMN ref_adresse.adresse.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: v_adresse_doublon; Type: VIEW; Schema: controle; Owner: -
--

CREATE VIEW controle.v_adresse_doublon AS
 SELECT a.cle_interop,
    a.code_insee,
    a.numero,
    a.rep,
    a.nom_voie,
    d.nb,
    a.geom
   FROM (ref_adresse.adresse a
     JOIN ( SELECT adresse.code_insee,
            adresse.numero,
            COALESCE(adresse.rep, ''::text) AS rep,
            lower(public.unaccent(adresse.nom_voie)) AS voie,
            count(*) AS nb
           FROM ref_adresse.adresse
          WHERE ((adresse.numero IS NOT NULL) AND (adresse.numero < 5000))
          GROUP BY adresse.code_insee, adresse.numero, COALESCE(adresse.rep, ''::text), (lower(public.unaccent(adresse.nom_voie)))
         HAVING (count(*) > 1)) d ON (((d.code_insee = a.code_insee) AND (d.numero = a.numero) AND (d.rep = COALESCE(a.rep, ''::text)) AND (d.voie = lower(public.unaccent(a.nom_voie))))));


--
-- Name: v_adresse_non_certifiee; Type: VIEW; Schema: controle; Owner: -
--

CREATE VIEW controle.v_adresse_non_certifiee AS
 SELECT a.cle_interop,
    a.code_insee,
    a.numero,
    a.rep,
    a.nom_voie,
    a.source_position,
    a.geom
   FROM ref_adresse.adresse a
  WHERE ((NOT a.certification_commune) AND (a.numero < 5000));


--
-- Name: arbre; Type: TABLE; Schema: espaces_verts; Owner: -
--

CREATE TABLE espaces_verts.arbre (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    numero text,
    code_insee text,
    essence text DEFAULT 'Indetermine'::text NOT NULL,
    implantation text,
    stade_dev text,
    hauteur_m numeric(4,1),
    circonference_cm integer,
    annee_plantation integer,
    etat_sanitaire text,
    risque text,
    remarquable boolean DEFAULT false NOT NULL,
    date_diagnostic date,
    statut text DEFAULT 'en_place'::text NOT NULL,
    observations text,
    photo text,
    precision_m numeric(5,2),
    source_geom text DEFAULT 'saisie'::text NOT NULL,
    source_attributs text DEFAULT 'saisie'::text NOT NULL,
    osm_id bigint,
    date_creation timestamp with time zone DEFAULT now() NOT NULL,
    auteur_creation text DEFAULT CURRENT_USER NOT NULL,
    date_maj timestamp with time zone,
    auteur_maj text,
    geom public.geometry(Point,2154) NOT NULL,
    CONSTRAINT arbre_annee_plantation_check CHECK (((annee_plantation >= 1700) AND (annee_plantation <= 2100))),
    CONSTRAINT arbre_circonference_cm_check CHECK (((circonference_cm >= 5) AND (circonference_cm <= 1500))),
    CONSTRAINT arbre_hauteur_m_check CHECK (((hauteur_m >= 0.5) AND (hauteur_m <= (50)::numeric))),
    CONSTRAINT arbre_statut_check CHECK ((statut = ANY (ARRAY['en_place'::text, 'abattu'::text, 'a_planter'::text])))
);


--
-- Name: TABLE arbre; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON TABLE espaces_verts.arbre IS 'Inventaire du patrimoine arboré - Arbres gérés par la collectivité : essence, dimensions, état sanitaire, risque et historique. Positions issues d''OpenStreetMap ; attributs simulés pour la démonstration.';


--
-- Name: COLUMN arbre.numero; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON COLUMN espaces_verts.arbre.numero IS 'Identifiant lisible attribué automatiquement : ARB-<code INSEE>-<numéro>';


--
-- Name: COLUMN arbre.code_insee; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON COLUMN espaces_verts.arbre.code_insee IS 'Commune, déduite de la position par la base (ne pas saisir)';


--
-- Name: COLUMN arbre.circonference_cm; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON COLUMN espaces_verts.arbre.circonference_cm IS 'Circonférence du tronc mesurée à 1,30 m du sol';


--
-- Name: COLUMN arbre.date_diagnostic; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON COLUMN espaces_verts.arbre.date_diagnostic IS 'Date du dernier diagnostic sanitaire, mise à jour par les interventions de type diagnostic';


--
-- Name: COLUMN arbre.precision_m; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON COLUMN espaces_verts.arbre.precision_m IS 'Précision horizontale du positionnement GNSS (m), renseignée automatiquement par QField';


--
-- Name: COLUMN arbre.source_geom; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON COLUMN espaces_verts.arbre.source_geom IS 'Origine de la position : saisie, osm (OpenStreetMap, ODbL), gps';


--
-- Name: COLUMN arbre.source_attributs; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON COLUMN espaces_verts.arbre.source_attributs IS 'Origine des attributs : saisie, osm, simulation (jeu de démonstration)';


--
-- Name: v_arbre_doublon; Type: VIEW; Schema: controle; Owner: -
--

CREATE VIEW controle.v_arbre_doublon AS
 SELECT a.numero AS numero_a,
    b.numero AS numero_b,
    round((public.st_distance(a.geom, b.geom))::numeric, 2) AS distance_m,
    a.geom
   FROM (espaces_verts.arbre a
     JOIN espaces_verts.arbre b ON (((a.id < b.id) AND public.st_dwithin(a.geom, b.geom, (1)::double precision))))
  WHERE ((a.statut = 'en_place'::text) AND (b.statut = 'en_place'::text));


--
-- Name: v_arbre_incomplet; Type: VIEW; Schema: controle; Owner: -
--

CREATE VIEW controle.v_arbre_incomplet AS
 SELECT a.numero,
    a.code_insee,
    concat_ws(', '::text,
        CASE
            WHEN (a.essence = 'Indetermine'::text) THEN 'essence'::text
            ELSE NULL::text
        END,
        CASE
            WHEN (a.etat_sanitaire IS NULL) THEN 'état sanitaire'::text
            ELSE NULL::text
        END,
        CASE
            WHEN (a.stade_dev IS NULL) THEN 'stade'::text
            ELSE NULL::text
        END,
        CASE
            WHEN (a.hauteur_m IS NULL) THEN 'hauteur'::text
            ELSE NULL::text
        END) AS champs_manquants,
    a.geom
   FROM espaces_verts.arbre a
  WHERE ((a.statut = 'en_place'::text) AND ((a.essence = 'Indetermine'::text) OR (a.etat_sanitaire IS NULL) OR (a.stade_dev IS NULL) OR (a.hauteur_m IS NULL)));


--
-- Name: commune; Type: TABLE; Schema: ref_admin; Owner: -
--

CREATE TABLE ref_admin.commune (
    code_insee text NOT NULL,
    nom text,
    statut text,
    population bigint,
    code_postal text,
    siren_commune text,
    superficie_cadastrale bigint,
    surface_ha double precision,
    geom public.geometry(MultiPolygon,2154)
);


--
-- Name: TABLE commune; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON TABLE ref_admin.commune IS 'Limites communales - Contours des 12 communes de la communauté de communes, avec leur population légale. Référentiel de rattachement de toutes les autres données.';


--
-- Name: COLUMN commune.code_insee; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON COLUMN ref_admin.commune.code_insee IS 'Code officiel géographique de la commune (INSEE)';


--
-- Name: COLUMN commune.nom; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON COLUMN ref_admin.commune.nom IS 'Nom';


--
-- Name: COLUMN commune.population; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON COLUMN ref_admin.commune.population IS 'Population municipale légale (INSEE)';


--
-- Name: COLUMN commune.surface_ha; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON COLUMN ref_admin.commune.surface_ha IS 'Surface calculée (ha, Lambert-93)';


--
-- Name: COLUMN commune.geom; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON COLUMN ref_admin.commune.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: batiment; Type: TABLE; Schema: ref_topo; Owner: -
--

CREATE TABLE ref_topo.batiment (
    cleabs text NOT NULL,
    nature text,
    usage_1 text,
    usage_2 text,
    construction_legere boolean,
    nombre_de_logements double precision,
    nombre_d_etages double precision,
    hauteur double precision,
    date_d_apparition text,
    origine_du_batiment text,
    identifiants_rnb text,
    geom public.geometry(MultiPolygon,2154)
);


--
-- Name: TABLE batiment; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON TABLE ref_topo.batiment IS 'Bâtiments - Bâtiments de la BD TOPO avec usage, nombre de logements, hauteur et identifiant RNB.';


--
-- Name: COLUMN batiment.cleabs; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.batiment.cleabs IS 'Identifiant de l''objet dans la BD TOPO';


--
-- Name: COLUMN batiment.usage_1; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.batiment.usage_1 IS 'Usage principal du bâtiment';


--
-- Name: COLUMN batiment.nombre_de_logements; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.batiment.nombre_de_logements IS 'Nombre de logements';


--
-- Name: COLUMN batiment.hauteur; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.batiment.hauteur IS 'Hauteur du bâtiment (m)';


--
-- Name: COLUMN batiment.identifiants_rnb; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.batiment.identifiants_rnb IS 'Identifiant du Référentiel national des bâtiments';


--
-- Name: COLUMN batiment.geom; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.batiment.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: v_batiment_sans_adresse; Type: VIEW; Schema: controle; Owner: -
--

CREATE VIEW controle.v_batiment_sans_adresse AS
 SELECT b.cleabs,
    c.code_insee,
    b.usage_1,
    b.nombre_de_logements,
    round((public.st_area(b.geom))::numeric) AS surface_m2,
    (public.st_pointonsurface(b.geom))::public.geometry(Point,2154) AS geom
   FROM (ref_topo.batiment b
     JOIN ref_admin.commune c ON (public.st_intersects(c.geom, public.st_pointonsurface(b.geom))))
  WHERE ((b.usage_1 = 'Résidentiel'::text) AND (public.st_area(b.geom) >= (40)::double precision) AND (NOT (EXISTS ( SELECT 1
           FROM ref_adresse.adresse a
          WHERE public.st_dwithin(a.geom, b.geom, (30)::double precision)))));


--
-- Name: parcelle; Type: TABLE; Schema: ref_cadastre; Owner: -
--

CREATE TABLE ref_cadastre.parcelle (
    idu text NOT NULL,
    code_insee text,
    commune text,
    section text,
    numero text,
    feuille bigint,
    com_abs text,
    contenance bigint,
    geom public.geometry(MultiPolygon,2154)
);


--
-- Name: TABLE parcelle; Type: COMMENT; Schema: ref_cadastre; Owner: -
--

COMMENT ON TABLE ref_cadastre.parcelle IS 'Parcelles cadastrales - Plan cadastral informatisé vectorisé (PCI) : géométrie, section, numéro et contenance de chaque parcelle. Ne contient aucune donnée sur les propriétaires.';


--
-- Name: COLUMN parcelle.idu; Type: COMMENT; Schema: ref_cadastre; Owner: -
--

COMMENT ON COLUMN ref_cadastre.parcelle.idu IS 'Identifiant unique de la parcelle (département + commune + préfixe + section + numéro)';


--
-- Name: COLUMN parcelle.code_insee; Type: COMMENT; Schema: ref_cadastre; Owner: -
--

COMMENT ON COLUMN ref_cadastre.parcelle.code_insee IS 'Code officiel géographique de la commune (INSEE)';


--
-- Name: COLUMN parcelle.section; Type: COMMENT; Schema: ref_cadastre; Owner: -
--

COMMENT ON COLUMN ref_cadastre.parcelle.section IS 'Section cadastrale';


--
-- Name: COLUMN parcelle.numero; Type: COMMENT; Schema: ref_cadastre; Owner: -
--

COMMENT ON COLUMN ref_cadastre.parcelle.numero IS 'Numéro (parcelle ou adresse)';


--
-- Name: COLUMN parcelle.contenance; Type: COMMENT; Schema: ref_cadastre; Owner: -
--

COMMENT ON COLUMN ref_cadastre.parcelle.contenance IS 'Contenance cadastrale (m²), surface fiscale indicative';


--
-- Name: COLUMN parcelle.geom; Type: COMMENT; Schema: ref_cadastre; Owner: -
--

COMMENT ON COLUMN ref_cadastre.parcelle.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: zone_urba; Type: TABLE; Schema: urbanisme; Owner: -
--

CREATE TABLE urbanisme.zone_urba (
    partition text,
    idurba text,
    libelle text,
    libelong text,
    typezone text,
    destdomi text,
    nomfic text,
    urlfic text,
    datvalid text,
    gpu_doc_id text,
    code_insee text,
    url_reglement text,
    geom public.geometry(MultiPolygon,2154),
    gid integer NOT NULL,
    CONSTRAINT zone_urba_typezone_ck CHECK ((typezone = ANY (ARRAY['U'::text, 'AUc'::text, 'AUs'::text, 'A'::text, 'N'::text, 'Nh'::text, 'Ah'::text])))
);


--
-- Name: TABLE zone_urba; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON TABLE urbanisme.zone_urba IS 'Zonage des PLU - Zones urbaines (U), à urbaniser (AU), agricoles (A) et naturelles (N) des plans locaux d''urbanisme, avec le lien vers le règlement écrit.';


--
-- Name: COLUMN zone_urba.idurba; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.zone_urba.idurba IS 'Identifiant du document d''urbanisme (standard CNIG)';


--
-- Name: COLUMN zone_urba.libelle; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.zone_urba.libelle IS 'Libellé court';


--
-- Name: COLUMN zone_urba.libelong; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.zone_urba.libelong IS 'Libellé long';


--
-- Name: COLUMN zone_urba.typezone; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.zone_urba.typezone IS 'Type de zone CNIG : U, AUc, AUs, A, N';


--
-- Name: COLUMN zone_urba.code_insee; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.zone_urba.code_insee IS 'Code officiel géographique de la commune (INSEE)';


--
-- Name: COLUMN zone_urba.url_reglement; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.zone_urba.url_reglement IS 'Lien vers le règlement écrit (pièce déposée au GPU)';


--
-- Name: COLUMN zone_urba.geom; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.zone_urba.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: COLUMN zone_urba.gid; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.zone_urba.gid IS 'Identifiant technique';


--
-- Name: v_geometrie_invalide; Type: VIEW; Schema: controle; Owner: -
--

CREATE VIEW controle.v_geometrie_invalide AS
 SELECT 'ref_cadastre.parcelle'::text AS couche,
    parcelle.idu AS identifiant,
    public.st_isvalidreason(parcelle.geom) AS anomalie,
    (public.st_pointonsurface(public.st_makevalid(parcelle.geom)))::public.geometry(Point,2154) AS geom
   FROM ref_cadastre.parcelle
  WHERE (NOT public.st_isvalid(parcelle.geom))
UNION ALL
 SELECT 'urbanisme.zone_urba'::text AS couche,
    (zone_urba.gid)::text AS identifiant,
    public.st_isvalidreason(zone_urba.geom) AS anomalie,
    public.st_pointonsurface(public.st_makevalid(zone_urba.geom)) AS geom
   FROM urbanisme.zone_urba
  WHERE (NOT public.st_isvalid(zone_urba.geom))
UNION ALL
 SELECT 'ref_topo.batiment'::text AS couche,
    batiment.cleabs AS identifiant,
    public.st_isvalidreason(batiment.geom) AS anomalie,
    public.st_pointonsurface(public.st_makevalid(batiment.geom)) AS geom
   FROM ref_topo.batiment
  WHERE (NOT public.st_isvalid(batiment.geom));


--
-- Name: doc_urba; Type: TABLE; Schema: urbanisme; Owner: -
--

CREATE TABLE urbanisme.doc_urba (
    code_insee text NOT NULL,
    partition text,
    idurba text,
    typedoc text,
    etat text,
    datappro text,
    nomproc text,
    nomreg text,
    gpu_doc_id text,
    gpu_timestamp text,
    url_reglement text,
    url_gpu text
);


--
-- Name: TABLE doc_urba; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON TABLE urbanisme.doc_urba IS 'Documents d''urbanisme en vigueur - Un enregistrement par commune : type de document (PLU, carte communale), date d''approbation et dernière procédure, au standard CNIG.';


--
-- Name: COLUMN doc_urba.code_insee; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.doc_urba.code_insee IS 'Code officiel géographique de la commune (INSEE)';


--
-- Name: COLUMN doc_urba.idurba; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.doc_urba.idurba IS 'Identifiant du document d''urbanisme (standard CNIG)';


--
-- Name: COLUMN doc_urba.url_reglement; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.doc_urba.url_reglement IS 'Lien vers le règlement écrit (pièce déposée au GPU)';


--
-- Name: mv_parcelle_zonage; Type: MATERIALIZED VIEW; Schema: urbanisme; Owner: -
--

CREATE MATERIALIZED VIEW urbanisme.mv_parcelle_zonage AS
 WITH inter AS (
         SELECT p_1.idu,
            p_1.code_insee,
            z.libelle,
            z.typezone,
            public.st_area(public.st_intersection(p_1.geom, z.geom)) AS surf
           FROM (ref_cadastre.parcelle p_1
             JOIN urbanisme.zone_urba z ON (((z.code_insee = p_1.code_insee) AND public.st_intersects(p_1.geom, z.geom))))
        )
 SELECT DISTINCT ON (p.idu) p.idu,
    p.code_insee,
    i.libelle AS zone,
    i.typezone,
    round(((((100)::double precision * i.surf) / NULLIF(public.st_area(p.geom), (0)::double precision)))::numeric, 1) AS part_pct,
    public.st_area(p.geom) AS surface_m2
   FROM (ref_cadastre.parcelle p
     LEFT JOIN inter i ON ((i.idu = p.idu)))
  ORDER BY p.idu, i.surf DESC NULLS LAST
  WITH NO DATA;


--
-- Name: MATERIALIZED VIEW mv_parcelle_zonage; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON MATERIALIZED VIEW urbanisme.mv_parcelle_zonage IS 'Zone du PLU majoritaire sur chaque parcelle (NULL si la commune n''a pas de document publié sur le GPU)';


--
-- Name: v_parcelle_hors_zonage; Type: VIEW; Schema: controle; Owner: -
--

CREATE VIEW controle.v_parcelle_hors_zonage AS
 SELECT m.idu,
    m.code_insee,
    COALESCE(m.part_pct, (0)::numeric) AS part_couverte_pct,
    (public.st_pointonsurface(p.geom))::public.geometry(Point,2154) AS geom
   FROM (urbanisme.mv_parcelle_zonage m
     JOIN ref_cadastre.parcelle p USING (idu))
  WHERE ((m.code_insee IN ( SELECT doc_urba.code_insee
           FROM urbanisme.doc_urba)) AND (COALESCE(m.part_pct, (0)::numeric) < (50)::numeric) AND (m.surface_m2 > (50)::double precision));


--
-- Name: v_zonage_chevauchement; Type: VIEW; Schema: controle; Owner: -
--

CREATE VIEW controle.v_zonage_chevauchement AS
 SELECT (row_number() OVER ())::integer AS gid,
    a.code_insee,
    a.libelle AS zone_a,
    b.libelle AS zone_b,
    round((public.st_area(public.st_intersection(a.geom, b.geom)))::numeric) AS surface_m2,
    (public.st_pointonsurface(public.st_intersection(a.geom, b.geom)))::public.geometry(Point,2154) AS geom
   FROM (urbanisme.zone_urba a
     JOIN urbanisme.zone_urba b ON (((a.code_insee = b.code_insee) AND (a.gid < b.gid) AND public.st_overlaps(a.geom, b.geom))))
  WHERE (public.st_area(public.st_intersection(a.geom, b.geom)) > (10)::double precision);


--
-- Name: v_synthese; Type: VIEW; Schema: controle; Owner: -
--

CREATE VIEW controle.v_synthese AS
 SELECT 'Géométries invalides'::text AS controle,
    'toutes couches'::text AS couche,
    ( SELECT count(*) AS count
           FROM controle.v_geometrie_invalide) AS anomalies
UNION ALL
 SELECT 'Chevauchements de zones'::text AS controle,
    'urbanisme.zone_urba'::text AS couche,
    ( SELECT count(*) AS count
           FROM controle.v_zonage_chevauchement) AS anomalies
UNION ALL
 SELECT 'Parcelles hors zonage'::text AS controle,
    'urbanisme.zone_urba'::text AS couche,
    ( SELECT count(*) AS count
           FROM controle.v_parcelle_hors_zonage) AS anomalies
UNION ALL
 SELECT 'Adresses en doublon'::text AS controle,
    'ref_adresse.adresse'::text AS couche,
    ( SELECT count(*) AS count
           FROM controle.v_adresse_doublon) AS anomalies
UNION ALL
 SELECT 'Adresses non certifiées'::text AS controle,
    'ref_adresse.adresse'::text AS couche,
    ( SELECT count(*) AS count
           FROM controle.v_adresse_non_certifiee) AS anomalies
UNION ALL
 SELECT 'Logements sans adresse proche'::text AS controle,
    'ref_topo.batiment'::text AS couche,
    ( SELECT count(*) AS count
           FROM controle.v_batiment_sans_adresse) AS anomalies
UNION ALL
 SELECT 'Arbres en doublon'::text AS controle,
    'espaces_verts.arbre'::text AS couche,
    ( SELECT count(*) AS count
           FROM controle.v_arbre_doublon) AS anomalies
UNION ALL
 SELECT 'Fiches arbre incomplètes'::text AS controle,
    'espaces_verts.arbre'::text AS couche,
    ( SELECT count(*) AS count
           FROM controle.v_arbre_incomplet) AS anomalies;


--
-- Name: liste_essence; Type: TABLE; Schema: espaces_verts; Owner: -
--

CREATE TABLE espaces_verts.liste_essence (
    code text NOT NULL,
    genre text NOT NULL,
    nom_francais text NOT NULL,
    type_feuillage text NOT NULL,
    allergisant boolean DEFAULT false NOT NULL,
    envahissante boolean DEFAULT false NOT NULL,
    CONSTRAINT liste_essence_type_feuillage_check CHECK ((type_feuillage = ANY (ARRAY['feuillu'::text, 'conifere'::text])))
);


--
-- Name: TABLE liste_essence; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON TABLE espaces_verts.liste_essence IS 'Référentiel des essences (nom scientifique, nom français, potentiel allergisant, caractère envahissant)';


--
-- Name: v_arbre; Type: VIEW; Schema: diffusion; Owner: -
--

CREATE VIEW diffusion.v_arbre AS
 SELECT a.numero,
    a.code_insee,
    a.essence,
    e.nom_francais,
    a.implantation,
    a.stade_dev,
    a.hauteur_m,
    a.circonference_cm,
    a.etat_sanitaire,
    a.remarquable,
    a.geom
   FROM (espaces_verts.arbre a
     JOIN espaces_verts.liste_essence e ON ((e.code = a.essence)))
  WHERE (a.statut = 'en_place'::text);


--
-- Name: fiche; Type: TABLE; Schema: metadonnees; Owner: -
--

CREATE TABLE metadonnees.fiche (
    identifiant uuid NOT NULL,
    table_nom text NOT NULL,
    titre text NOT NULL,
    resume text NOT NULL,
    theme_inspire text,
    mots_cles text[],
    producteur text NOT NULL,
    gestionnaire text NOT NULL,
    licence text NOT NULL,
    niveau_diffusion text NOT NULL,
    motif_restriction text,
    source_url text,
    millesime text,
    date_integration date DEFAULT CURRENT_DATE NOT NULL,
    frequence_maj text,
    echelle text,
    nb_objets integer,
    emprise public.geometry(Polygon,2154),
    CONSTRAINT fiche_check CHECK (((niveau_diffusion = 'ouverte'::text) OR (motif_restriction IS NOT NULL))),
    CONSTRAINT fiche_niveau_diffusion_check CHECK ((niveau_diffusion = ANY (ARRAY['ouverte'::text, 'interne'::text, 'restreinte'::text])))
);


--
-- Name: TABLE fiche; Type: COMMENT; Schema: metadonnees; Owner: -
--

COMMENT ON TABLE metadonnees.fiche IS 'Catalogue des jeux de données du SIG (une fiche par table)';


--
-- Name: COLUMN fiche.niveau_diffusion; Type: COMMENT; Schema: metadonnees; Owner: -
--

COMMENT ON COLUMN metadonnees.fiche.niveau_diffusion IS 'ouverte : diffusable à tous (open data) ; interne : agents de la collectivité ; restreinte : convention ou habilitation nécessaire';


--
-- Name: v_catalogue; Type: VIEW; Schema: diffusion; Owner: -
--

CREATE VIEW diffusion.v_catalogue AS
 SELECT fiche.identifiant,
    fiche.table_nom,
    fiche.titre,
    fiche.resume,
    fiche.producteur,
    fiche.licence,
    fiche.millesime,
    fiche.date_integration,
    fiche.frequence_maj,
    fiche.nb_objets
   FROM metadonnees.fiche
  WHERE (fiche.niveau_diffusion = 'ouverte'::text);


--
-- Name: v_commune; Type: VIEW; Schema: diffusion; Owner: -
--

CREATE VIEW diffusion.v_commune AS
 SELECT commune.code_insee,
    commune.nom,
    commune.population,
    commune.surface_ha,
    commune.geom
   FROM ref_admin.commune;


--
-- Name: zonage_naturel; Type: TABLE; Schema: environnement; Owner: -
--

CREATE TABLE environnement.zonage_naturel (
    type_zonage text,
    libelle_type text,
    code_mnhn text,
    nom text,
    gestionnaire text,
    url_inpn text,
    surface_ha_territoire double precision,
    geom public.geometry(MultiPolygon,2154),
    gid integer NOT NULL
);


--
-- Name: TABLE zonage_naturel; Type: COMMENT; Schema: environnement; Owner: -
--

COMMENT ON TABLE environnement.zonage_naturel IS 'Zonages du patrimoine naturel - Natura 2000, ZNIEFF, réserve naturelle régionale du Ried de Sélestat (Ill*Wald) et arrêtés de protection de biotope qui concernent le territoire.';


--
-- Name: COLUMN zonage_naturel.type_zonage; Type: COMMENT; Schema: environnement; Owner: -
--

COMMENT ON COLUMN environnement.zonage_naturel.type_zonage IS 'Type de zonage (SIC, ZPS, ZNIEFF1, ZNIEFF2, RNR, APB)';


--
-- Name: COLUMN zonage_naturel.nom; Type: COMMENT; Schema: environnement; Owner: -
--

COMMENT ON COLUMN environnement.zonage_naturel.nom IS 'Nom';


--
-- Name: COLUMN zonage_naturel.geom; Type: COMMENT; Schema: environnement; Owner: -
--

COMMENT ON COLUMN environnement.zonage_naturel.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: COLUMN zonage_naturel.gid; Type: COMMENT; Schema: environnement; Owner: -
--

COMMENT ON COLUMN environnement.zonage_naturel.gid IS 'Identifiant technique';


--
-- Name: equipement; Type: TABLE; Schema: ref_topo; Owner: -
--

CREATE TABLE ref_topo.equipement (
    cleabs text NOT NULL,
    categorie text,
    nature text,
    nature_detaillee text,
    toponyme text,
    insee_commune text,
    fictif boolean,
    geom public.geometry(MultiPolygon,2154)
);


--
-- Name: TABLE equipement; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON TABLE ref_topo.equipement IS 'Équipements et sites d''intérêt - Zones d''activité ou d''intérêt de la BD TOPO : enseignement, santé, sport, administration, culture.';


--
-- Name: COLUMN equipement.cleabs; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.equipement.cleabs IS 'Identifiant de l''objet dans la BD TOPO';


--
-- Name: COLUMN equipement.geom; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.equipement.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: sup_assiette_s; Type: TABLE; Schema: servitudes; Owner: -
--

CREATE TABLE servitudes.sup_assiette_s (
    suptype text,
    partition text,
    idgen text,
    nomsuplitt text,
    fichier text,
    gpu_doc_id text,
    idass text,
    nomass text,
    typeass text,
    modegeoass text,
    paramcalc double precision,
    geom public.geometry(MultiPolygon,2154),
    gid integer NOT NULL
);


--
-- Name: TABLE sup_assiette_s; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON TABLE servitudes.sup_assiette_s IS 'Servitudes d''utilité publique (assiettes) - Emprises où s''applique une servitude : abords des monuments historiques (AC1), plans de prévention des risques (PM1), protection des captages (AS1), réseaux...';


--
-- Name: COLUMN sup_assiette_s.suptype; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_assiette_s.suptype IS 'Catégorie de servitude d''utilité publique (AC1, PM1...)';


--
-- Name: COLUMN sup_assiette_s.geom; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_assiette_s.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: COLUMN sup_assiette_s.gid; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_assiette_s.gid IS 'Identifiant technique';


--
-- Name: sup_generateur_s; Type: TABLE; Schema: servitudes; Owner: -
--

CREATE TABLE servitudes.sup_generateur_s (
    suptype text,
    partition text,
    idgen text,
    nomsuplitt text,
    fichier text,
    gpu_doc_id text,
    nomgen text,
    typegen text,
    geom public.geometry(MultiPolygon,2154),
    gid integer NOT NULL
);


--
-- Name: TABLE sup_generateur_s; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON TABLE servitudes.sup_generateur_s IS 'Servitudes d''utilité publique (générateurs surfaciques) - Objets qui génèrent une servitude : monuments historiques, sites, captages.';


--
-- Name: COLUMN sup_generateur_s.suptype; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_generateur_s.suptype IS 'Catégorie de servitude d''utilité publique (AC1, PM1...)';


--
-- Name: COLUMN sup_generateur_s.geom; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_generateur_s.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: COLUMN sup_generateur_s.gid; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_generateur_s.gid IS 'Identifiant technique';


--
-- Name: mv_indicateurs_commune; Type: MATERIALIZED VIEW; Schema: ref_admin; Owner: -
--

CREATE MATERIALIZED VIEW ref_admin.mv_indicateurs_commune AS
 WITH adr AS (
         SELECT adresse.code_insee,
            count(*) AS nb_adresses,
            round((100.0 * avg((adresse.certification_commune)::integer)), 1) AS adresses_certifiees_pct,
            round((100.0 * avg(((COALESCE(adresse.cad_parcelles, ''::text) <> ''::text))::integer)), 1) AS adresses_liees_parcelle_pct
           FROM ref_adresse.adresse
          GROUP BY adresse.code_insee
        ), parc AS (
         SELECT parcelle.code_insee,
            count(*) AS nb_parcelles
           FROM ref_cadastre.parcelle
          GROUP BY parcelle.code_insee
        ), bati AS (
         SELECT c_1.code_insee,
            count(*) AS nb_batiments,
            sum(b.nombre_de_logements) AS nb_logements
           FROM (ref_topo.batiment b
             JOIN ref_admin.commune c_1 ON (public.st_intersects(c_1.geom, public.st_pointonsurface(b.geom))))
          GROUP BY c_1.code_insee
        ), sans_adr AS (
         SELECT v_batiment_sans_adresse.code_insee,
            count(*) AS logements_sans_adresse
           FROM controle.v_batiment_sans_adresse
          GROUP BY v_batiment_sans_adresse.code_insee
        ), zon AS (
         SELECT zone_urba.code_insee,
            round(((sum(public.st_area(zone_urba.geom)) FILTER (WHERE (zone_urba.typezone = 'U'::text)) / ('10000'::numeric)::double precision))::numeric, 1) AS zone_u_ha,
            round(((sum(public.st_area(zone_urba.geom)) FILTER (WHERE (zone_urba.typezone = ANY (ARRAY['AUc'::text, 'AUs'::text]))) / ('10000'::numeric)::double precision))::numeric, 1) AS zone_au_ha,
            round(((sum(public.st_area(zone_urba.geom)) FILTER (WHERE (zone_urba.typezone = ANY (ARRAY['A'::text, 'Ah'::text]))) / ('10000'::numeric)::double precision))::numeric, 1) AS zone_a_ha,
            round(((sum(public.st_area(zone_urba.geom)) FILTER (WHERE (zone_urba.typezone = ANY (ARRAY['N'::text, 'Nh'::text]))) / ('10000'::numeric)::double precision))::numeric, 1) AS zone_n_ha
           FROM urbanisme.zone_urba
          GROUP BY zone_urba.code_insee
        ), natura AS (
         SELECT c_1.code_insee,
            round(((((100)::double precision * public.st_area(public.st_intersection(c_1.geom, public.st_union(n.geom)))) / public.st_area(c_1.geom)))::numeric, 1) AS natura2000_pct
           FROM (ref_admin.commune c_1
             JOIN environnement.zonage_naturel n ON (((n.type_zonage = ANY (ARRAY['SIC'::text, 'ZPS'::text])) AND public.st_intersects(c_1.geom, n.geom))))
          GROUP BY c_1.code_insee, c_1.geom
        ), znieff AS (
         SELECT c_1.code_insee,
            round(((((100)::double precision * public.st_area(public.st_intersection(c_1.geom, public.st_union(n.geom)))) / public.st_area(c_1.geom)))::numeric, 1) AS znieff_pct
           FROM (ref_admin.commune c_1
             JOIN environnement.zonage_naturel n ON (((n.type_zonage ~~ 'ZNIEFF%'::text) AND public.st_intersects(c_1.geom, n.geom))))
          GROUP BY c_1.code_insee, c_1.geom
        ), ppri AS (
         SELECT c_1.code_insee,
            round(((((100)::double precision * public.st_area(public.st_intersection(c_1.geom, public.st_union(public.st_makevalid(s.geom))))) / public.st_area(c_1.geom)))::numeric, 1) AS ppri_pct
           FROM (ref_admin.commune c_1
             JOIN servitudes.sup_assiette_s s ON (((s.suptype = 'PM1'::text) AND public.st_intersects(c_1.geom, s.geom))))
          GROUP BY c_1.code_insee, c_1.geom
        ), mh AS (
         SELECT c_1.code_insee,
            count(DISTINCT g.idgen) AS nb_monuments_historiques
           FROM (ref_admin.commune c_1
             JOIN servitudes.sup_generateur_s g ON (((g.suptype = 'AC1'::text) AND public.st_intersects(c_1.geom, g.geom))))
          GROUP BY c_1.code_insee
        ), arb AS (
         SELECT arbre.code_insee,
            count(*) AS nb_arbres,
            count(*) FILTER (WHERE (arbre.etat_sanitaire = ANY (ARRAY['deperissant'::text, 'mort'::text]))) AS nb_arbres_degrades
           FROM espaces_verts.arbre
          WHERE (arbre.statut = 'en_place'::text)
          GROUP BY arbre.code_insee
        ), equip AS (
         SELECT c_1.code_insee,
            count(*) FILTER (WHERE (e.categorie = 'Science et enseignement'::text)) AS nb_etablissements_scolaires,
            count(*) FILTER (WHERE (e.categorie = 'Sport'::text)) AS nb_equipements_sportifs
           FROM (ref_topo.equipement e
             JOIN ref_admin.commune c_1 ON (public.st_intersects(c_1.geom, public.st_pointonsurface(e.geom))))
          GROUP BY c_1.code_insee
        )
 SELECT c.code_insee,
    c.nom,
    c.population,
    c.surface_ha,
    round(((c.population)::double precision / NULLIF((c.surface_ha / (100)::double precision), (0)::double precision))) AS densite_hab_km2,
    COALESCE(d.typedoc, 'Non publié'::text) AS document_urbanisme,
    to_date(d.datappro, 'YYYYMMDD'::text) AS date_approbation,
    d.nomproc AS derniere_procedure,
    parc.nb_parcelles,
    bati.nb_batiments,
    bati.nb_logements,
    adr.nb_adresses,
    adr.adresses_certifiees_pct,
    adr.adresses_liees_parcelle_pct,
    COALESCE(sans_adr.logements_sans_adresse, (0)::bigint) AS logements_sans_adresse,
    zon.zone_u_ha,
    zon.zone_au_ha,
    zon.zone_a_ha,
    zon.zone_n_ha,
    COALESCE(natura.natura2000_pct, (0)::numeric) AS natura2000_pct,
    COALESCE(znieff.znieff_pct, (0)::numeric) AS znieff_pct,
    COALESCE(ppri.ppri_pct, (0)::numeric) AS ppri_pct,
    COALESCE(mh.nb_monuments_historiques, (0)::bigint) AS nb_monuments_historiques,
    COALESCE(equip.nb_etablissements_scolaires, (0)::bigint) AS nb_etablissements_scolaires,
    COALESCE(equip.nb_equipements_sportifs, (0)::bigint) AS nb_equipements_sportifs,
    COALESCE(arb.nb_arbres, (0)::bigint) AS nb_arbres,
    COALESCE(arb.nb_arbres_degrades, (0)::bigint) AS nb_arbres_degrades,
    c.geom
   FROM ((((((((((((ref_admin.commune c
     LEFT JOIN urbanisme.doc_urba d USING (code_insee))
     LEFT JOIN adr USING (code_insee))
     LEFT JOIN parc USING (code_insee))
     LEFT JOIN bati USING (code_insee))
     LEFT JOIN sans_adr USING (code_insee))
     LEFT JOIN zon USING (code_insee))
     LEFT JOIN natura USING (code_insee))
     LEFT JOIN znieff USING (code_insee))
     LEFT JOIN ppri USING (code_insee))
     LEFT JOIN mh USING (code_insee))
     LEFT JOIN arb USING (code_insee))
     LEFT JOIN equip USING (code_insee))
  ORDER BY c.code_insee
  WITH NO DATA;


--
-- Name: MATERIALIZED VIEW mv_indicateurs_commune; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON MATERIALIZED VIEW ref_admin.mv_indicateurs_commune IS 'Indicateurs SIG par commune (urbanisme, adressage, environnement, risques, patrimoine arboré)';


--
-- Name: v_indicateurs_commune; Type: VIEW; Schema: diffusion; Owner: -
--

CREATE VIEW diffusion.v_indicateurs_commune AS
 SELECT mv_indicateurs_commune.code_insee,
    mv_indicateurs_commune.nom,
    mv_indicateurs_commune.population,
    mv_indicateurs_commune.surface_ha,
    mv_indicateurs_commune.densite_hab_km2,
    mv_indicateurs_commune.document_urbanisme,
    mv_indicateurs_commune.date_approbation,
    mv_indicateurs_commune.derniere_procedure,
    mv_indicateurs_commune.nb_parcelles,
    mv_indicateurs_commune.nb_batiments,
    mv_indicateurs_commune.nb_logements,
    mv_indicateurs_commune.nb_adresses,
    mv_indicateurs_commune.adresses_certifiees_pct,
    mv_indicateurs_commune.adresses_liees_parcelle_pct,
    mv_indicateurs_commune.logements_sans_adresse,
    mv_indicateurs_commune.zone_u_ha,
    mv_indicateurs_commune.zone_au_ha,
    mv_indicateurs_commune.zone_a_ha,
    mv_indicateurs_commune.zone_n_ha,
    mv_indicateurs_commune.natura2000_pct,
    mv_indicateurs_commune.znieff_pct,
    mv_indicateurs_commune.ppri_pct,
    mv_indicateurs_commune.nb_monuments_historiques,
    mv_indicateurs_commune.nb_etablissements_scolaires,
    mv_indicateurs_commune.nb_equipements_sportifs,
    mv_indicateurs_commune.nb_arbres,
    mv_indicateurs_commune.nb_arbres_degrades,
    mv_indicateurs_commune.geom
   FROM ref_admin.mv_indicateurs_commune;


--
-- Name: v_zone_urba; Type: VIEW; Schema: diffusion; Owner: -
--

CREATE VIEW diffusion.v_zone_urba AS
 SELECT zone_urba.gid,
    zone_urba.code_insee,
    zone_urba.idurba,
    zone_urba.libelle,
    zone_urba.libelong,
    zone_urba.typezone,
    zone_urba.destdomi,
    zone_urba.urlfic,
    zone_urba.geom
   FROM urbanisme.zone_urba;


--
-- Name: zonage_naturel_gid_seq; Type: SEQUENCE; Schema: environnement; Owner: -
--

ALTER TABLE environnement.zonage_naturel ALTER COLUMN gid ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME environnement.zonage_naturel_gid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: intervention; Type: TABLE; Schema: espaces_verts; Owner: -
--

CREATE TABLE espaces_verts.intervention (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    arbre_id uuid NOT NULL,
    type_intervention text NOT NULL,
    date_intervention date NOT NULL,
    intervenant text DEFAULT 'Régie espaces verts'::text NOT NULL,
    cout_ht numeric(10,2),
    etat_constate text,
    commentaire text,
    date_creation timestamp with time zone DEFAULT now() NOT NULL,
    auteur_creation text DEFAULT CURRENT_USER NOT NULL,
    CONSTRAINT intervention_cout_ht_check CHECK ((cout_ht >= (0)::numeric))
);


--
-- Name: TABLE intervention; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON TABLE espaces_verts.intervention IS 'Interventions sur le patrimoine arboré - Historique des diagnostics, tailles, élagages et abattages, avec leur coût.';


--
-- Name: journal; Type: TABLE; Schema: espaces_verts; Owner: -
--

CREATE TABLE espaces_verts.journal (
    id bigint NOT NULL,
    table_nom text NOT NULL,
    objet_id uuid NOT NULL,
    operation text NOT NULL,
    date_op timestamp with time zone DEFAULT now() NOT NULL,
    utilisateur text DEFAULT CURRENT_USER NOT NULL,
    avant jsonb,
    apres jsonb
);


--
-- Name: TABLE journal; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON TABLE espaces_verts.journal IS 'Journal des créations, modifications et suppressions (alimenté par déclencheur)';


--
-- Name: journal_id_seq; Type: SEQUENCE; Schema: espaces_verts; Owner: -
--

ALTER TABLE espaces_verts.journal ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME espaces_verts.journal_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: liste_etat_sanitaire; Type: TABLE; Schema: espaces_verts; Owner: -
--

CREATE TABLE espaces_verts.liste_etat_sanitaire (
    code text NOT NULL,
    libelle text NOT NULL,
    ordre smallint NOT NULL,
    couleur text NOT NULL
);


--
-- Name: liste_implantation; Type: TABLE; Schema: espaces_verts; Owner: -
--

CREATE TABLE espaces_verts.liste_implantation (
    code text NOT NULL,
    libelle text NOT NULL
);


--
-- Name: liste_risque; Type: TABLE; Schema: espaces_verts; Owner: -
--

CREATE TABLE espaces_verts.liste_risque (
    code text NOT NULL,
    libelle text NOT NULL,
    ordre smallint NOT NULL
);


--
-- Name: liste_stade_dev; Type: TABLE; Schema: espaces_verts; Owner: -
--

CREATE TABLE espaces_verts.liste_stade_dev (
    code text NOT NULL,
    libelle text NOT NULL,
    ordre smallint NOT NULL
);


--
-- Name: liste_type_intervention; Type: TABLE; Schema: espaces_verts; Owner: -
--

CREATE TABLE espaces_verts.liste_type_intervention (
    code text NOT NULL,
    libelle text NOT NULL,
    cout_ref numeric(8,2)
);


--
-- Name: seq_numero_arbre; Type: SEQUENCE; Schema: espaces_verts; Owner: -
--

CREATE SEQUENCE espaces_verts.seq_numero_arbre
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: v_arbre; Type: VIEW; Schema: espaces_verts; Owner: -
--

CREATE VIEW espaces_verts.v_arbre AS
 SELECT a.id,
    a.numero,
    a.code_insee,
    c.nom AS commune,
    a.essence,
    e.nom_francais,
    e.genre,
    e.allergisant,
    e.envahissante,
    a.implantation,
    i.libelle AS implantation_libelle,
    a.stade_dev,
    a.hauteur_m,
    a.circonference_cm,
    a.annee_plantation,
    a.etat_sanitaire,
    s.libelle AS etat_libelle,
    s.ordre AS etat_ordre,
    a.risque,
    a.remarquable,
    a.date_diagnostic,
    a.statut,
    der.date_intervention AS derniere_intervention,
    der.type_intervention AS dernier_type_intervention,
    ((a.date_diagnostic IS NULL) OR (a.date_diagnostic < (CURRENT_DATE - '3 years'::interval))) AS diagnostic_a_refaire,
    a.source_geom,
    a.source_attributs,
    a.geom
   FROM (((((espaces_verts.arbre a
     JOIN ref_admin.commune c USING (code_insee))
     JOIN espaces_verts.liste_essence e ON ((e.code = a.essence)))
     LEFT JOIN espaces_verts.liste_implantation i ON ((i.code = a.implantation)))
     LEFT JOIN espaces_verts.liste_etat_sanitaire s ON ((s.code = a.etat_sanitaire)))
     LEFT JOIN LATERAL ( SELECT intervention.date_intervention,
            intervention.type_intervention
           FROM espaces_verts.intervention
          WHERE (intervention.arbre_id = a.id)
          ORDER BY intervention.date_intervention DESC
         LIMIT 1) der ON (true))
  WHERE (a.statut = 'en_place'::text);


--
-- Name: VIEW v_arbre; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON VIEW espaces_verts.v_arbre IS 'Arbres en place avec libellés, dernière intervention et besoin de diagnostic';


--
-- Name: v_arbre_diagnostic_a_programmer; Type: VIEW; Schema: espaces_verts; Owner: -
--

CREATE VIEW espaces_verts.v_arbre_diagnostic_a_programmer AS
 SELECT v.id,
    v.numero,
    v.code_insee,
    v.commune,
    v.essence,
    v.nom_francais,
    v.genre,
    v.allergisant,
    v.envahissante,
    v.implantation,
    v.implantation_libelle,
    v.stade_dev,
    v.hauteur_m,
    v.circonference_cm,
    v.annee_plantation,
    v.etat_sanitaire,
    v.etat_libelle,
    v.etat_ordre,
    v.risque,
    v.remarquable,
    v.date_diagnostic,
    v.statut,
    v.derniere_intervention,
    v.dernier_type_intervention,
    v.diagnostic_a_refaire,
    v.source_geom,
    v.source_attributs,
    v.geom,
    COALESCE((CURRENT_DATE - v.date_diagnostic), 9999) AS jours_depuis_diagnostic
   FROM espaces_verts.v_arbre v
  WHERE v.diagnostic_a_refaire;


--
-- Name: VIEW v_arbre_diagnostic_a_programmer; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON VIEW espaces_verts.v_arbre_diagnostic_a_programmer IS 'Arbres à inscrire au prochain programme de diagnostic sanitaire';


--
-- Name: v_arbre_prioritaire; Type: VIEW; Schema: espaces_verts; Owner: -
--

CREATE VIEW espaces_verts.v_arbre_prioritaire AS
 SELECT v.id,
    v.numero,
    v.code_insee,
    v.commune,
    v.essence,
    v.nom_francais,
    v.genre,
    v.allergisant,
    v.envahissante,
    v.implantation,
    v.implantation_libelle,
    v.stade_dev,
    v.hauteur_m,
    v.circonference_cm,
    v.annee_plantation,
    v.etat_sanitaire,
    v.etat_libelle,
    v.etat_ordre,
    v.risque,
    v.remarquable,
    v.date_diagnostic,
    v.statut,
    v.derniere_intervention,
    v.dernier_type_intervention,
    v.diagnostic_a_refaire,
    v.source_geom,
    v.source_attributs,
    v.geom,
        CASE
            WHEN ((v.etat_sanitaire = 'mort'::text) OR ((v.risque = 'eleve'::text) AND (v.etat_ordre >= 4))) THEN 1
            WHEN ((v.etat_sanitaire = 'deperissant'::text) OR (v.risque = 'eleve'::text)) THEN 2
            ELSE 3
        END AS priorite
   FROM espaces_verts.v_arbre v
  WHERE ((v.etat_sanitaire = ANY (ARRAY['mort'::text, 'deperissant'::text, 'surveiller'::text])) OR (v.risque = 'eleve'::text));


--
-- Name: VIEW v_arbre_prioritaire; Type: COMMENT; Schema: espaces_verts; Owner: -
--

COMMENT ON VIEW espaces_verts.v_arbre_prioritaire IS 'Arbres à traiter : 1 = sécurisation immédiate, 2 = sous 6 mois, 3 = surveillance renforcée';


--
-- Name: v_synthese_commune; Type: VIEW; Schema: espaces_verts; Owner: -
--

CREATE VIEW espaces_verts.v_synthese_commune AS
 SELECT c.code_insee,
    c.nom AS commune,
    count(a.id) AS nb_arbres,
    count(a.id) FILTER (WHERE a.remarquable) AS nb_remarquables,
    count(a.id) FILTER (WHERE (a.etat_sanitaire = ANY (ARRAY['deperissant'::text, 'mort'::text]))) AS nb_degrades,
    round(((100.0 * (count(a.id) FILTER (WHERE (a.etat_sanitaire = ANY (ARRAY['deperissant'::text, 'mort'::text]))))::numeric) / (NULLIF(count(a.id), 0))::numeric), 1) AS part_degrades_pct,
    count(DISTINCT a.essence) AS nb_essences,
    ( SELECT COALESCE(sum(i.cout_ht), (0)::numeric) AS "coalesce"
           FROM (espaces_verts.intervention i
             JOIN espaces_verts.arbre a2 ON ((a2.id = i.arbre_id)))
          WHERE ((a2.code_insee = c.code_insee) AND (i.date_intervention >= date_trunc('year'::text, (CURRENT_DATE)::timestamp with time zone)))) AS cout_annee_en_cours
   FROM (ref_admin.commune c
     LEFT JOIN espaces_verts.arbre a ON (((a.code_insee = c.code_insee) AND (a.statut = 'en_place'::text))))
  GROUP BY c.code_insee, c.nom;


--
-- Name: journal_diffusion; Type: TABLE; Schema: metadonnees; Owner: -
--

CREATE TABLE metadonnees.journal_diffusion (
    id bigint NOT NULL,
    date_diffusion timestamp with time zone DEFAULT now() NOT NULL,
    demandeur text NOT NULL,
    objet text NOT NULL,
    destinataire text NOT NULL,
    communes text[] NOT NULL,
    jeux text[] NOT NULL,
    convention text,
    fichier text NOT NULL,
    utilisateur text DEFAULT CURRENT_USER NOT NULL,
    CONSTRAINT journal_diffusion_destinataire_check CHECK ((destinataire = ANY (ARRAY['externe'::text, 'interne'::text])))
);


--
-- Name: TABLE journal_diffusion; Type: COMMENT; Schema: metadonnees; Owner: -
--

COMMENT ON TABLE metadonnees.journal_diffusion IS 'Registre des extractions remises à des tiers (scripts/extraction.py)';


--
-- Name: journal_diffusion_id_seq; Type: SEQUENCE; Schema: metadonnees; Owner: -
--

ALTER TABLE metadonnees.journal_diffusion ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME metadonnees.journal_diffusion_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: journal_integration; Type: TABLE; Schema: metadonnees; Owner: -
--

CREATE TABLE metadonnees.journal_integration (
    id bigint NOT NULL,
    date_integration timestamp with time zone DEFAULT now() NOT NULL,
    table_nom text NOT NULL,
    nb_objets integer NOT NULL,
    source text,
    script text,
    utilisateur text DEFAULT CURRENT_USER NOT NULL
);


--
-- Name: TABLE journal_integration; Type: COMMENT; Schema: metadonnees; Owner: -
--

COMMENT ON TABLE metadonnees.journal_integration IS 'Historique des intégrations de données (une ligne par chargement)';


--
-- Name: journal_integration_id_seq; Type: SEQUENCE; Schema: metadonnees; Owner: -
--

ALTER TABLE metadonnees.journal_integration ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME metadonnees.journal_integration_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: epci; Type: TABLE; Schema: ref_admin; Owner: -
--

CREATE TABLE ref_admin.epci (
    siren text NOT NULL,
    nom text,
    nb_communes bigint,
    population bigint,
    surface_ha double precision,
    geom public.geometry(MultiPolygon,2154)
);


--
-- Name: TABLE epci; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON TABLE ref_admin.epci IS 'Périmètre intercommunal - Périmètre de la communauté de communes, obtenu par fusion des limites communales.';


--
-- Name: COLUMN epci.nom; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON COLUMN ref_admin.epci.nom IS 'Nom';


--
-- Name: COLUMN epci.population; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON COLUMN ref_admin.epci.population IS 'Population municipale légale (INSEE)';


--
-- Name: COLUMN epci.surface_ha; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON COLUMN ref_admin.epci.surface_ha IS 'Surface calculée (ha, Lambert-93)';


--
-- Name: COLUMN epci.geom; Type: COMMENT; Schema: ref_admin; Owner: -
--

COMMENT ON COLUMN ref_admin.epci.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: cimetiere; Type: TABLE; Schema: ref_topo; Owner: -
--

CREATE TABLE ref_topo.cimetiere (
    cleabs text NOT NULL,
    nature text,
    toponyme text,
    geom public.geometry(MultiPolygon,2154)
);


--
-- Name: TABLE cimetiere; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON TABLE ref_topo.cimetiere IS 'Cimetières - Emprises des cimetières (BD TOPO).';


--
-- Name: COLUMN cimetiere.cleabs; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.cimetiere.cleabs IS 'Identifiant de l''objet dans la BD TOPO';


--
-- Name: COLUMN cimetiere.geom; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.cimetiere.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: surface_hydro; Type: TABLE; Schema: ref_topo; Owner: -
--

CREATE TABLE ref_topo.surface_hydro (
    cleabs text NOT NULL,
    nature text,
    cpx_toponyme_de_plan_d_eau text,
    persistance text,
    geom public.geometry(MultiPolygon,2154)
);


--
-- Name: TABLE surface_hydro; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON TABLE ref_topo.surface_hydro IS 'Surfaces en eau - Plans d''eau et surfaces hydrographiques de la BD TOPO.';


--
-- Name: COLUMN surface_hydro.cleabs; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.surface_hydro.cleabs IS 'Identifiant de l''objet dans la BD TOPO';


--
-- Name: COLUMN surface_hydro.geom; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.surface_hydro.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: terrain_sport; Type: TABLE; Schema: ref_topo; Owner: -
--

CREATE TABLE ref_topo.terrain_sport (
    cleabs text NOT NULL,
    nature text,
    nature_detaillee text,
    geom public.geometry(MultiPolygon,2154)
);


--
-- Name: TABLE terrain_sport; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON TABLE ref_topo.terrain_sport IS 'Terrains de sport - Terrains et équipements sportifs de plein air (BD TOPO).';


--
-- Name: COLUMN terrain_sport.cleabs; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.terrain_sport.cleabs IS 'Identifiant de l''objet dans la BD TOPO';


--
-- Name: COLUMN terrain_sport.geom; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.terrain_sport.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: troncon_hydro; Type: TABLE; Schema: ref_topo; Owner: -
--

CREATE TABLE ref_topo.troncon_hydro (
    cleabs text NOT NULL,
    nature text,
    cpx_toponyme_de_cours_d_eau text,
    persistance text,
    position_par_rapport_au_sol text,
    fictif boolean,
    geom public.geometry(MultiLineString,2154)
);


--
-- Name: TABLE troncon_hydro; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON TABLE ref_topo.troncon_hydro IS 'Cours d''eau - Tronçons hydrographiques de la BD TOPO : Ill, Giessen, Lièpvrette, Blind et cours d''eau phréatiques du Ried.';


--
-- Name: COLUMN troncon_hydro.cleabs; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.troncon_hydro.cleabs IS 'Identifiant de l''objet dans la BD TOPO';


--
-- Name: COLUMN troncon_hydro.geom; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.troncon_hydro.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: troncon_route; Type: TABLE; Schema: ref_topo; Owner: -
--

CREATE TABLE ref_topo.troncon_route (
    cleabs text NOT NULL,
    nature text,
    importance text,
    nom_collaboratif_gauche text,
    nom_collaboratif_droite text,
    cpx_numero text,
    nombre_de_voies double precision,
    largeur_de_chaussee double precision,
    sens_de_circulation text,
    urbain boolean,
    acces_vehicule_leger text,
    prive boolean,
    itineraire_vert boolean,
    position_par_rapport_au_sol text,
    fictif boolean,
    geom public.geometry(MultiLineString,2154)
);


--
-- Name: TABLE troncon_route; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON TABLE ref_topo.troncon_route IS 'Tronçons de route - Réseau routier de la BD TOPO : nature, importance, nom de voie, largeur, sens de circulation.';


--
-- Name: COLUMN troncon_route.cleabs; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.troncon_route.cleabs IS 'Identifiant de l''objet dans la BD TOPO';


--
-- Name: COLUMN troncon_route.geom; Type: COMMENT; Schema: ref_topo; Owner: -
--

COMMENT ON COLUMN ref_topo.troncon_route.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: categorie_sup; Type: TABLE; Schema: servitudes; Owner: -
--

CREATE TABLE servitudes.categorie_sup (
    code text NOT NULL,
    libelle text NOT NULL,
    famille text NOT NULL
);


--
-- Name: TABLE categorie_sup; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON TABLE servitudes.categorie_sup IS 'Nomenclature des catégories de servitudes d''utilité publique';


--
-- Name: COLUMN categorie_sup.libelle; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.categorie_sup.libelle IS 'Libellé court';


--
-- Name: sup_assiette_s_gid_seq; Type: SEQUENCE; Schema: servitudes; Owner: -
--

ALTER TABLE servitudes.sup_assiette_s ALTER COLUMN gid ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME servitudes.sup_assiette_s_gid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: sup_generateur_l; Type: TABLE; Schema: servitudes; Owner: -
--

CREATE TABLE servitudes.sup_generateur_l (
    suptype text,
    partition text,
    idgen text,
    nomsuplitt text,
    fichier text,
    gpu_doc_id text,
    nomgen text,
    typegen text,
    geom public.geometry(MultiLineString,2154),
    gid integer NOT NULL
);


--
-- Name: TABLE sup_generateur_l; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON TABLE servitudes.sup_generateur_l IS 'Servitudes d''utilité publique (générateurs linéaires) - Canalisations, lignes électriques et voies qui génèrent une servitude.';


--
-- Name: COLUMN sup_generateur_l.suptype; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_generateur_l.suptype IS 'Catégorie de servitude d''utilité publique (AC1, PM1...)';


--
-- Name: COLUMN sup_generateur_l.geom; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_generateur_l.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: COLUMN sup_generateur_l.gid; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_generateur_l.gid IS 'Identifiant technique';


--
-- Name: sup_generateur_l_gid_seq; Type: SEQUENCE; Schema: servitudes; Owner: -
--

ALTER TABLE servitudes.sup_generateur_l ALTER COLUMN gid ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME servitudes.sup_generateur_l_gid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: sup_generateur_p; Type: TABLE; Schema: servitudes; Owner: -
--

CREATE TABLE servitudes.sup_generateur_p (
    suptype text,
    partition text,
    idgen text,
    nomsuplitt text,
    fichier text,
    gpu_doc_id text,
    nomgen text,
    typegen text,
    geom public.geometry(MultiPoint,2154),
    gid integer NOT NULL
);


--
-- Name: TABLE sup_generateur_p; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON TABLE servitudes.sup_generateur_p IS 'Servitudes d''utilité publique (générateurs ponctuels) - Objets ponctuels qui génèrent une servitude.';


--
-- Name: COLUMN sup_generateur_p.suptype; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_generateur_p.suptype IS 'Catégorie de servitude d''utilité publique (AC1, PM1...)';


--
-- Name: COLUMN sup_generateur_p.geom; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_generateur_p.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: COLUMN sup_generateur_p.gid; Type: COMMENT; Schema: servitudes; Owner: -
--

COMMENT ON COLUMN servitudes.sup_generateur_p.gid IS 'Identifiant technique';


--
-- Name: sup_generateur_p_gid_seq; Type: SEQUENCE; Schema: servitudes; Owner: -
--

ALTER TABLE servitudes.sup_generateur_p ALTER COLUMN gid ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME servitudes.sup_generateur_p_gid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: sup_generateur_s_gid_seq; Type: SEQUENCE; Schema: servitudes; Owner: -
--

ALTER TABLE servitudes.sup_generateur_s ALTER COLUMN gid ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME servitudes.sup_generateur_s_gid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: v_assiette_s; Type: VIEW; Schema: servitudes; Owner: -
--

CREATE VIEW servitudes.v_assiette_s AS
 SELECT s.gid,
    s.suptype,
    k.libelle AS categorie_libelle,
    k.famille,
    servitudes.nom_lisible(COALESCE(NULLIF(s.nomsuplitt, ''::text), s.nomass)) AS objet,
    s.typeass,
    s.modegeoass,
    s.idgen,
    s.fichier,
    s.geom
   FROM (servitudes.sup_assiette_s s
     LEFT JOIN servitudes.categorie_sup k ON ((k.code = s.suptype)));


--
-- Name: v_generateur_s; Type: VIEW; Schema: servitudes; Owner: -
--

CREATE VIEW servitudes.v_generateur_s AS
 SELECT g.gid,
    g.suptype,
    k.libelle AS categorie_libelle,
    servitudes.nom_lisible(g.nomgen) AS objet,
    g.typegen,
    g.idgen,
    g.geom
   FROM (servitudes.sup_generateur_s g
     LEFT JOIN servitudes.categorie_sup k ON ((k.code = g.suptype)));


--
-- Name: info_surf; Type: TABLE; Schema: urbanisme; Owner: -
--

CREATE TABLE urbanisme.info_surf (
    partition text,
    idurba text,
    libelle text,
    txt text,
    typeinf text,
    stypeinf text,
    nomfic text,
    urlfic text,
    datvalid text,
    gpu_doc_id text,
    code_insee text,
    url_reglement text,
    geom public.geometry(MultiPolygon,2154),
    gid integer NOT NULL
);


--
-- Name: TABLE info_surf; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON TABLE urbanisme.info_surf IS 'Informations surfaciques des PLU - Périmètres reportés à titre d''information (droit de préemption, risques, ZAC...).';


--
-- Name: COLUMN info_surf.idurba; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.info_surf.idurba IS 'Identifiant du document d''urbanisme (standard CNIG)';


--
-- Name: COLUMN info_surf.libelle; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.info_surf.libelle IS 'Libellé court';


--
-- Name: COLUMN info_surf.typeinf; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.info_surf.typeinf IS 'Type d''information (nomenclature CNIG)';


--
-- Name: COLUMN info_surf.code_insee; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.info_surf.code_insee IS 'Code officiel géographique de la commune (INSEE)';


--
-- Name: COLUMN info_surf.url_reglement; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.info_surf.url_reglement IS 'Lien vers le règlement écrit (pièce déposée au GPU)';


--
-- Name: COLUMN info_surf.geom; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.info_surf.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: COLUMN info_surf.gid; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.info_surf.gid IS 'Identifiant technique';


--
-- Name: info_surf_gid_seq; Type: SEQUENCE; Schema: urbanisme; Owner: -
--

ALTER TABLE urbanisme.info_surf ALTER COLUMN gid ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME urbanisme.info_surf_gid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: prescription_lin; Type: TABLE; Schema: urbanisme; Owner: -
--

CREATE TABLE urbanisme.prescription_lin (
    partition text,
    idurba text,
    libelle text,
    txt text,
    typepsc text,
    stypepsc text,
    nomfic text,
    urlfic text,
    datvalid text,
    gpu_doc_id text,
    code_insee text,
    url_reglement text,
    geom public.geometry(MultiLineString,2154),
    gid integer NOT NULL
);


--
-- Name: TABLE prescription_lin; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON TABLE urbanisme.prescription_lin IS 'Prescriptions linéaires des PLU - Linéaires protégés (haies, alignements, commerces), reculs et marges graphiques.';


--
-- Name: COLUMN prescription_lin.idurba; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_lin.idurba IS 'Identifiant du document d''urbanisme (standard CNIG)';


--
-- Name: COLUMN prescription_lin.libelle; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_lin.libelle IS 'Libellé court';


--
-- Name: COLUMN prescription_lin.typepsc; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_lin.typepsc IS 'Type de prescription (nomenclature CNIG)';


--
-- Name: COLUMN prescription_lin.code_insee; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_lin.code_insee IS 'Code officiel géographique de la commune (INSEE)';


--
-- Name: COLUMN prescription_lin.url_reglement; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_lin.url_reglement IS 'Lien vers le règlement écrit (pièce déposée au GPU)';


--
-- Name: COLUMN prescription_lin.geom; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_lin.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: COLUMN prescription_lin.gid; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_lin.gid IS 'Identifiant technique';


--
-- Name: prescription_lin_gid_seq; Type: SEQUENCE; Schema: urbanisme; Owner: -
--

ALTER TABLE urbanisme.prescription_lin ALTER COLUMN gid ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME urbanisme.prescription_lin_gid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: prescription_pct; Type: TABLE; Schema: urbanisme; Owner: -
--

CREATE TABLE urbanisme.prescription_pct (
    partition text,
    idurba text,
    libelle text,
    txt text,
    typepsc text,
    stypepsc text,
    nomfic text,
    urlfic text,
    datvalid text,
    gpu_doc_id text,
    code_insee text,
    url_reglement text,
    geom public.geometry(MultiPoint,2154),
    gid integer NOT NULL
);


--
-- Name: TABLE prescription_pct; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON TABLE urbanisme.prescription_pct IS 'Prescriptions ponctuelles des PLU - Éléments ponctuels protégés (arbres remarquables, petit patrimoine).';


--
-- Name: COLUMN prescription_pct.idurba; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_pct.idurba IS 'Identifiant du document d''urbanisme (standard CNIG)';


--
-- Name: COLUMN prescription_pct.libelle; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_pct.libelle IS 'Libellé court';


--
-- Name: COLUMN prescription_pct.typepsc; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_pct.typepsc IS 'Type de prescription (nomenclature CNIG)';


--
-- Name: COLUMN prescription_pct.code_insee; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_pct.code_insee IS 'Code officiel géographique de la commune (INSEE)';


--
-- Name: COLUMN prescription_pct.url_reglement; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_pct.url_reglement IS 'Lien vers le règlement écrit (pièce déposée au GPU)';


--
-- Name: COLUMN prescription_pct.geom; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_pct.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: COLUMN prescription_pct.gid; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_pct.gid IS 'Identifiant technique';


--
-- Name: prescription_pct_gid_seq; Type: SEQUENCE; Schema: urbanisme; Owner: -
--

ALTER TABLE urbanisme.prescription_pct ALTER COLUMN gid ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME urbanisme.prescription_pct_gid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: prescription_surf; Type: TABLE; Schema: urbanisme; Owner: -
--

CREATE TABLE urbanisme.prescription_surf (
    partition text,
    idurba text,
    libelle text,
    txt text,
    typepsc text,
    stypepsc text,
    nomfic text,
    urlfic text,
    datvalid text,
    gpu_doc_id text,
    code_insee text,
    url_reglement text,
    geom public.geometry(MultiPolygon,2154),
    gid integer NOT NULL
);


--
-- Name: TABLE prescription_surf; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON TABLE urbanisme.prescription_surf IS 'Prescriptions surfaciques des PLU - Espaces boisés classés, éléments de paysage protégés, emplacements réservés, secteurs d''OAP...';


--
-- Name: COLUMN prescription_surf.idurba; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_surf.idurba IS 'Identifiant du document d''urbanisme (standard CNIG)';


--
-- Name: COLUMN prescription_surf.libelle; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_surf.libelle IS 'Libellé court';


--
-- Name: COLUMN prescription_surf.typepsc; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_surf.typepsc IS 'Type de prescription (nomenclature CNIG)';


--
-- Name: COLUMN prescription_surf.code_insee; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_surf.code_insee IS 'Code officiel géographique de la commune (INSEE)';


--
-- Name: COLUMN prescription_surf.url_reglement; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_surf.url_reglement IS 'Lien vers le règlement écrit (pièce déposée au GPU)';


--
-- Name: COLUMN prescription_surf.geom; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_surf.geom IS 'Géométrie (Lambert-93, EPSG:2154)';


--
-- Name: COLUMN prescription_surf.gid; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.prescription_surf.gid IS 'Identifiant technique';


--
-- Name: prescription_surf_gid_seq; Type: SEQUENCE; Schema: urbanisme; Owner: -
--

ALTER TABLE urbanisme.prescription_surf ALTER COLUMN gid ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME urbanisme.prescription_surf_gid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: type_information; Type: TABLE; Schema: urbanisme; Owner: -
--

CREATE TABLE urbanisme.type_information (
    code text NOT NULL,
    libelle text NOT NULL
);


--
-- Name: COLUMN type_information.libelle; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.type_information.libelle IS 'Libellé court';


--
-- Name: type_prescription; Type: TABLE; Schema: urbanisme; Owner: -
--

CREATE TABLE urbanisme.type_prescription (
    code text NOT NULL,
    libelle text NOT NULL
);


--
-- Name: COLUMN type_prescription.libelle; Type: COMMENT; Schema: urbanisme; Owner: -
--

COMMENT ON COLUMN urbanisme.type_prescription.libelle IS 'Libellé court';


--
-- Name: v_synthese_zonage; Type: VIEW; Schema: urbanisme; Owner: -
--

CREATE VIEW urbanisme.v_synthese_zonage AS
 SELECT c.code_insee,
    c.nom AS commune,
    d.typedoc,
    d.datappro,
    round(((sum(public.st_area(z.geom)) FILTER (WHERE (z.typezone = 'U'::text)) / ('10000'::numeric)::double precision))::numeric, 1) AS u_ha,
    round(((sum(public.st_area(z.geom)) FILTER (WHERE (z.typezone ~~ 'AU%'::text)) / ('10000'::numeric)::double precision))::numeric, 1) AS au_ha,
    round(((sum(public.st_area(z.geom)) FILTER (WHERE ((z.typezone ~~ 'A%'::text) AND (z.typezone !~~ 'AU%'::text))) / ('10000'::numeric)::double precision))::numeric, 1) AS a_ha,
    round(((sum(public.st_area(z.geom)) FILTER (WHERE (z.typezone ~~ 'N%'::text)) / ('10000'::numeric)::double precision))::numeric, 1) AS n_ha
   FROM ((ref_admin.commune c
     LEFT JOIN urbanisme.doc_urba d USING (code_insee))
     LEFT JOIN urbanisme.zone_urba z USING (code_insee))
  GROUP BY c.code_insee, c.nom, d.typedoc, d.datappro;


--
-- Name: zone_urba_gid_seq; Type: SEQUENCE; Schema: urbanisme; Owner: -
--

ALTER TABLE urbanisme.zone_urba ALTER COLUMN gid ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME urbanisme.zone_urba_gid_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: zonage_naturel zonage_naturel_pkey; Type: CONSTRAINT; Schema: environnement; Owner: -
--

ALTER TABLE ONLY environnement.zonage_naturel
    ADD CONSTRAINT zonage_naturel_pkey PRIMARY KEY (gid);


--
-- Name: arbre arbre_numero_key; Type: CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.arbre
    ADD CONSTRAINT arbre_numero_key UNIQUE (numero);


--
-- Name: arbre arbre_pkey; Type: CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.arbre
    ADD CONSTRAINT arbre_pkey PRIMARY KEY (id);


--
-- Name: intervention intervention_pkey; Type: CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.intervention
    ADD CONSTRAINT intervention_pkey PRIMARY KEY (id);


--
-- Name: journal journal_pkey; Type: CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.journal
    ADD CONSTRAINT journal_pkey PRIMARY KEY (id);


--
-- Name: liste_essence liste_essence_pkey; Type: CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.liste_essence
    ADD CONSTRAINT liste_essence_pkey PRIMARY KEY (code);


--
-- Name: liste_etat_sanitaire liste_etat_sanitaire_pkey; Type: CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.liste_etat_sanitaire
    ADD CONSTRAINT liste_etat_sanitaire_pkey PRIMARY KEY (code);


--
-- Name: liste_implantation liste_implantation_pkey; Type: CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.liste_implantation
    ADD CONSTRAINT liste_implantation_pkey PRIMARY KEY (code);


--
-- Name: liste_risque liste_risque_pkey; Type: CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.liste_risque
    ADD CONSTRAINT liste_risque_pkey PRIMARY KEY (code);


--
-- Name: liste_stade_dev liste_stade_dev_pkey; Type: CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.liste_stade_dev
    ADD CONSTRAINT liste_stade_dev_pkey PRIMARY KEY (code);


--
-- Name: liste_type_intervention liste_type_intervention_pkey; Type: CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.liste_type_intervention
    ADD CONSTRAINT liste_type_intervention_pkey PRIMARY KEY (code);


--
-- Name: fiche fiche_pkey; Type: CONSTRAINT; Schema: metadonnees; Owner: -
--

ALTER TABLE ONLY metadonnees.fiche
    ADD CONSTRAINT fiche_pkey PRIMARY KEY (identifiant);


--
-- Name: fiche fiche_table_nom_key; Type: CONSTRAINT; Schema: metadonnees; Owner: -
--

ALTER TABLE ONLY metadonnees.fiche
    ADD CONSTRAINT fiche_table_nom_key UNIQUE (table_nom);


--
-- Name: journal_diffusion journal_diffusion_pkey; Type: CONSTRAINT; Schema: metadonnees; Owner: -
--

ALTER TABLE ONLY metadonnees.journal_diffusion
    ADD CONSTRAINT journal_diffusion_pkey PRIMARY KEY (id);


--
-- Name: journal_integration journal_integration_pkey; Type: CONSTRAINT; Schema: metadonnees; Owner: -
--

ALTER TABLE ONLY metadonnees.journal_integration
    ADD CONSTRAINT journal_integration_pkey PRIMARY KEY (id);


--
-- Name: commune commune_pkey; Type: CONSTRAINT; Schema: ref_admin; Owner: -
--

ALTER TABLE ONLY ref_admin.commune
    ADD CONSTRAINT commune_pkey PRIMARY KEY (code_insee);


--
-- Name: epci epci_pkey; Type: CONSTRAINT; Schema: ref_admin; Owner: -
--

ALTER TABLE ONLY ref_admin.epci
    ADD CONSTRAINT epci_pkey PRIMARY KEY (siren);


--
-- Name: adresse adresse_pkey; Type: CONSTRAINT; Schema: ref_adresse; Owner: -
--

ALTER TABLE ONLY ref_adresse.adresse
    ADD CONSTRAINT adresse_pkey PRIMARY KEY (cle_interop);


--
-- Name: parcelle parcelle_pkey; Type: CONSTRAINT; Schema: ref_cadastre; Owner: -
--

ALTER TABLE ONLY ref_cadastre.parcelle
    ADD CONSTRAINT parcelle_pkey PRIMARY KEY (idu);


--
-- Name: batiment batiment_pkey; Type: CONSTRAINT; Schema: ref_topo; Owner: -
--

ALTER TABLE ONLY ref_topo.batiment
    ADD CONSTRAINT batiment_pkey PRIMARY KEY (cleabs);


--
-- Name: cimetiere cimetiere_pkey; Type: CONSTRAINT; Schema: ref_topo; Owner: -
--

ALTER TABLE ONLY ref_topo.cimetiere
    ADD CONSTRAINT cimetiere_pkey PRIMARY KEY (cleabs);


--
-- Name: equipement equipement_pkey; Type: CONSTRAINT; Schema: ref_topo; Owner: -
--

ALTER TABLE ONLY ref_topo.equipement
    ADD CONSTRAINT equipement_pkey PRIMARY KEY (cleabs);


--
-- Name: surface_hydro surface_hydro_pkey; Type: CONSTRAINT; Schema: ref_topo; Owner: -
--

ALTER TABLE ONLY ref_topo.surface_hydro
    ADD CONSTRAINT surface_hydro_pkey PRIMARY KEY (cleabs);


--
-- Name: terrain_sport terrain_sport_pkey; Type: CONSTRAINT; Schema: ref_topo; Owner: -
--

ALTER TABLE ONLY ref_topo.terrain_sport
    ADD CONSTRAINT terrain_sport_pkey PRIMARY KEY (cleabs);


--
-- Name: troncon_hydro troncon_hydro_pkey; Type: CONSTRAINT; Schema: ref_topo; Owner: -
--

ALTER TABLE ONLY ref_topo.troncon_hydro
    ADD CONSTRAINT troncon_hydro_pkey PRIMARY KEY (cleabs);


--
-- Name: troncon_route troncon_route_pkey; Type: CONSTRAINT; Schema: ref_topo; Owner: -
--

ALTER TABLE ONLY ref_topo.troncon_route
    ADD CONSTRAINT troncon_route_pkey PRIMARY KEY (cleabs);


--
-- Name: categorie_sup categorie_sup_pkey; Type: CONSTRAINT; Schema: servitudes; Owner: -
--

ALTER TABLE ONLY servitudes.categorie_sup
    ADD CONSTRAINT categorie_sup_pkey PRIMARY KEY (code);


--
-- Name: sup_assiette_s sup_assiette_s_pkey; Type: CONSTRAINT; Schema: servitudes; Owner: -
--

ALTER TABLE ONLY servitudes.sup_assiette_s
    ADD CONSTRAINT sup_assiette_s_pkey PRIMARY KEY (gid);


--
-- Name: sup_generateur_l sup_generateur_l_pkey; Type: CONSTRAINT; Schema: servitudes; Owner: -
--

ALTER TABLE ONLY servitudes.sup_generateur_l
    ADD CONSTRAINT sup_generateur_l_pkey PRIMARY KEY (gid);


--
-- Name: sup_generateur_p sup_generateur_p_pkey; Type: CONSTRAINT; Schema: servitudes; Owner: -
--

ALTER TABLE ONLY servitudes.sup_generateur_p
    ADD CONSTRAINT sup_generateur_p_pkey PRIMARY KEY (gid);


--
-- Name: sup_generateur_s sup_generateur_s_pkey; Type: CONSTRAINT; Schema: servitudes; Owner: -
--

ALTER TABLE ONLY servitudes.sup_generateur_s
    ADD CONSTRAINT sup_generateur_s_pkey PRIMARY KEY (gid);


--
-- Name: doc_urba doc_urba_pkey; Type: CONSTRAINT; Schema: urbanisme; Owner: -
--

ALTER TABLE ONLY urbanisme.doc_urba
    ADD CONSTRAINT doc_urba_pkey PRIMARY KEY (code_insee);


--
-- Name: info_surf info_surf_pkey; Type: CONSTRAINT; Schema: urbanisme; Owner: -
--

ALTER TABLE ONLY urbanisme.info_surf
    ADD CONSTRAINT info_surf_pkey PRIMARY KEY (gid);


--
-- Name: prescription_lin prescription_lin_pkey; Type: CONSTRAINT; Schema: urbanisme; Owner: -
--

ALTER TABLE ONLY urbanisme.prescription_lin
    ADD CONSTRAINT prescription_lin_pkey PRIMARY KEY (gid);


--
-- Name: prescription_pct prescription_pct_pkey; Type: CONSTRAINT; Schema: urbanisme; Owner: -
--

ALTER TABLE ONLY urbanisme.prescription_pct
    ADD CONSTRAINT prescription_pct_pkey PRIMARY KEY (gid);


--
-- Name: prescription_surf prescription_surf_pkey; Type: CONSTRAINT; Schema: urbanisme; Owner: -
--

ALTER TABLE ONLY urbanisme.prescription_surf
    ADD CONSTRAINT prescription_surf_pkey PRIMARY KEY (gid);


--
-- Name: type_information type_information_pkey; Type: CONSTRAINT; Schema: urbanisme; Owner: -
--

ALTER TABLE ONLY urbanisme.type_information
    ADD CONSTRAINT type_information_pkey PRIMARY KEY (code);


--
-- Name: type_prescription type_prescription_pkey; Type: CONSTRAINT; Schema: urbanisme; Owner: -
--

ALTER TABLE ONLY urbanisme.type_prescription
    ADD CONSTRAINT type_prescription_pkey PRIMARY KEY (code);


--
-- Name: zone_urba zone_urba_pkey; Type: CONSTRAINT; Schema: urbanisme; Owner: -
--

ALTER TABLE ONLY urbanisme.zone_urba
    ADD CONSTRAINT zone_urba_pkey PRIMARY KEY (gid);


--
-- Name: idx_zonage_naturel_geom; Type: INDEX; Schema: environnement; Owner: -
--

CREATE INDEX idx_zonage_naturel_geom ON environnement.zonage_naturel USING gist (geom);


--
-- Name: arbre_code_insee_idx; Type: INDEX; Schema: espaces_verts; Owner: -
--

CREATE INDEX arbre_code_insee_idx ON espaces_verts.arbre USING btree (code_insee);


--
-- Name: arbre_etat_idx; Type: INDEX; Schema: espaces_verts; Owner: -
--

CREATE INDEX arbre_etat_idx ON espaces_verts.arbre USING btree (etat_sanitaire);


--
-- Name: arbre_geom_idx; Type: INDEX; Schema: espaces_verts; Owner: -
--

CREATE INDEX arbre_geom_idx ON espaces_verts.arbre USING gist (geom);


--
-- Name: intervention_arbre_idx; Type: INDEX; Schema: espaces_verts; Owner: -
--

CREATE INDEX intervention_arbre_idx ON espaces_verts.intervention USING btree (arbre_id);


--
-- Name: journal_objet_idx; Type: INDEX; Schema: espaces_verts; Owner: -
--

CREATE INDEX journal_objet_idx ON espaces_verts.journal USING btree (objet_id);


--
-- Name: idx_commune_geom; Type: INDEX; Schema: ref_admin; Owner: -
--

CREATE INDEX idx_commune_geom ON ref_admin.commune USING gist (geom);


--
-- Name: idx_epci_geom; Type: INDEX; Schema: ref_admin; Owner: -
--

CREATE INDEX idx_epci_geom ON ref_admin.epci USING gist (geom);


--
-- Name: mv_indicateurs_commune_insee; Type: INDEX; Schema: ref_admin; Owner: -
--

CREATE UNIQUE INDEX mv_indicateurs_commune_insee ON ref_admin.mv_indicateurs_commune USING btree (code_insee);


--
-- Name: adresse_code_insee_idx; Type: INDEX; Schema: ref_adresse; Owner: -
--

CREATE INDEX adresse_code_insee_idx ON ref_adresse.adresse USING btree (code_insee);


--
-- Name: adresse_voie_trgm_idx; Type: INDEX; Schema: ref_adresse; Owner: -
--

CREATE INDEX adresse_voie_trgm_idx ON ref_adresse.adresse USING gin (lower(nom_voie) public.gin_trgm_ops);


--
-- Name: idx_adresse_geom; Type: INDEX; Schema: ref_adresse; Owner: -
--

CREATE INDEX idx_adresse_geom ON ref_adresse.adresse USING gist (geom);


--
-- Name: idx_parcelle_geom; Type: INDEX; Schema: ref_cadastre; Owner: -
--

CREATE INDEX idx_parcelle_geom ON ref_cadastre.parcelle USING gist (geom);


--
-- Name: parcelle_code_insee_idx; Type: INDEX; Schema: ref_cadastre; Owner: -
--

CREATE INDEX parcelle_code_insee_idx ON ref_cadastre.parcelle USING btree (code_insee);


--
-- Name: parcelle_section_idx; Type: INDEX; Schema: ref_cadastre; Owner: -
--

CREATE INDEX parcelle_section_idx ON ref_cadastre.parcelle USING btree (code_insee, section, numero);


--
-- Name: batiment_usage_idx; Type: INDEX; Schema: ref_topo; Owner: -
--

CREATE INDEX batiment_usage_idx ON ref_topo.batiment USING btree (usage_1);


--
-- Name: idx_batiment_geom; Type: INDEX; Schema: ref_topo; Owner: -
--

CREATE INDEX idx_batiment_geom ON ref_topo.batiment USING gist (geom);


--
-- Name: idx_cimetiere_geom; Type: INDEX; Schema: ref_topo; Owner: -
--

CREATE INDEX idx_cimetiere_geom ON ref_topo.cimetiere USING gist (geom);


--
-- Name: idx_equipement_geom; Type: INDEX; Schema: ref_topo; Owner: -
--

CREATE INDEX idx_equipement_geom ON ref_topo.equipement USING gist (geom);


--
-- Name: idx_surface_hydro_geom; Type: INDEX; Schema: ref_topo; Owner: -
--

CREATE INDEX idx_surface_hydro_geom ON ref_topo.surface_hydro USING gist (geom);


--
-- Name: idx_terrain_sport_geom; Type: INDEX; Schema: ref_topo; Owner: -
--

CREATE INDEX idx_terrain_sport_geom ON ref_topo.terrain_sport USING gist (geom);


--
-- Name: idx_troncon_hydro_geom; Type: INDEX; Schema: ref_topo; Owner: -
--

CREATE INDEX idx_troncon_hydro_geom ON ref_topo.troncon_hydro USING gist (geom);


--
-- Name: idx_troncon_route_geom; Type: INDEX; Schema: ref_topo; Owner: -
--

CREATE INDEX idx_troncon_route_geom ON ref_topo.troncon_route USING gist (geom);


--
-- Name: idx_sup_assiette_s_geom; Type: INDEX; Schema: servitudes; Owner: -
--

CREATE INDEX idx_sup_assiette_s_geom ON servitudes.sup_assiette_s USING gist (geom);


--
-- Name: idx_sup_generateur_l_geom; Type: INDEX; Schema: servitudes; Owner: -
--

CREATE INDEX idx_sup_generateur_l_geom ON servitudes.sup_generateur_l USING gist (geom);


--
-- Name: idx_sup_generateur_p_geom; Type: INDEX; Schema: servitudes; Owner: -
--

CREATE INDEX idx_sup_generateur_p_geom ON servitudes.sup_generateur_p USING gist (geom);


--
-- Name: idx_sup_generateur_s_geom; Type: INDEX; Schema: servitudes; Owner: -
--

CREATE INDEX idx_sup_generateur_s_geom ON servitudes.sup_generateur_s USING gist (geom);


--
-- Name: idx_info_surf_geom; Type: INDEX; Schema: urbanisme; Owner: -
--

CREATE INDEX idx_info_surf_geom ON urbanisme.info_surf USING gist (geom);


--
-- Name: idx_prescription_lin_geom; Type: INDEX; Schema: urbanisme; Owner: -
--

CREATE INDEX idx_prescription_lin_geom ON urbanisme.prescription_lin USING gist (geom);


--
-- Name: idx_prescription_pct_geom; Type: INDEX; Schema: urbanisme; Owner: -
--

CREATE INDEX idx_prescription_pct_geom ON urbanisme.prescription_pct USING gist (geom);


--
-- Name: idx_prescription_surf_geom; Type: INDEX; Schema: urbanisme; Owner: -
--

CREATE INDEX idx_prescription_surf_geom ON urbanisme.prescription_surf USING gist (geom);


--
-- Name: idx_zone_urba_geom; Type: INDEX; Schema: urbanisme; Owner: -
--

CREATE INDEX idx_zone_urba_geom ON urbanisme.zone_urba USING gist (geom);


--
-- Name: mv_parcelle_zonage_idu; Type: INDEX; Schema: urbanisme; Owner: -
--

CREATE UNIQUE INDEX mv_parcelle_zonage_idu ON urbanisme.mv_parcelle_zonage USING btree (idu);


--
-- Name: zone_urba_code_insee_idx; Type: INDEX; Schema: urbanisme; Owner: -
--

CREATE INDEX zone_urba_code_insee_idx ON urbanisme.zone_urba USING btree (code_insee);


--
-- Name: arbre arbre_avant; Type: TRIGGER; Schema: espaces_verts; Owner: -
--

CREATE TRIGGER arbre_avant BEFORE INSERT OR UPDATE ON espaces_verts.arbre FOR EACH ROW EXECUTE FUNCTION espaces_verts.tg_arbre_avant();


--
-- Name: arbre arbre_journal; Type: TRIGGER; Schema: espaces_verts; Owner: -
--

CREATE TRIGGER arbre_journal AFTER INSERT OR DELETE OR UPDATE ON espaces_verts.arbre FOR EACH ROW EXECUTE FUNCTION espaces_verts.tg_journal();


--
-- Name: intervention intervention_apres; Type: TRIGGER; Schema: espaces_verts; Owner: -
--

CREATE TRIGGER intervention_apres AFTER INSERT ON espaces_verts.intervention FOR EACH ROW EXECUTE FUNCTION espaces_verts.tg_intervention_apres();


--
-- Name: intervention intervention_journal; Type: TRIGGER; Schema: espaces_verts; Owner: -
--

CREATE TRIGGER intervention_journal AFTER INSERT OR DELETE OR UPDATE ON espaces_verts.intervention FOR EACH ROW EXECUTE FUNCTION espaces_verts.tg_journal();


--
-- Name: arbre arbre_code_insee_fkey; Type: FK CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.arbre
    ADD CONSTRAINT arbre_code_insee_fkey FOREIGN KEY (code_insee) REFERENCES ref_admin.commune(code_insee);


--
-- Name: arbre arbre_essence_fkey; Type: FK CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.arbre
    ADD CONSTRAINT arbre_essence_fkey FOREIGN KEY (essence) REFERENCES espaces_verts.liste_essence(code);


--
-- Name: arbre arbre_etat_sanitaire_fkey; Type: FK CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.arbre
    ADD CONSTRAINT arbre_etat_sanitaire_fkey FOREIGN KEY (etat_sanitaire) REFERENCES espaces_verts.liste_etat_sanitaire(code);


--
-- Name: arbre arbre_implantation_fkey; Type: FK CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.arbre
    ADD CONSTRAINT arbre_implantation_fkey FOREIGN KEY (implantation) REFERENCES espaces_verts.liste_implantation(code);


--
-- Name: arbre arbre_risque_fkey; Type: FK CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.arbre
    ADD CONSTRAINT arbre_risque_fkey FOREIGN KEY (risque) REFERENCES espaces_verts.liste_risque(code);


--
-- Name: arbre arbre_stade_dev_fkey; Type: FK CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.arbre
    ADD CONSTRAINT arbre_stade_dev_fkey FOREIGN KEY (stade_dev) REFERENCES espaces_verts.liste_stade_dev(code);


--
-- Name: intervention intervention_arbre_id_fkey; Type: FK CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.intervention
    ADD CONSTRAINT intervention_arbre_id_fkey FOREIGN KEY (arbre_id) REFERENCES espaces_verts.arbre(id) ON DELETE CASCADE;


--
-- Name: intervention intervention_etat_constate_fkey; Type: FK CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.intervention
    ADD CONSTRAINT intervention_etat_constate_fkey FOREIGN KEY (etat_constate) REFERENCES espaces_verts.liste_etat_sanitaire(code);


--
-- Name: intervention intervention_type_intervention_fkey; Type: FK CONSTRAINT; Schema: espaces_verts; Owner: -
--

ALTER TABLE ONLY espaces_verts.intervention
    ADD CONSTRAINT intervention_type_intervention_fkey FOREIGN KEY (type_intervention) REFERENCES espaces_verts.liste_type_intervention(code);


--
-- Name: adresse adresse_commune_fk; Type: FK CONSTRAINT; Schema: ref_adresse; Owner: -
--

ALTER TABLE ONLY ref_adresse.adresse
    ADD CONSTRAINT adresse_commune_fk FOREIGN KEY (code_insee) REFERENCES ref_admin.commune(code_insee);


--
-- Name: parcelle parcelle_commune_fk; Type: FK CONSTRAINT; Schema: ref_cadastre; Owner: -
--

ALTER TABLE ONLY ref_cadastre.parcelle
    ADD CONSTRAINT parcelle_commune_fk FOREIGN KEY (code_insee) REFERENCES ref_admin.commune(code_insee);


--
-- Name: doc_urba doc_urba_commune_fk; Type: FK CONSTRAINT; Schema: urbanisme; Owner: -
--

ALTER TABLE ONLY urbanisme.doc_urba
    ADD CONSTRAINT doc_urba_commune_fk FOREIGN KEY (code_insee) REFERENCES ref_admin.commune(code_insee);


--
-- Name: zone_urba zone_urba_doc_fk; Type: FK CONSTRAINT; Schema: urbanisme; Owner: -
--

ALTER TABLE ONLY urbanisme.zone_urba
    ADD CONSTRAINT zone_urba_doc_fk FOREIGN KEY (code_insee) REFERENCES urbanisme.doc_urba(code_insee);


--
-- PostgreSQL database dump complete
--

