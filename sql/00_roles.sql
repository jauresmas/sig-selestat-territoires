-- =============================================================================
-- Socle SIG intercommunal - 00. Rôles du serveur
-- À exécuter une fois par serveur PostgreSQL, en superutilisateur, AVANT de
-- restaurer la sauvegarde (les rôles sont communs à toutes les bases d'un
-- serveur : une sauvegarde de base ne les contient pas).
-- Rejouable : ne crée que ce qui manque.
-- =============================================================================

DO $$
DECLARE
    r record;
BEGIN
    FOR r IN SELECT * FROM (VALUES
        ('sig_admin',       true),   -- administrateur SIG, propriétaire des objets
        ('sig_editeur',     false),  -- groupe : saisie des données métier
        ('sig_lecteur',     false),  -- groupe : consultation des données internes
        ('sig_public',      false),  -- groupe : diffusion externe (schéma diffusion)
        ('u_espaces_verts', true),   -- compte nominatif d'exemple (éditeur)
        ('u_urbanisme',     true),   -- compte nominatif d'exemple (lecteur)
        ('u_web',           true)    -- compte technique de la carte web (public)
    ) AS t(nom, connexion)
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.nom) THEN
            EXECUTE format('CREATE ROLE %I %s', r.nom,
                           CASE WHEN r.connexion THEN 'LOGIN' ELSE 'NOLOGIN' END);
        END IF;
    END LOOP;
END $$;

GRANT sig_lecteur TO sig_editeur;   -- un éditeur peut aussi consulter
GRANT sig_editeur TO u_espaces_verts;
GRANT sig_lecteur TO u_urbanisme;
GRANT sig_public  TO u_web;

COMMENT ON ROLE sig_admin   IS 'Administrateur du SIG : propriétaire des schémas, intégration des référentiels';
COMMENT ON ROLE sig_editeur IS 'Saisie des données métier (espaces verts), au bureau ou sur le terrain avec QField';
COMMENT ON ROLE sig_lecteur IS 'Consultation de l''ensemble des données internes';
COMMENT ON ROLE sig_public  IS 'Diffusion externe : lecture du seul schéma diffusion';

-- Les mots de passe ne sont jamais écrits ici : les définir ensuite dans psql
-- avec \password sig_admin (puis u_espaces_verts, u_urbanisme, u_web).
