#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=app_password="$LEADHUNTER_APP_DB_PASSWORD" \
  --set=worker_password="$LEADHUNTER_WORKER_DB_PASSWORD" <<-'EOSQL'
SELECT format(
  'CREATE ROLE leadhunter_app LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
  :'app_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_app') \gexec
ALTER ROLE leadhunter_app PASSWORD :'app_password';

SELECT format(
  'CREATE ROLE leadhunter_worker LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
  :'worker_password'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_worker') \gexec
ALTER ROLE leadhunter_worker PASSWORD :'worker_password';

GRANT CONNECT ON DATABASE leadhunter TO leadhunter_app, leadhunter_worker;
GRANT USAGE ON SCHEMA public TO leadhunter_app, leadhunter_worker;
EOSQL
