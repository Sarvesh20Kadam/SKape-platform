# PostgreSQL point-in-time recovery proof

This note describes the disposable point-in-time proof in
`apps/SKape-os/backend/tests/test_postgres_pitr.py`. It is a synthetic
test on an isolated PostgreSQL 16 cluster. It is not a production
recovery procedure, and a passing run does not establish a 24-hour
recovery point or a 4-hour recovery time.

## What the proof does

When `SKAPE_PITR_DRILL=1`, the test starts a new `postgres:16` container
with WAL archiving enabled at first startup. That container has its own
data volume, WAL archive volume, restore volume, network, published
ports, and generated role password. The existing `skape-pg-test`
container must already be present. The drill records its identity before
the proof and checks that same identity afterward. It does not start,
stop, reconfigure, or remove that container.

The test migrates one new database to the repository Alembic head,
loads two synthetic organizations, and takes a `pg_basebackup`. It then
commits project "PITR Transaction A", records a UTC timestamp from the
source database, and commits project "PITR Transaction B". Recovery of
a second container pauses at that timestamp.

The paused database must contain transaction A, must not contain
transaction B, and must be at the repository Alembic head. The test
promotes that server and then logs in, checks tenant isolation, creates
one follow-up project, and checks production readiness. The source
cluster must still contain both A and B. The follow-up project must
exist only on the promoted copy.

A successful run prints backup, replay, promote, and total durations,
the base-backup and archive sizes, the source target timestamp, the
replay timestamp, and the gap between them. Those numbers describe one
synthetic run. They do not prove a recovery-point or recovery-time
objective.

## What the proof does not do

It does not archive to a second site, encrypt backups, schedule
backups, or choose a hosting provider. It is not part of GitHub
Actions. It does not connect to the shared test database or to a
production database.

## Requirements

- Docker, with the local `postgres:16` image already present. The test
  does not pull an image.
- The existing `skape-pg-test` container must already be present, whether
  it is running or stopped. The drill records that container before the
  proof and checks it again afterward. It does not start, stop,
  reconfigure, or remove that container or its volume.
- Free localhost ports `55433` and `55434`.
- `SKAPE_PITR_DRILL=1`.

The proof does not read `SKAPE_TEST_DATABASE_URL`. Do not point it at a
production database. The cluster password is generated for the run and
is not printed.

## Run

From `apps/SKape-os/backend`:

```text
SKAPE_PITR_DRILL=1 python -m pytest -q tests/test_postgres_pitr.py
```

Without `SKAPE_PITR_DRILL=1`, the live proof is skipped. The offline
checks still run. With the flag set, a missing Docker engine, a busy
proof port, or an existing proof resource name fails the test. An
existing resource is left in place.

## Cleanup

Cleanup runs after success, failure, and a normal interruption. It
removes a container, volume, or network only when this run created it,
its name is in the `skape-pitr-` namespace, and it carries the proof
label. The shared test container and any resource that already existed
are not removal targets. A resource whose inspected name does not match
the name this run created is left in place.

## Production

Passing this proof shows that a synthetic PostgreSQL 16 cluster can
recover to a timestamp between two commits and then serve the checked
application calls. Production recovery still needs an off-host archive,
a measured restore of a production-sized copy, retention, and an
operational handover.
