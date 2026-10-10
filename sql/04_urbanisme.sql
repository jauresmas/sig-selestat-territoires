-- =============================================================================
-- Socle SIG intercommunal - 04. Urbanisme : zonage par parcelle et fiche parcelle
-- La fiche parcelle rassemble en une requête ce qu'un instructeur ADS
-- (Cart@DS) ou un agent d'accueil cherche pour renseigner un administré.
-- =============================================================================

-- Zonage dominant de chaque parcelle : sert aux statistiques, à l'atlas et
-- aux contrôles (parcelles hors zonage). Rafraîchi après chaque intégration.
DROP MATERIALIZED VIEW IF EXISTS urbanisme.mv_parcelle_zonage CASCADE;
CREATE MATERIALIZED VIEW urbanisme.mv_parcelle_zonage AS
WITH inter AS (
    SELECT p.idu, p.code_insee, z.libelle, z.typezone,
           ST_Area(ST_Intersection(p.geom, z.geom)) AS surf
    FROM ref_cadastre.parcelle p
    JOIN urbanisme.zone_urba z
      ON z.code_insee = p.code_insee AND ST_Intersects(p.geom, z.geom)
)
SELECT DISTINCT ON (p.idu)
       p.idu, p.code_insee, i.libelle AS zone, i.typezone,
       round((100 * i.surf / nullif(ST_Area(p.geom), 0))::numeric, 1) AS part_pct,
       ST_Area(p.geom) AS surface_m2
FROM ref_cadastre.parcelle p
LEFT JOIN inter i ON i.idu = p.idu
ORDER BY p.idu, i.surf DESC NULLS LAST;

CREATE UNIQUE INDEX mv_parcelle_zonage_idu ON urbanisme.mv_parcelle_zonage (idu);
COMMENT ON MATERIALIZED VIEW urbanisme.mv_parcelle_zonage IS
    'Zone du PLU majoritaire sur chaque parcelle (NULL si la commune n''a pas de document publié sur le GPU)';

-- Synthèse du zonage par commune (hectares par grande famille de zones)
CREATE OR REPLACE VIEW urbanisme.v_synthese_zonage AS
SELECT c.code_insee, c.nom AS commune, d.typedoc, d.datappro,
       round((sum(ST_Area(z.geom)) FILTER (WHERE z.typezone = 'U') / 1e4)::numeric, 1) AS u_ha,
       round((sum(ST_Area(z.geom)) FILTER (WHERE z.typezone LIKE 'AU%') / 1e4)::numeric, 1) AS au_ha,
       round((sum(ST_Area(z.geom)) FILTER (WHERE z.typezone LIKE 'A%' AND z.typezone NOT LIKE 'AU%') / 1e4)::numeric, 1) AS a_ha,
       round((sum(ST_Area(z.geom)) FILTER (WHERE z.typezone LIKE 'N%') / 1e4)::numeric, 1) AS n_ha
FROM ref_admin.commune c
LEFT JOIN urbanisme.doc_urba d USING (code_insee)
LEFT JOIN urbanisme.zone_urba z USING (code_insee)
GROUP BY c.code_insee, c.nom, d.typedoc, d.datappro;

-- -----------------------------------------------------------------------------
-- Fiche parcelle : SELECT urbanisme.fiche_parcelle('67462000AB0123');
-- Un léger retrait (-0,5 m) évite de remonter les zones simplement contiguës.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION urbanisme.fiche_parcelle(p_idu text)
RETURNS jsonb LANGUAGE sql STABLE AS $$
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
COMMENT ON FUNCTION urbanisme.fiche_parcelle(text) IS
    'Renseignements d''urbanisme d''une parcelle au format JSON (zonage, prescriptions, SUP, environnement, adresses)';
