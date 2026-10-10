# PostgreSQL logical recovery drill

This note describes the disposable backup-and-restore drill in
`apps/SKape-os/backend/tests/test_postgres_recovery.py`. It is not a
production recovery procedure.

## What the drill proves

The drill creates a disposable database, migrates it to the current
Alembic head, and loads synthetic organizations, users, and a project
through the application API. It takes a custom-format logical backup
with `pg_dump`, restores that backup with `pg_restore` into a second
empty disposable database, and checks that the copy has the same schema
revision and records. It then logs in as those synthetic users, checks
that one organization cannot read the other's project, creates a project
only on the restored database, and confirms production readiness reports
ready.

## What the drill does not prove

A successful logical restore does not establish point-in-time recovery,
write-ahead-log archiving, off-site retention, an encryption-at-rest
policy, a tested recovery time objective, a tested recovery point
objective, or production recovery readiness. No backup schedule,
retention period, or hosting platform is defined here.

## Requirements

- PostgreSQL client tools `pg_dump` and `pg_restore` on `PATH`, at least
  as new as the server major version.
- If the tools are only inside the disposable PostgreSQL container, set
  `SKAPE_PG_DOCKER_CONTAINER` to that container name. Do not point it at
  a production instance.
- `SKAPE_RECOVERY_DRILL=1`
- `SKAPE_REQUIRE_POSTGRES=1`
- `SKAPE_TEST_DATABASE_URL` set to the administrative connection for the
  disposable test server.
- `SKAPE_PG_CLIENT_TIMEOUT_SECONDS` is optional. When unset, each client
  invocation stops after 60 seconds. A set value must be a whole number
  from 1 to 600. Host and Docker invocations use the same limit.

The administrative database must not be named `skape`, `postgres`,
`template0`, or `template1`, and it must not use a generated
`skape_test_` disposable name. The drill refuses those names before it
creates, dumps, restores, or drops anything.

Do not put production credentials in `SKAPE_TEST_DATABASE_URL` or in the
container setting. Do not point the drill at a production database.

## Run

From `apps/SKape-os/backend`, with the variables above set in the
environment and not printed:

```text
python -m pytest -q tests/test_postgres_recovery.py
```

Without `SKAPE_RECOVERY_DRILL=1`, the live drill is skipped. With the
drill enabled, a missing URL, a missing PostgreSQL requirement, or
missing client tools fails the test. It does not skip.

## How to read failures

- `SKAPE_TEST_DATABASE_URL is required`: the drill was enabled without
  an administrative connection.
- `SKAPE_REQUIRE_POSTGRES=1 is required`: the drill was enabled without
  the existing PostgreSQL guard.
- `pg_dump is required on PATH, or set SKAPE_PG_DOCKER_CONTAINER to the disposable PostgreSQL container`:
  `pg_dump` was not found. The same sentence with `pg_restore` means that
  tool was not found. The drill fails rather than skipping.
- `pg_dump and pg_restore must come from the same place`: one tool came
  from `PATH` and the other would have come from Docker.
- `pg_dump is older than the PostgreSQL server`: install a client whose
  major version is at least the server's.
- `pg_dump failed with status` or `pg_restore failed with status`: that
  client exited non-zero. Text after the status has connection URLs and
  the password removed. Do not treat a non-zero client status as a passed
  drill.
- `PostgreSQL client timed out after N seconds`: the client exceeded
  `SKAPE_PG_CLIENT_TIMEOUT_SECONDS` or the 60-second default. The message
  does not include the command, a connection URL, or a password. The
  local client process is killed and waited for. In Docker mode the same
  tool name is then signaled inside the container.
- A schema assertion failure means `alembic_version` on the restored
  database is not the repository head.
- A project, login, or tenant assertion failure means the restored data
  or the application checks against that database did not match the
  synthetic workflow.
- `refusing to operate on a non-disposable database` means a name failed
  the disposable-name check and no dump or restore continued for that
  name.
- `refusing to drop database` means the existing drop helper rejected the
  name before it opened a connection. No drop statement is issued.

## Cleanup

Each database is created by the existing disposable-database helper and
dropped by that helper on success and on failure. A drop runs only after
the generated name matches `skape_test_` plus 16 hexadecimal characters.
Protected names are not drop targets. The helper refuses those names
before it opens a connection to drop, and it closes the engines it
opened.

The custom-format backup stays in the test process's memory until the
test function returns. It is not written to a backup file or to the
temporary directory.

The temporary directory is used for a password file only when the client
tools run on the host. Docker mode does not write that file. On Unix the
host-mode file is set to mode `0600` before the client starts, so only
its owner can read and write it. Windows does not apply that Unix mode;
the file is still deleted when the test ends, and the password is not
placed on the command line. The directory and any file in it are removed
on success and on failure, including a failed dump, restore, or timeout.

## Production

Operators must not substitute production credentials or aim this drill
at a production database. Passing the drill only shows that a logical
backup of a synthetic disposable database can be restored and checked.
It does not replace a production backup, a restore rehearsal against a
copy of production data, or an operational handover.
