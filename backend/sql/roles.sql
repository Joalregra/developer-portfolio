-- Least-privilege database user for the running app (rule DATA-07). Run it ONCE, as the database
-- owner, after schema.sql.
--
--   psql "$OWNER_DATABASE_URL" -v ON_ERROR_STOP=1 -v app_password='<long random password>' \
--     -f backend/sql/roles.sql
--
-- The password comes from the psql variable, so it is never written in this file. If you forget
-- `-v app_password=...`, psql stops with a syntax error and no role is created. Put the same
-- password in the DATABASE_URL of the app.
--
-- On Neon: the web SQL editor does not support psql variables. Paste this file into the SQL
-- editor and write the password between quotes where :'app_password' is. Do NOT create the role
-- from the Neon console (Roles): roles made there, or through the CLI or the API, join
-- neon_superuser (pg_read_all_data and pg_write_all_data), which defeats the limits below. A role
-- made with CREATE ROLE has no extra privileges. Afterwards check it:
--
--   SELECT rolname, pg_has_role(rolname, 'neon_superuser', 'member') AS is_neon_superuser
--   FROM pg_roles WHERE rolname = 'portfolio_app';   -- must be false
--
-- The app can only INSERT and SELECT. It cannot UPDATE, DELETE or change the schema, so a bug or
-- an injection in the app cannot erase the log. Migrations use the owner; the retention job has
-- its own user, created by retention_role.sql.

BEGIN;

CREATE ROLE portfolio_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';

-- Tables are private unless granted; this also closes the default access of the public role.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
-- PostgreSQL 14 and older let everyone create objects in the public schema, which would give
-- the app user DDL rights. Newer versions already forbid it; this makes it explicit.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

GRANT USAGE ON SCHEMA public TO portfolio_app;
-- ON CONFLICT DO NOTHING needs only INSERT. There are no sequences, so nothing else is needed.
GRANT SELECT, INSERT ON chat_messages, feedback TO portfolio_app;

-- The log is best effort. These limits keep a slow or stuck query from holding a connection.
ALTER ROLE portfolio_app SET statement_timeout = '5s';
ALTER ROLE portfolio_app SET idle_in_transaction_session_timeout = '10s';

COMMIT;
