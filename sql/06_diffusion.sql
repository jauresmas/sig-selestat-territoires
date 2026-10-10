-- =============================================================================
-- Socle SIG intercommunal - 06. Vues de diffusion
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Vues de diffusion : ce qui peut sortir de la collectivité
-- (carte web publique, plateforme open data, réponses aux demandes externes)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW diffusion.v_commune AS
SELECT code_insee, nom, population, surface_ha, geom FROM ref_admin.commune;

CREATE OR REPLACE VIEW diffusion.v_zone_urba AS
SELECT gid, code_insee, idurba, libelle, libelong, typezone, destdomi, urlfic, geom
FROM urbanisme.zone_urba;

-- Patrimoine arboré : on publie l'essence, la taille et l'état, pas les
-- observations libres ni les noms des agents (données internes)
CREATE OR REPLACE VIEW diffusion.v_arbre AS
SELECT a.numero, a.code_insee, a.essence, e.nom_francais, a.implantation, a.stade_dev,
       a.hauteur_m, a.circonference_cm, a.etat_sanitaire, a.remarquable, a.geom
FROM espaces_verts.arbre a
JOIN espaces_verts.liste_essence e ON e.code = a.essence
WHERE a.statut = 'en_place';

-- Vue de la fiche des jeux de données publiables
CREATE OR REPLACE VIEW diffusion.v_catalogue AS
SELECT identifiant, table_nom, titre, resume, producteur, licence, millesime,
       date_integration, frequence_maj, nb_objets
FROM metadonnees.fiche WHERE niveau_diffusion = 'ouverte';

GRANT SELECT ON ALL TABLES IN SCHEMA diffusion TO sig_public, sig_lecteur;
