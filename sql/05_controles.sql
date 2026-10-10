-- =============================================================================
-- Socle SIG intercommunal - 05. Contrôles qualité
-- Chaque vue renvoie une ligne par anomalie, avec sa géométrie : elles
-- s'ouvrent directement dans QGIS pour corriger, et alimentent le rapport
-- de contrôle (scripts/02_controle_qualite.py).
-- =============================================================================

-- 1. Géométries invalides dans les tables surfaciques principales
CREATE OR REPLACE VIEW controle.v_geometrie_invalide AS
SELECT 'ref_cadastre.parcelle' AS couche, idu AS identifiant,
       ST_IsValidReason(geom) AS anomalie, ST_PointOnSurface(ST_MakeValid(geom))::geometry(Point, 2154) AS geom
FROM ref_cadastre.parcelle WHERE NOT ST_IsValid(geom)
UNION ALL
SELECT 'urbanisme.zone_urba', gid::text, ST_IsValidReason(geom), ST_PointOnSurface(ST_MakeValid(geom))
FROM urbanisme.zone_urba WHERE NOT ST_IsValid(geom)
UNION ALL
SELECT 'ref_topo.batiment', cleabs, ST_IsValidReason(geom), ST_PointOnSurface(ST_MakeValid(geom))
FROM ref_topo.batiment WHERE NOT ST_IsValid(geom);

-- 2. Zonage du PLU : chevauchements entre zones d'un même document
CREATE OR REPLACE VIEW controle.v_zonage_chevauchement AS
SELECT (row_number() OVER ())::int AS gid, a.code_insee, a.libelle AS zone_a, b.libelle AS zone_b,
       round(ST_Area(ST_Intersection(a.geom, b.geom))::numeric) AS surface_m2,
       ST_PointOnSurface(ST_Intersection(a.geom, b.geom))::geometry(Point, 2154) AS geom
FROM urbanisme.zone_urba a
JOIN urbanisme.zone_urba b
  ON a.code_insee = b.code_insee AND a.gid < b.gid AND ST_Overlaps(a.geom, b.geom)
WHERE ST_Area(ST_Intersection(a.geom, b.geom)) > 10;

-- 3. Zonage du PLU : parcelles non couvertes (trous dans le plan de zonage)
CREATE OR REPLACE VIEW controle.v_parcelle_hors_zonage AS
SELECT m.idu, m.code_insee, coalesce(m.part_pct, 0) AS part_couverte_pct,
       ST_PointOnSurface(p.geom)::geometry(Point, 2154) AS geom
FROM urbanisme.mv_parcelle_zonage m
JOIN ref_cadastre.parcelle p USING (idu)
WHERE m.code_insee IN (SELECT code_insee FROM urbanisme.doc_urba)
  AND coalesce(m.part_pct, 0) < 50
  AND m.surface_m2 > 50;

-- 4. Adresses : doublons (même numéro, indice et voie dans une commune)
CREATE OR REPLACE VIEW controle.v_adresse_doublon AS
SELECT a.cle_interop, a.code_insee, a.numero, a.rep, a.nom_voie, d.nb, a.geom
FROM ref_adresse.adresse a
JOIN (
    SELECT code_insee, numero, coalesce(rep, '') AS rep, lower(unaccent(nom_voie)) AS voie,
           count(*) AS nb
    FROM ref_adresse.adresse
    WHERE numero IS NOT NULL AND numero < 5000
    GROUP BY 1, 2, 3, 4 HAVING count(*) > 1
) d ON d.code_insee = a.code_insee AND d.numero = a.numero
   AND d.rep = coalesce(a.rep, '') AND d.voie = lower(unaccent(a.nom_voie));

-- 5. Adresses non certifiées par la commune : la commune est responsable de
--    son adressage (loi 3DS) et certifie chaque adresse dans sa Base Adresse Locale
CREATE OR REPLACE VIEW controle.v_adresse_non_certifiee AS
SELECT a.cle_interop, a.code_insee, a.numero, a.rep, a.nom_voie, a.source_position, a.geom
FROM ref_adresse.adresse a
WHERE NOT a.certification_commune AND a.numero < 5000;

-- 6. Bâtiments d'habitation sans adresse à moins de 30 m : candidats à
--    l'adressage dans la Base Adresse Locale (compétence communale, loi 3DS)
CREATE OR REPLACE VIEW controle.v_batiment_sans_adresse AS
SELECT b.cleabs, c.code_insee, b.usage_1, b.nombre_de_logements,
       round(ST_Area(b.geom)::numeric) AS surface_m2,
       ST_PointOnSurface(b.geom)::geometry(Point, 2154) AS geom
FROM ref_topo.batiment b
JOIN ref_admin.commune c ON ST_Intersects(c.geom, ST_PointOnSurface(b.geom))
WHERE b.usage_1 = 'Résidentiel'
  AND ST_Area(b.geom) >= 40
  AND NOT EXISTS (SELECT 1 FROM ref_adresse.adresse a WHERE ST_DWithin(a.geom, b.geom, 30));

-- 7. Arbres : doublons de saisie (deux points à moins de 1 m)
CREATE OR REPLACE VIEW controle.v_arbre_doublon AS
SELECT a.numero AS numero_a, b.numero AS numero_b,
       round(ST_Distance(a.geom, b.geom)::numeric, 2) AS distance_m, a.geom
FROM espaces_verts.arbre a
JOIN espaces_verts.arbre b ON a.id < b.id AND ST_DWithin(a.geom, b.geom, 1)
WHERE a.statut = 'en_place' AND b.statut = 'en_place';

-- 8. Arbres : fiches incomplètes (attributs obligatoires pour le plan de gestion)
CREATE OR REPLACE VIEW controle.v_arbre_incomplet AS
SELECT a.numero, a.code_insee,
       concat_ws(', ',
           CASE WHEN a.essence = 'Indetermine' THEN 'essence' END,
           CASE WHEN a.etat_sanitaire IS NULL THEN 'état sanitaire' END,
           CASE WHEN a.stade_dev IS NULL THEN 'stade' END,
           CASE WHEN a.hauteur_m IS NULL THEN 'hauteur' END) AS champs_manquants,
       a.geom
FROM espaces_verts.arbre a
WHERE a.statut = 'en_place'
  AND (a.essence = 'Indetermine' OR a.etat_sanitaire IS NULL
       OR a.stade_dev IS NULL OR a.hauteur_m IS NULL);

-- Tableau de bord : nombre d'anomalies par contrôle
CREATE OR REPLACE VIEW controle.v_synthese AS
SELECT 'Géométries invalides' AS controle, 'toutes couches' AS couche,
       (SELECT count(*) FROM controle.v_geometrie_invalide) AS anomalies
UNION ALL SELECT 'Chevauchements de zones', 'urbanisme.zone_urba',
       (SELECT count(*) FROM controle.v_zonage_chevauchement)
UNION ALL SELECT 'Parcelles hors zonage', 'urbanisme.zone_urba',
       (SELECT count(*) FROM controle.v_parcelle_hors_zonage)
UNION ALL SELECT 'Adresses en doublon', 'ref_adresse.adresse',
       (SELECT count(*) FROM controle.v_adresse_doublon)
UNION ALL SELECT 'Adresses non certifiées', 'ref_adresse.adresse',
       (SELECT count(*) FROM controle.v_adresse_non_certifiee)
UNION ALL SELECT 'Logements sans adresse proche', 'ref_topo.batiment',
       (SELECT count(*) FROM controle.v_batiment_sans_adresse)
UNION ALL SELECT 'Arbres en doublon', 'espaces_verts.arbre',
       (SELECT count(*) FROM controle.v_arbre_doublon)
UNION ALL SELECT 'Fiches arbre incomplètes', 'espaces_verts.arbre',
       (SELECT count(*) FROM controle.v_arbre_incomplet);
