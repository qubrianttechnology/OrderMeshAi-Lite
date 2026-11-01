-- Executed only on first initialization of the local Compose PostgreSQL volume.
-- psql variable interpolation quotes the secret as a SQL literal; no secret in source.
\getenv app_password DB_APP_PASSWORD
CREATE ROLE ordermesh_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD :'app_password';
GRANT CONNECT ON DATABASE ordermesh TO ordermesh_app;
GRANT USAGE ON SCHEMA public TO ordermesh_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ordermesh_app;
