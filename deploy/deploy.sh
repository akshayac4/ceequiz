#!/usr/bin/env bash
# Runs on the VPS, in /opt/ceequiz. Invoked by GitHub Actions over the
# restricted deploy key (see README section "Deploy to the VPS").
set -euo pipefail

cd /opt/ceequiz

TARGET_REF="${1:-origin/main}"

echo "==> Fetching latest code"
git fetch origin
git reset --hard "$TARGET_REF"

echo "==> Backing up the database"
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)
docker compose exec -T db pg_dump -U "$(grep ^POSTGRES_USER .env | cut -d= -f2)" "$(grep ^POSTGRES_DB .env | cut -d= -f2)" \
  | gzip > "backups/ceequiz-${STAMP}.sql.gz"

echo "==> Building image"
docker compose build web

echo "==> Starting containers"
docker compose up -d

echo "==> Running migrations"
docker compose exec -T web python manage.py migrate --noinput

echo "==> Collecting static files"
docker compose exec -T web python manage.py collectstatic --noinput

echo "==> Health check"
for i in $(seq 1 10); do
  if docker compose exec -T web curl -fs http://localhost:8000/healthz > /dev/null; then
    echo "Health check OK"
    echo "==> Deployed commit: $(git rev-parse HEAD)"
    exit 0
  fi
  sleep 3
done

echo "Health check FAILED — deploy did not come up cleanly." >&2
exit 1
