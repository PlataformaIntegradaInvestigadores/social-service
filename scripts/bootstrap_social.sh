#!/usr/bin/env bash

set -euo pipefail

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-social-service}"
DB_CONTAINER="${DB_CONTAINER:-${COMPOSE_PROJECT_NAME}-social-db-1}"
REDIS_CONTAINER="${REDIS_CONTAINER:-${COMPOSE_PROJECT_NAME}-social-redis-1}"
WEB_CONTAINER="${WEB_CONTAINER:-${COMPOSE_PROJECT_NAME}-social-service-1}"

DB_NAME="${DB_NAME:-pgdb}"
DB_USER="${DB_USER:-pguser}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

echo "Starting social consensus stack"
docker compose up -d --build

echo "Waiting for PostgreSQL"
until docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
  sleep 3
done

echo "Ensuring pgvector extension"
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" <<SQL
CREATE EXTENSION IF NOT EXISTS vector;
SQL

echo "Waiting for Redis"
if [ -n "$REDIS_PASSWORD" ]; then
  until docker exec -e REDISCLI_AUTH="$REDIS_PASSWORD" "$REDIS_CONTAINER" redis-cli ping | grep PONG >/dev/null 2>&1; do
    sleep 2
  done
else
  until docker exec "$REDIS_CONTAINER" redis-cli ping | grep PONG >/dev/null 2>&1; do
    sleep 2
  done
fi

echo "Applying Django migrations"
docker exec -i "$WEB_CONTAINER" python manage.py migrate

echo "Social consensus stack is ready"
