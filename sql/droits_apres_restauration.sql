-- =============================================================================
-- Socle SIG intercommunal - Droits sur la base après une restauration
-- La sauvegarde (pg_dump) restaure les propriétaires, les droits sur les schémas,
-- tables et vues, et les droits par défaut, mais pas les droits portés par la
-- base elle-même. À exécuter en superutilisateur, connecté à la base restaurée.
-- =============================================================================

DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I OWNER TO sig_admin', current_database());
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO sig_lecteur, sig_public', current_database());
END $$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
