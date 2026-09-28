#!/usr/bin/env bash
set -euo pipefail

# Migra o PostgreSQL atual para a VPS nova.
# Execute NA VPS, depois de preencher /opt/bbl-boxtv/.env.
# A URL de origem deve ser informada somente no terminal:
#   export OLD_DATABASE_URL='postgresql://...?...'
#   sudo -E /opt/bbl-boxtv/app/migrate-render-db.sh

ROOT=/opt/bbl-boxtv
cd "$ROOT"
set -a
. ./.env
set +a

: "${OLD_DATABASE_URL:?Defina OLD_DATABASE_URL antes de executar.}"
mkdir -p backups
STAMP=$(date -u +%Y%m%d_%H%M%S)
DUMP="backups/render_before_migration_${STAMP}.dump"

if ! command -v pg_dump >/dev/null 2>&1; then
  apt-get update
  apt-get install -y postgresql-client
fi

echo "1/5 Criando snapshot do banco Render..."
pg_dump --format=custom --no-owner --no-acl "$OLD_DATABASE_URL" -f "$DUMP"

echo "2/5 Parando somente a API nova..."
docker compose stop app

echo "3/5 Recriando banco de destino..."
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$POSTGRES_DB' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "$POSTGRES_DB";
CREATE DATABASE "$POSTGRES_DB" OWNER "$POSTGRES_USER";
SQL

echo "4/5 Restaurando dados..."
pg_restore --no-owner --no-acl   --dbname="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@127.0.0.1:5432/$POSTGRES_DB"   "$DUMP" || {
    # O Postgres do container não é exposto no host por padrão; restaura via stdin.
    pg_restore --no-owner --no-acl --file=- "$DUMP" |       docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1
  }

echo "5/5 Subindo API e verificando..."
docker compose up -d app
sleep 8
docker compose ps
echo "Snapshot mantido em $ROOT/$DUMP"
echo "Valide /health e o painel antes de trocar qualquer Box."
