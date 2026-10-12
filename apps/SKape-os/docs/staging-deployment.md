# Staging deployment contract

This note is the contract for the first isolated staging deployment.
It does not select a hosting provider, create a service, or record a
completed verification. It is not a production readiness claim.

Behavior the backend already implements is described in
`apps/SKape-os/docs/production-startup.md`. Variable names match
`apps/SKape-os/backend/.env.production.example`. That file is a
template. Do not deploy its placeholder values, and do not copy a
filled-in production configuration onto staging.

## Environment boundary

Staging is a non-production environment. It has its own disposable
PostgreSQL 16 database. That database is not the local development
database and it is not the production database.

The initial staging deployment runs exactly one API process. The API
lifespan in `apps/SKape-os/backend/app/main.py` starts the device
monitor with that process and stops the monitor when the process
stops. One process is the staging shape. Do not add a second API
process for the initial deployment.

Use Python 3.12, the series named in
`apps/SKape-os/backend/.python-version` and installed by
`.github/workflows/skape-os-backend.yml`. From
`apps/SKape-os/backend`, install only `requirements.txt`:

```text
python -m pip install -r requirements.txt
```

Do not install `apps/SKape-os/backend/requirements-backup.txt` on the
staging API.

## Runtime validation and secrets

Set `SKAPE_ENV=production` on the staging API. That value enables the
production runtime checks. It does not mean the process is production,
and it does not authorize use of the production database.

`SKAPE_ENV` accepts only `production` and `development`. The value
`staging` is rejected before startup. Staging therefore uses
`SKAPE_ENV=production` with staging-only credentials:

- `DATABASE_URL` names the disposable staging PostgreSQL 16 database.
- `SECRET_KEY` is a staging signing secret of at least 32 characters.
- `ALGORITHM` is `HS256`.
- `SKAPE_CORS_ORIGINS` is the staging frontend origin.
- `SKAPE_ENABLE_API_DOCS` stays false.

The production database URL is forbidden on staging. Production
signing secrets and every other production credential are forbidden
on staging. Supply staging values through the host secret store. Do
not commit them. `load_dotenv()` reads a file named `.env` and does
not replace variables already present in the process. The root
`.gitignore` ignores a file named `.env`.

The startup check parses configuration. It does not open a database
connection, and the API process does not run migrations.

## Frontend and CORS

Build the frontend from `apps/SKape-os/frontend` with:

```text
VITE_API_URL=https://<staging-api-origin>/api/v1
```

`<staging-api-origin>` is a placeholder for the staging API host. This
repository does not name that host. Client paths such as
`/users/login` are served by the API under `/api/v1`, so the value
includes that prefix.

`apps/SKape-os/frontend/src/api/apiBaseUrl.ts` resolves that variable.
`apps/SKape-os/frontend/vite.config.ts` runs the same check during
`npm run build`, and `apps/SKape-os/frontend/src/api/client.ts` uses
the resolved value as the Axios base URL. A production build fails
when the value is missing, not a valid URL, not HTTPS, uses a local
host, includes credentials, a query, or a fragment, or does not end
with `/api/v1`. One or more trailing slashes are removed. The build
does not fall back to localhost, and the error text does not include
the supplied value.

`npm run dev` is the development-only path. It accepts the same HTTPS
shape, and it accepts HTTP only for an explicit `localhost`,
`127.0.0.1`, or `::1` host that still ends with `/api/v1`. It does not
invent a localhost URL when the variable is unset.

Set `SKAPE_CORS_ORIGINS` to the frontend's HTTPS origin only. The
value has no path and no wildcard. It is the browser origin of the
staging frontend, not the API URL. When the frontend and API use
separate hosts, `SKAPE_CORS_ORIGINS` and `VITE_API_URL` are different
values.

The frontend uses browser routing. The chosen frontend host must
serve the built `index.html` for client-side routes. This repository
does not configure that host.

## Migration

Run `alembic upgrade head` from `apps/SKape-os/backend` as a separate,
explicit operation. Point `DATABASE_URL` at the empty staging
database. `apps/SKape-os/backend/alembic.ini` does not store a
connection URL. Complete that command before starting the API.

Never run migrations automatically during API startup. Starting
`app.main:app` does not call Alembic.

## Readiness

After the API process is running, use `GET /api/v1/health/ready` as
the readiness check. Require a successful ready response before using
the site.

`GET /api/v1/health/` reports process status only. It does not verify
database connectivity, the PostgreSQL major version, or schema
readiness. A ready response in production mode requires PostgreSQL
major version 16 and `alembic_version` matching the repository head.
Startup still only parses configuration: it does not connect or
migrate. A failed readiness check returns HTTP 503 and does not
migrate. PostgreSQL 16 must be provisioned separately before staging
can pass readiness. This note does not record that provisioning.

## Release control

Keep automatic deployment from `main` disabled until hosting behavior
has been inspected and deliberately approved. These workflows are
triggered by push and pull request. Neither file contains a deploy
step:

- `.github/workflows/skape-os-backend.yml` is configured to run the
  SQLite suite and the PostgreSQL 16 job.
- `.github/workflows/skape-os-frontend.yml` is configured to install
  the frontend lockfile with Node 22, run lint and the API URL tests,
  and build with the non-production placeholder
  `https://staging.example.invalid/api/v1`. A following build with
  `VITE_API_URL` unset must fail and its output must contain
  `VITE_API_URL is required.` Any other build failure fails that step.
  Node 22 is inside the lockfile range `>=22.12.0`. The workflow does
  not pin a patch release. A defined workflow is not a completed
  GitHub Actions run.

Absence of a deploy step in those files does not prove that an
external host is idle.

No hosting provider is selected here. Do not treat
`apps/SKape-os/docs/render-deployment.md` as an active staging
configuration. That note is a proposal and says nothing in this
repository is deployed.

## Excluded from initial staging

The initial staging deployment excludes:

- R2 credentials and every other object-store credential.
- The backup dependency set in
  `apps/SKape-os/backend/requirements-backup.txt`.
- Production backup activity, including scheduled backups, restores,
  and PITR.
- The R2 smoke harness, `python -m backup.smoke`.

Live R2 testing stays unauthorized. A staging deployment does not
change that.

## Rollback of an empty staging database

Use this procedure only when the staging database is disposable and
empty of data worth keeping:

1. Stop the staging API process.
2. Discard the staging database.
3. Create a new empty staging database.
4. Run `alembic upgrade head` against that new database before
   starting the API again.

This procedure must never be used against production. Discarding a
database is not a production rollback. `alembic downgrade` is not a
substitute for this empty-database procedure, and it does not restore
data removed by an upgrade.

## Evidence boundary

Record staging verification separately from production release
evidence. A successful staging migration and a ready response show
only that this revision started under the production checks against
the disposable staging database.

They do not provision production PostgreSQL, rotate production
secrets, measure backup retention, PITR, RPO, or RTO, or authorize a
production deployment. Completing the staging acceptance checklist
does not show that production backup, PITR, RPO, RTO, production
migration, production release, or live R2 testing is ready. Those
operations remain unauthorized. No staging verification is recorded
in this document.

## Staging acceptance checklist

The checklist has eleven rows. Each item stays `not recorded` until
its own evidence exists. A repository test does not check an item
that requires the disposable staging database or a chosen host.
Record only safe identifiers and yes/no confirmations. Do not record
connection strings, secret values, tokens, or environment values.

| Check | Required evidence | Status |
|---|---|---|
| Frontend lint, API URL tests, and production build | The frontend workflow, or the same local commands, on the revision being staged. The build uses an explicit HTTPS URL ending in `/api/v1`. | not recorded |
| Backend SQLite and PostgreSQL 16 CI | Both jobs in `.github/workflows/skape-os-backend.yml` succeed on that same revision. | not recorded |
| Disposable staging PostgreSQL migration | `alembic upgrade head` from `apps/SKape-os/backend` against the empty staging database, as its own step, before the API starts. | not recorded |
| Readiness endpoint | `GET /api/v1/health/ready` returns ready after that migration on PostgreSQL 16. `GET /api/v1/health/` is not sufficient. Another major version stays unavailable. | not recorded |
| HTTPS, CORS, and disabled API docs | `SKAPE_CORS_ORIGINS` is the staging frontend HTTPS origin with no path or wildcard. `/docs`, `/redoc`, and `/openapi.json` are absent. | not recorded |
| Staging resource and secret separation | The staging database is disposable and is not the production database. The staging signing secret differs from the production signing secret, and neither value is recorded. Staging does not contain production database credentials. The API process has no R2, object-storage, or backup credentials or environment variables. Record a database host name, a database name, and yes/no answers only. | not recorded |
| Authentication and organization isolation | On the staging API, repeat these cases from the repository tests. Unauthenticated `POST /api/v1/comments/`, `GET /api/v1/comments/1`, `PUT /api/v1/comments/1`, and `DELETE /api/v1/comments/1` return 401, as in `test_comments_require_authentication` in `apps/SKape-os/backend/tests/test_comments.py`. The authenticated organization owner created by `POST /api/v1/users/` can `POST /api/v1/projects/` and `POST /api/v1/tasks/` for a project in that organization, both returning 200, as in `test_project_task_comment_and_activity_workflow` in `apps/SKape-os/backend/tests/test_workflows.py`. That test checks cross-organization task access and expects 404 from `GET /api/v1/tasks/{id}`. `test_asset_assignment_stays_inside_the_organization` in the same file checks cross-organization asset access and expects 404 from `GET /api/v1/assets/{id}`. That workflow test and `test_api_crud_validation_and_tenant_boundaries` in `apps/SKape-os/backend/tests/test_comments.py` expect `GET /api/v1/comments/{task_id}` for the other organization to return 200 with an empty list. | not recorded |
| Frontend deep-link routing | Direct navigation to `/login` and `/dashboard`, and a refresh of each URL, returns the built `index.html`. Those paths are client routes in `apps/SKape-os/frontend/src/routes/AppRouter.tsx`. | not recorded |
| Device-monitor process count and shutdown | One API process is running. Stopping it stops the monitor. | not recorded |
| Rollback on the empty staging database | The empty-database procedure in this note is exercised on staging only. | not recorded |
| Evidence and production gates | Staging results are stored separately from production release evidence. Production migration, production release, backup, PITR, RPO, RTO measurement, and live R2 testing stay unauthorized. Passing the staging rows does not show production recovery readiness. | not recorded |
