#!/usr/bin/env bash
set -euo pipefail

# BBL.BOXTV - instalação de produção em VPS Ubuntu.
# Uso: copie .env.vps para /opt/bbl-boxtv/.env, ajuste os valores e rode como root.

ROOT=/opt/bbl-boxtv
REPO=https://github.com/bblboxtv-bot/bbl-tvbox-server.git
mkdir -p "$ROOT"/{uploads,postgres,backups,caddy}

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl git docker.io docker-compose-v2
  systemctl enable --now docker
fi

if [ ! -d "$ROOT/app/.git" ]; then
  git clone "$REPO" "$ROOT/app"
else
  git -C "$ROOT/app" fetch --all --prune
  git -C "$ROOT/app" checkout main
  git -C "$ROOT/app" pull --ff-only
fi

if [ ! -f "$ROOT/.env" ]; then
  cat > "$ROOT/.env" <<'ENV'
DOMAIN=SEU_DOMINIO_AQUI
PUBLIC_BASE_URL=https://SEU_DOMINIO_AQUI
ADMIN_KEY=TROQUE_ESTA_CHAVE
ACTIVATION_KEY=BBL-2026
POSTGRES_DB=bbl_tvbox
POSTGRES_USER=bbl
POSTGRES_PASSWORD=TROQUE_ESTA_SENHA_FORTE
RUN_DB_INIT_ON_STARTUP=0
FILE_STORAGE=filesystem
DB_CONNECT_TIMEOUT=5
DB_IDLE_SESSION_TIMEOUT_MS=60000
DB_STATEMENT_TIMEOUT_MS=30000
DB_LOCK_TIMEOUT_MS=5000
ENV
  echo "Edite $ROOT/.env e rode novamente."
  exit 2
fi

cat > "$ROOT/docker-compose.yml" <<'YAML'
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    env_file: .env
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - ./postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 10

  app:
    build: ./app
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      UPLOAD_DIR: /data/uploads
      RUN_DB_INIT_ON_STARTUP: ${RUN_DB_INIT_ON_STARTUP:-0}
    volumes:
      - ./uploads:/data/uploads
    depends_on:
      db:
        condition: service_healthy
    command: uvicorn main:app --host 0.0.0.0 --port 8000
    expose:
      - "8000"

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    env_file: .env
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./caddy/data:/data
      - ./caddy/config:/config
    depends_on:
      - app
YAML

cat > "$ROOT/Caddyfile" <<'CADDY'
{$DOMAIN} {
  encode zstd gzip
  reverse_proxy app:8000
}
CADDY

cat > "$ROOT/backup.sh" <<'BACKUP'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/bbl-boxtv
set -a
. ./.env
set +a
STAMP=$(date -u +%Y%m%d_%H%M%S)
mkdir -p backups
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "backups/db_$STAMP.sql.gz"
tar -czf "backups/uploads_$STAMP.tar.gz" uploads
find backups -type f -mtime +14 -delete
BACKUP
chmod +x "$ROOT/backup.sh"

cd "$ROOT"
# Primeira inicialização: cria/migra schema uma vez, depois desliga a flag.
sed -i 's/^RUN_DB_INIT_ON_STARTUP=.*/RUN_DB_INIT_ON_STARTUP=1/' .env
docker compose up -d --build
sleep 15
docker compose restart app
sed -i 's/^RUN_DB_INIT_ON_STARTUP=.*/RUN_DB_INIT_ON_STARTUP=0/' .env

cat >/etc/cron.d/bbl-boxtv-backup <<'CRON'
17 3 * * * root /opt/bbl-boxtv/backup.sh >/var/log/bbl-boxtv-backup.log 2>&1
CRON
chmod 644 /etc/cron.d/bbl-boxtv-backup

echo "BBL.BOXTV VPS preparada."
echo "Health: https://$(grep '^DOMAIN=' .env | cut -d= -f2)/health"
