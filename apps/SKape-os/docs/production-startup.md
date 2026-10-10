# Production startup and migration

This note separates behavior the backend already implements from
operational steps that are not implemented. It is not a production
readiness claim.

The variable names match `apps/SKape-os/backend/.env.production.example`.
That file is a template. Do not deploy its placeholder values.

## Implemented behavior

`SKAPE_ENV=production` requires a PostgreSQL `DATABASE_URL` that names a
database, an explicit HTTPS `SKAPE_CORS_ORIGINS` list, and API
documentation left disabled. `SECRET_KEY` must be at least 32 characters
and `ALGORITHM` must be `HS256`. The startup check parses configuration.
It does not open a database connection and it does not run migrations.

`load_dotenv()` reads a file named `.env` and does not replace variables
already present in the process. The production example file is not that
file. Supply production values through the host's secret mechanism.

`alembic upgrade head`, run from `apps/SKape-os/backend`, reads
`DATABASE_URL` from the environment. `alembic.ini` does not store a
connection URL. An online PostgreSQL migration runs in one transaction.
The API process does not call Alembic.

`GET /api/v1/health/` reports the process status and does not check the
database. `GET /api/v1/health/ready` checks connectivity and, in
production, that `alembic_version` matches the repository heads. A
failed readiness check returns HTTP 503. Readiness does not migrate.

PostgreSQL 16 is the major version used by the backend tests and the
isolated recovery proof. Startup does not reject another PostgreSQL
major version.

The frontend build reads `VITE_API_URL` from `apps/SKape-os/frontend/src/api/client.ts`.
The repository does not set a default.

## Intended order

These steps describe the intended order. Hosting, TLS termination,
secret storage, automated backups, WAL archiving, monitoring, and
rollback are not selected or implemented in this repository.

1. Provision the chosen PostgreSQL service and confirm the network path
   and TLS requirements for that service. No provider is selected here.
2. Supply the production variables through the host's secret-management
   mechanism. Do not copy `.env.production.example` into a production
   `.env` and do not commit filled-in secrets. The root `.gitignore`
   ignores a file named `.env`.
3. Take and verify a backup before migrating, once a production backup
   destination exists. The logical restore drill and the isolated PITR
   proof are synthetic tests. They are not that backup system, and this
   step cannot be completed until the backup system exists.
4. From `apps/SKape-os/backend`, run `alembic upgrade head` as its own
   deployment step, with `DATABASE_URL` set to the production database.
5. Start the API process only after that migration command succeeds.
   Starting the process does not migrate. The process also starts the
   device monitor.
6. Request `GET /api/v1/health/ready` and confirm it reports ready
   before sending user traffic. The endpoint is served by the running
   process, so this check follows process start. A schema mismatch
   stays unavailable and does not repair itself.
7. Build the frontend with `VITE_API_URL` set to the intended HTTPS API
   origin, and use that same origin in `SKAPE_CORS_ORIGINS`. Serving
   the built files, and terminating TLS in front of them, is outside
   this repository.

## Not implemented

No Dockerfile, process manager, reverse proxy, TLS terminator, secret
store, hosting platform, production database, backup schedule, WAL
archive, monitoring system, or rollback procedure is defined here.
Passing the local recovery drills does not establish a recovery point,
a recovery time, or production readiness.
