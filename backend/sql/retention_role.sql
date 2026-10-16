-- Database user for the retention job (rule DATA-06). Run it ONCE, as the database owner, after
-- schema.sql and roles.sql.
--
--   psql "$OWNER_DATABASE_URL" -v ON_ERROR_STOP=1 -v retention_password='<long random password>' \
--     -f backend/sql/retention_role.sql
--
-- Put that password in RETENTION_DATABASE_URL, on the server that runs the job. The running app
-- never gets it: the app user can only INSERT and SELECT (roles.sql), so a bug or an injection in
-- the app cannot erase the log. This user can only SELECT (to find the old rows) and DELETE.
-- It cannot INSERT, UPDATE or change the schema.
--
-- On Neon: the web SQL editor does not support psql variables. Create the role
-- portfolio_retention in the Neon console (Roles) instead, delete the CREATE ROLE statement
-- below and run the rest.

BEGIN;

CREATE ROLE portfolio_retention LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  PASSWORD :'retention_password';

-- Tables are private unless granted (roles.sql already closed the public role's access).
GRANT USAGE ON SCHEMA public TO portfolio_retention;
-- feedback rows go away with their message (ON DELETE CASCADE); the grant also allows a manual
-- clean-up of a rating.
GRANT SELECT, DELETE ON chat_messages, feedback TO portfolio_retention;

-- The job deletes in small batches. These limits keep a stuck query from holding a connection.
ALTER ROLE portfolio_retention SET statement_timeout = '60s';
ALTER ROLE portfolio_retention SET idle_in_transaction_session_timeout = '30s';

COMMIT;
