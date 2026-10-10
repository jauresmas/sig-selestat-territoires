-- =============================================================================
-- Socle SIG intercommunal - 07. Indicateurs par commune
-- Une ligne par commune : alimente l'atlas communal, le tableau de bord et la
-- carte web. Vue matérialisée, rafraîchie après chaque intégration :
--   REFRESH MATERIALIZED VIEW ref_admin.mv_indicateurs_commune;
-- =============================================================================

DROP MATERIALIZED VIEW IF EXISTS ref_admin.mv_indicateurs_commune CASCADE;
CREATE MATERIALIZED VIEW ref_admin.mv_indicateurs_commune AS
WITH
adr AS (
    SELECT code_insee, count(*) AS nb_adresses,
           round(100.0 * avg(certification_commune::int), 1) AS adresses_certifiees_pct,
           round(100.0 * avg((coalesce(cad_parcelles, '') <> '')::int), 1) AS adresses_liees_parcelle_pct
    FROM ref_adresse.adresse GROUP BY code_insee
),
parc AS (
    SELECT code_insee, count(*) AS nb_parcelles FROM ref_cadastre.parcelle GROUP BY code_insee
),
bati AS (
    SELECT c.code_insee, count(*) AS nb_batiments,
           sum(b.nombre_de_logements) AS nb_logements
    FROM ref_topo.batiment b
    JOIN ref_admin.commune c ON ST_Intersects(c.geom, ST_PointOnSurface(b.geom))
    GROUP BY c.code_insee
),
sans_adr AS (
    SELECT code_insee, count(*) AS logements_sans_adresse
    FROM controle.v_batiment_sans_adresse GROUP BY code_insee
),
zon AS (
    SELECT code_insee,
           round((sum(ST_Area(geom)) FILTER (WHERE typezone = 'U') / 1e4)::numeric, 1) AS zone_u_ha,
           round((sum(ST_Area(geom)) FILTER (WHERE typezone IN ('AUc', 'AUs')) / 1e4)::numeric, 1) AS zone_au_ha,
           round((sum(ST_Area(geom)) FILTER (WHERE typezone IN ('A', 'Ah')) / 1e4)::numeric, 1) AS zone_a_ha,
           round((sum(ST_Area(geom)) FILTER (WHERE typezone IN ('N', 'Nh')) / 1e4)::numeric, 1) AS zone_n_ha
    FROM urbanisme.zone_urba GROUP BY code_insee
),
natura AS (
    SELECT c.code_insee,
           round((100 * ST_Area(ST_Intersection(c.geom, ST_Union(n.geom))) / ST_Area(c.geom))::numeric, 1) AS natura2000_pct
    FROM ref_admin.commune c
    JOIN environnement.zonage_naturel n ON n.type_zonage IN ('SIC', 'ZPS') AND ST_Intersects(c.geom, n.geom)
    GROUP BY c.code_insee, c.geom
),
znieff AS (
    SELECT c.code_insee,
           round((100 * ST_Area(ST_Intersection(c.geom, ST_Union(n.geom))) / ST_Area(c.geom))::numeric, 1) AS znieff_pct
    FROM ref_admin.commune c
    JOIN environnement.zonage_naturel n ON n.type_zonage LIKE 'ZNIEFF%' AND ST_Intersects(c.geom, n.geom)
    GROUP BY c.code_insee, c.geom
),
ppri AS (
    SELECT c.code_insee,
           round((100 * ST_Area(ST_Intersection(c.geom, ST_Union(ST_MakeValid(s.geom)))) / ST_Area(c.geom))::numeric, 1) AS ppri_pct
    FROM ref_admin.commune c
    JOIN servitudes.sup_assiette_s s ON s.suptype = 'PM1' AND ST_Intersects(c.geom, s.geom)
    GROUP BY c.code_insee, c.geom
),
mh AS (
    SELECT c.code_insee, count(DISTINCT g.idgen) AS nb_monuments_historiques
    FROM ref_admin.commune c
    JOIN servitudes.sup_generateur_s g ON g.suptype = 'AC1' AND ST_Intersects(c.geom, g.geom)
    GROUP BY c.code_insee
),
arb AS (
    SELECT code_insee, count(*) AS nb_arbres,
           count(*) FILTER (WHERE etat_sanitaire IN ('deperissant', 'mort')) AS nb_arbres_degrades
    FROM espaces_verts.arbre WHERE statut = 'en_place' GROUP BY code_insee
),
equip AS (
    SELECT c.code_insee,
           count(*) FILTER (WHERE e.categorie = 'Science et enseignement') AS nb_etablissements_scolaires,
           count(*) FILTER (WHERE e.categorie = 'Sport') AS nb_equipements_sportifs
    FROM ref_topo.equipement e
    JOIN ref_admin.commune c ON ST_Intersects(c.geom, ST_PointOnSurface(e.geom))
    GROUP BY c.code_insee
)
SELECT c.code_insee, c.nom, c.population, c.surface_ha,
       round(c.population / nullif(c.surface_ha / 100, 0)) AS densite_hab_km2,
       coalesce(d.typedoc, 'Non publié') AS document_urbanisme,
       to_date(d.datappro, 'YYYYMMDD') AS date_approbation,
       d.nomproc AS derniere_procedure,
       parc.nb_parcelles, bati.nb_batiments, bati.nb_logements,
       adr.nb_adresses, adr.adresses_certifiees_pct, adr.adresses_liees_parcelle_pct,
       coalesce(sans_adr.logements_sans_adresse, 0) AS logements_sans_adresse,
       zon.zone_u_ha, zon.zone_au_ha, zon.zone_a_ha, zon.zone_n_ha,
       coalesce(natura.natura2000_pct, 0) AS natura2000_pct,
       coalesce(znieff.znieff_pct, 0) AS znieff_pct,
       coalesce(ppri.ppri_pct, 0) AS ppri_pct,
       coalesce(mh.nb_monuments_historiques, 0) AS nb_monuments_historiques,
       coalesce(equip.nb_etablissements_scolaires, 0) AS nb_etablissements_scolaires,
       coalesce(equip.nb_equipements_sportifs, 0) AS nb_equipements_sportifs,
       coalesce(arb.nb_arbres, 0) AS nb_arbres,
       coalesce(arb.nb_arbres_degrades, 0) AS nb_arbres_degrades,
       c.geom
FROM ref_admin.commune c
LEFT JOIN urbanisme.doc_urba d USING (code_insee)
LEFT JOIN adr USING (code_insee)
LEFT JOIN parc USING (code_insee)
LEFT JOIN bati USING (code_insee)
LEFT JOIN sans_adr USING (code_insee)
LEFT JOIN zon USING (code_insee)
LEFT JOIN natura USING (code_insee)
LEFT JOIN znieff USING (code_insee)
LEFT JOIN ppri USING (code_insee)
LEFT JOIN mh USING (code_insee)
LEFT JOIN arb USING (code_insee)
LEFT JOIN equip USING (code_insee)
ORDER BY c.code_insee;

CREATE UNIQUE INDEX mv_indicateurs_commune_insee ON ref_admin.mv_indicateurs_commune (code_insee);
COMMENT ON MATERIALIZED VIEW ref_admin.mv_indicateurs_commune IS
    'Indicateurs SIG par commune (urbanisme, adressage, environnement, risques, patrimoine arboré)';

CREATE OR REPLACE VIEW diffusion.v_indicateurs_commune AS
SELECT * FROM ref_admin.mv_indicateurs_commune;

GRANT SELECT ON ref_admin.mv_indicateurs_commune TO sig_lecteur;
GRANT SELECT ON diffusion.v_indicateurs_commune TO sig_public, sig_lecteur;
