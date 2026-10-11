# PostgreSQL logical recovery drill

This note describes the disposable backup-and-restore drill in
`apps/SKape-os/backend/tests/test_postgres_recovery.py`. It is not a
production recovery procedure.

## What the drill proves

The drill creates a disposable database, migrates it to the current
Alembic head, and loads synthetic organizations, users, and a project
through the application API. It streams a custom-format logical backup
from `pg_dump` into a temporary `backup.dump` file, records a SHA-256
digest and the file size, and checks that same file again immediately
before `pg_restore`. A checksum mismatch stops the restore. The restore
goes into a second empty disposable database. The drill then checks the
schema revision and records, logs in as those synthetic users, checks
that one organization cannot read the other's project, creates a project
only on the restored database, and confirms production readiness reports
ready.

It also records three durations with a monotonic clock: the `pg_dump`
invocation, the `pg_restore` invocation, and the span from the start of
the dump through the final workflow checks. A successful run prints
those durations and the digest. The test checks that each duration is
zero or greater and that the total is at least the dump duration plus
the restore duration. It does not impose a maximum time.

## What the drill does not prove

A successful logical restore does not establish point-in-time recovery,
write-ahead-log archiving, off-site retention, an encryption-at-rest
policy, or production recovery readiness. No backup schedule, retention
period, or hosting platform is defined here. A separate synthetic
point-in-time proof is described in `postgres-pitr.md`. Passing that
proof is not production recovery readiness either.

The printed durations do not prove a proposed four-hour recovery time
objective or a proposed 24-hour recovery point objective. They describe
one synthetic run on the machine that executed the test.

`backup.r2.publish_remote_backup` can be exercised with an in-memory
object store. That test checks manifest, checksum, and pointer rules.
It does not contact Cloudflare R2, create a bucket, or prove off-site
retention, a recovery point objective, a recovery time objective, or
production recovery.

`backup.r2_client` adapts an injected S3 client to that same `head`,
`get`, and conditional `put` protocol. A missing object stays distinct
from a forbidden response. ETags remain quoted concurrency tokens.
`configure_r2_client` names explicit credentials, path-style
addressing, signature version `s3v4`, checksum calculation and
validation of `when_required`, a 10-second connect timeout, a 60-second
read timeout, and at most three standard-mode attempts. That retry mode
repeats the same request, so conditional headers stay on each attempt.
`create_r2_client` constructs that client from an explicit endpoint,
region, access key, and secret. It does not read ambient credentials,
create a bucket, or send a request. A download whose `ContentLength`
is missing, invalid, or larger than 5 GiB is rejected before it is read. Five GiB is the single `PutObject`
maximum. A response body that defines `close` is closed after success
and after rejection. Those tests use a fake client. They do not contact
Cloudflare R2 or create a bucket. `requirements-backup.txt` pins the
object-store client separately from the API requirements. CI does not
install that file. Compatibility of that pin with these client settings
is not established by an installed copy of the libraries.

## R2 smoke harness

`python -m backup.smoke`, run from `apps/SKape-os/backend`, is an opt-in
check for `R2Client`. It is not a recovery, retention, or PITR drill.
This repository has not run it against Cloudflare.

The harness reads only these variables. It does not itself read
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_PROFILE`, or a
credential file. Client construction passes the explicit smoke
credentials. A set `AWS_PROFILE` whose profile is missing can still
stop construction before any object operation. The smoke shell must
have the `AWS_*` names listed in `r2-smoke-preflight.md` unset. That
unset state is an external check and is not verified here.

A missing opt-in flag or a bucket name that fails the rule below
stops the process before a client is constructed. The `smoke-` rule
is a syntactic guard. Passing it does not prove the bucket is
dedicated, empty, or non-production. Complete `r2-smoke-preflight.md`
before any live run. That record keeps evidence complete at `no` and
live-test authorization at `not given` until a separate approval is
written there.

- `SKAPE_R2_SMOKE=1`
- `SKAPE_R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com`
- `SKAPE_R2_REGION=auto`
- `SKAPE_R2_BUCKET` must start with `smoke-` and must not contain a
  hyphen segment equal to `prod` or `production`.
- `SKAPE_R2_ACCESS_KEY_ID`
- `SKAPE_R2_SECRET_ACCESS_KEY`

The token needs `GetObject`, `PutObject`, and `ListBucket` on that
bucket. It must not have `DeleteObject`. The harness writes only
`logical/daily/smoke-<time>-<nonce>.dump` and the matching `.json`
key. It heads `logical/latest.json` before and after the writes and
does not write that key. It does not call `publish_remote_backup`,
create a bucket, or delete an object. Failures use fixed messages and
do not include the secret.

Cleanup is a separate operator action with a different principal.
The harness does not delete, and it does not open a database. On
success it prints both keys to stdout. If an object operation fails
after the run has started, stderr prints the fixed error and then
those same two keys. A configuration or client-construction failure,
before any object operation, prints only the fixed error and does not
list keys. Delete only the printed keys. The name check above does
not enforce this limit. Do not point this harness at a production
bucket.

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
  tool name is then signaled inside the container. A partial
  `backup.dump` is still removed.
- `pg_dump produced an empty backup`: the dump command exited zero and
  wrote no bytes.
- `pg_dump did not write a custom-format backup`: the file does not begin
  with the custom-format marker. The message does not include the file
  body.
- `backup checksum does not match`: the file size or SHA-256 digest
  changed after the dump. `pg_restore` is not started.
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

The test creates a temporary directory whose name starts with
`skape-recovery-`. `pg_dump` streams the custom-format archive to
`backup.dump` in that directory. Host and Docker execution both write
this host file. The test does not keep the complete archive as one in-memory byte
string. Docker does not use an in-container dump path. `pg_restore`
reads that same host file through stdin after the checksum check.

The temporary directory also holds a password file when the client tools
run on the host. Docker mode does not write that password file. On Unix
the host-mode file is set to mode `0600` before the client starts, so
only its owner can read and write it. Windows does not apply that Unix
mode; the file is still deleted when the test ends, and the password is
not placed on the command line.

Cleanup removes files only inside a directory whose name starts with
`skape-recovery-`, then removes that directory. It runs on success and
on failure, including a checksum mismatch, a failed dump, a failed
restore, a timeout, and an assertion failure. A partial `backup.dump`
is included. Protected and unrelated databases are not drop targets.

## Production

Operators must not substitute production credentials or aim this drill
at a production database. Passing the drill only shows that a logical
backup of a synthetic disposable database can be restored and checked.
It does not replace a production backup, a restore rehearsal against a
copy of production data, or an operational handover.
