# Centinela — social-service

Servicio Django que maneja autenticación, feeds sociales (posts, comentarios, likes, encuestas), consenso científico entre investigadores y ofertas laborales (jobs). Expone API REST + WebSockets (Django Channels) para actualizaciones en tiempo real de feeds.

Parte del org multi-repo `PlataformaIntegradaInvestigadores`. Se comunica con el resto de la plataforma a través de `gateway-service` (nginx), en la red Docker `centinela-net`.

## Stack

- Django 5.0 + Django REST Framework, servido con Daphne (ASGI) para soportar WebSockets
- Django Channels + `channels-redis` (WebSockets de feeds en tiempo real)
- Celery (worker + beat) para tareas asíncronas y programadas
- PostgreSQL 16 con `pgvector` (embeddings)
- Redis 6 (broker de Channels/Celery)
- SimpleJWT (autenticación)

## Estructura del proyecto

```
apps/
  custom_auth/      # autenticación, usuarios, JWT
  concensus/         # consenso científico entre investigadores
  feeds/              # posts, comentarios, likes, encuestas, WebSockets
  jobs/                # ofertas laborales, postulaciones
  media/              # uploads de feeds (gitignorado salvo estructura)

project/              # settings, urls raíz, asgi.py (Daphne)
scripts/               # scripts de bootstrap (migraciones + pgvector)
```

Cada app en `apps/<app>/` sigue arquitectura por capas (Clean/Hexagonal):

```
apps/<app>/
  domain/                    # entidades y reglas de negocio puras
    entities/
    services/
  infrastructure/
    api/v1/
      views/                 # DRF views/viewsets
      serializers/
      urls/
    migrations/
  tests/                      # test_*.py (pytest-django)
```

## Requisitos previos

- Docker y Docker Compose
- Red Docker externa `centinela-net` (compartida con el resto de la plataforma). Si no existe, créala una vez: `docker network create centinela-net`

## Levantar en local

### Configuración obligatoria (hazlo antes del primer arranque)

El repo **no trae secretos**: cada quien define los suyos en un `.env` local (gitignorado).

1. Crea la red compartida (una sola vez por máquina):
   ```bash
   docker network create centinela-net
   ```
2. Copia la plantilla y edítala:
   ```bash
   cp .env.example .env
   ```
3. Reemplaza en `.env` todos los valores `change-me-*` y las claves de ejemplo. Como mínimo:
   - `SECRET_KEY` y `JWT_SIGNING_KEY`
   - `DB_PASSWORD`
   - `REDIS_PASSWORD`: **invéntala tú**. `docker-compose.yml` arranca Redis con `--requirepass $REDIS_PASSWORD` y Django/Channels/Celery leen la misma variable, así que no hay nada más que sincronizar. Si queda vacía, `docker compose up` falla con un mensaje explícito.
   - `PROFILE_SYNC_INTERNAL_TOKEN`
4. Las URLs entre servicios (`EMBEDDING_SERVICE_URL`, `GRS_SERVICE_URL`, `PROFILE_IDENTITY_BASE_URL`) apuntan a los alias de `centinela-net`. Si solo levantas este servicio, esas funciones fallarán hasta que levantes los otros repos o cambies las URLs.

> `redis.conf` ya no contiene contraseña: no pongas secretos en archivos versionados.

### Con Docker (recomendado)

```bash
docker compose up -d --build
```

Levanta `social-service` (Daphne, puerto `8000`), `social-db` (Postgres+pgvector, puerto `5433`→`5432`), `social-redis`, `social-worker` y `social-beat`.

### Sin Docker (desarrollo)

```bash
python -m venv .venv && .venv/Scripts/activate  # o source .venv/bin/activate en Linux/Mac
pip install -r requirements.txt
bash scripts/bootstrap_social.sh   # migraciones + extensión pgvector
python manage.py runserver
```

## Variables de entorno

Ver `.env.example`. Variables clave:

| Variable | Descripción |
|---|---|
| `SECRET_KEY` / `JWT_SIGNING_KEY` | Claves de Django y de firma de JWT |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | Conexión a PostgreSQL |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | Conexión a Redis. `REDIS_PASSWORD` es obligatoria y la usa también el contenedor de Redis (`--requirepass`) |
| `SOCIAL_DB_VOLUME` | Opcional. Nombre del volumen de Postgres; solo para servidores con un volumen preexistente (p. ej. `centinela_postgres_data`) |
| `DEBUG` / `ALLOWED_HOSTS` | Configuración estándar de Django |

## Documentación (Swagger)

Schema OpenAPI: `GET /api/schema?format=json`. UI local propia en `/api/schema/swagger-ui/` (y Redoc en `/api/schema/redoc/`), además disponible centralizada en el hub del `gateway-service`: `/api/docs/v1/social`. `SPECTACULAR_SETTINGS` recorta el prefijo interno `/api` y declara `servers: [{"url": "/api/social"}]` para que "Try it out" funcione a través del gateway.

## Tests

```bash
pytest apps/ --cov=apps --cov-report=term
```

Cobertura mínima exigida en CI: **90%** (`--cov-fail-under=90` en `.github/workflows/ci.yml`). Los tests de cada app viven en `apps/<app>/tests/test_*.py`.

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`): tests unitarios (Postgres+pgvector) → tests de integración (Postgres + Redis) → build de imagen Docker → deploy automático a staging (`develop` branch, runner self-hosted `ticcd`), con healthcheck contra `/api/v1/` y rollback automático si falla.

## Convenciones

- Branches: `feature/*` → `develop`, `hotfix/*` → `main`.
- Commits: [Conventional Commits](https://www.conventionalcommits.org/), inglés, con el *por qué* en el cuerpo.
