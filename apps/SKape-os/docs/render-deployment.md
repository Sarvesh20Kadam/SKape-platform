# Proposed Render deployment

This checklist is proposed configuration for a possible Render
deployment. It does not create a Render account, service, database, or
secret. Nothing in this repository is deployed to Render. It is not a
production readiness claim.

Startup behavior it relies on is documented in
`apps/SKape-os/docs/production-startup.md`.

## Backend

Proposed service root: `apps/SKape-os/backend`.

`apps/SKape-os/backend/.python-version` contains `3.12`. That is the
Python series installed by `.github/workflows/skape-os-backend.yml`.
The file does not name a patch release. Render documents that a
`.python-version` value without a patch selects the latest patch in
that series. A `PYTHON_VERSION` environment variable overrides the file
and must be a full version. Do not set `PYTHON_VERSION` to a patch this
repository has not verified. Confirm the build log shows a 3.12
release. Render's version notes describe this filename at the
repository root for a single-app repository. This proposal sets the
service root to the backend directory, where the file is stored, because
files outside that root are not available to the build.

Proposed install command, run from that root:

```text
python -m pip install -r requirements.txt
```

Proposed start command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The application does not read `PORT`. The command binds all interfaces
on the port the host provides. Render's default for that variable is
`10000`.

Proposed HTTP health check path: `/api/v1/health/ready`, with no
trailing slash. That route checks the database and, in production, the
Alembic head. It returns HTTP 503 when the check fails. `GET /` and
`GET /api/v1/health/` do not check the database. A redirect is not a
substitute. A 3xx response can satisfy the host health check without
running the readiness handler.

Use one paid web service instance. Render does not offer the pre-deploy
command on a free web service. Startup also starts one device monitor.
The default database pool allows at most 10 connections for that one
process.

## PostgreSQL

Proposed database: PostgreSQL 16, in the same region as the API. Select
version 16 explicitly. The create-form default is not 16. The
application tests PostgreSQL 16 and does not reject another major
version at startup.

Proposed connectivity: the API uses the database's internal URL. Add
`sslmode=require` to that URL. The application does not set TLS itself.
Restrict or disable external access. The free database plan provides no
backups and expires 30 days after creation. Do not choose a memory
size, including 256 MB, without workload evidence. A published
connection limit above 10 is not evidence that the memory size is
sufficient.

## Environment and secrets

Set these on the API service through the host secret store. Do not
deploy `apps/SKape-os/backend/.env.production.example`, and do not
commit a filled-in `.env`. `load_dotenv()` reads a file named `.env`
and does not replace variables already present in the process.

- `SKAPE_ENV=production`
- `DATABASE_URL`, a PostgreSQL URL that names a database
- `SECRET_KEY`, at least 32 characters
- `ALGORITHM=HS256`
- `SKAPE_CORS_ORIGINS`, the browser-visible HTTPS frontend origin
- `SKAPE_ENABLE_API_DOCS=false`

`SKAPE_CORS_ORIGINS` and `VITE_API_URL` are different values when the
frontend and API use separate hosts. The CORS value is the frontend
origin and has no path. `VITE_API_URL` is a frontend build variable,
not an API process variable.

## Migration and readiness

Proposed pre-deploy command, from the backend root:

```text
alembic upgrade head
```

Run that command as its own step before the new process serves traffic.
Alembic reads `DATABASE_URL`. `alembic.ini` does not store a URL. An
online PostgreSQL migration runs in one transaction, so a failed
upgrade rolls that transaction back. The API process does not migrate.

Render runs a pre-deploy command after the build and before the new
instance starts, on a separate instance. If the command fails, the
deploy stops and the previous release keeps serving. If the command
succeeds, the schema change is already committed before the new process
passes its health check.

After the process starts, request `GET /api/v1/health/ready` and
confirm it reports ready before sending user traffic. A schema mismatch
stays unavailable and does not repair itself.

## Frontend

Proposed static site root: `apps/SKape-os/frontend`.

Proposed build command:

```text
npm ci && npm run build
```

`npm run build` runs `tsc -b && vite build`. Vite's configuration does
not change the output directory, so the proposed publish directory is
`dist`.

The lockfile for Vite 8.2.0 requires Node `^20.19.0` or `>=22.12.0`
(`apps/SKape-os/frontend/package-lock.json`). This repository does not
pin a Node patch release. Do not invent one. The static-site build must
use a release inside that range, confirmed by a successful build.

Set `VITE_API_URL` for that build to the HTTPS API origin followed by
`/api/v1`. The client has no default, and its request paths do not
include `/api/v1`. Changing the value requires a new build.

The frontend uses browser routing. The proposed static host rewrites
client routes to `/index.html`. A host that only serves files that
exist will fail those routes on refresh.

## Rollback

A successful pre-deploy migration is not undone when the new release
fails its health check, or when the host rolls the service back to the
previous build. The previous application can then be running against
the new schema. `alembic downgrade` is not the production recovery
procedure. Recovery is a point-in-time restore into a new database,
followed by a switch of `DATABASE_URL`, and only after a second person
approves it. The founder executes that restore.

## Launch blockers

These acceptance targets remain unmet. This checklist does not
implement them.

- Off-site backup storage. Copies that stay only on the database host
  do not meet the recovery design.
- Retention of 14 daily, 8 weekly, and 6 monthly backups. Render's
  point-in-time window is 3 days on the Hobby workspace and 7 days on
  Pro or higher. Logical exports kept by Render last 7 days. Neither
  is the retention target.
- An alert when the newest recoverable point is older than 24 hours.
- A measured recovery point of no more than 24 hours, and a measured
  recovery time within 4 hours. Point-in-time recovery is mandatory
  before production launch. The local recovery drills do not establish
  either number.

Second-person approval for a production restore is an operating rule.
It is not a control implemented in this repository, and it is not a
proposed host setting.
