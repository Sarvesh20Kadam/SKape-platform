# R2 smoke preflight record

Local inspection on 2026-10-11 did not select a bucket or authorize a
live run. `python -m backup.smoke` stays blocked until an operator
completes the external checks below and a separate explicit
authorization is given.

Locally verified repository facts describe this repository only.
External checks are a separate list and stay unverified until the
named person writes evidence. The decision gate is separate from
both, and live-test authorization is `not given`.

Do not write secrets, access keys, account IDs, or endpoint URLs in
this file. The bucket name is the only Cloudflare identifier it
should hold. A missing name in this repository does not prove that a
live bucket is unused.

## Locally verified repository facts

Local inspection date: 2026-10-11. These rows are repository facts.
They are not external evidence.

Source revision: `98fa4acd17e2cec8301b14a0cb02b489bfcabc6e`. No
Cloudflare account, host secret store, or `.env` file was read.

| Finding | Source |
|---|---|
| The production example names no R2 bucket and no `SKAPE_R2_*` variable. Its variables are `SKAPE_ENV`, `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, optional token expiry, `SKAPE_CORS_ORIGINS`, `SKAPE_ENABLE_API_DOCS`, and optional pool settings. The values are placeholders. | `apps/SKape-os/backend/.env.production.example` |
| Application code does not reference `SKAPE_R2`, `cloudflarestorage`, or `publish_remote_backup`. | `apps/SKape-os/backend/app/` |
| The Render note is a proposal. It says nothing in this repository is deployed to Render. Its proposed environment list has no R2 variable. Off-site backup storage is an unmet launch blocker. | `apps/SKape-os/docs/render-deployment.md` |
| No backup schedule, hosting platform, or production database is defined in the repository. | `apps/SKape-os/docs/production-startup.md` |
| The logical-recovery note defines no backup schedule, and this repository has not run the smoke harness against Cloudflare. | `apps/SKape-os/docs/postgres-recovery.md` |
| The PITR proof does not schedule backups, choose a host, or run in GitHub Actions. | `apps/SKape-os/docs/postgres-pitr.md` |
| Backend CI runs on push and pull request. The workflow has no `schedule` entry. No `render.yaml` is present. | `.github/workflows/skape-os-backend.yml` |
| Automated tests use synthetic bucket strings. Those strings are not a selected Cloudflare bucket. | `apps/SKape-os/backend/tests/test_backup_r2_smoke.py` |

A missing R2 name in the sources above does not prove that a live
bucket is unused. The `smoke-` name rule in the harness is a
syntactic guard only. It does not prove that a bucket is dedicated,
empty, or non-production.

## External checks

These rows are external evidence. They are not repository facts.
Every status stays `unverified`, and every evidence cell stays empty.
Do not record access keys, secret values, account IDs, endpoint URLs,
or other credentials in any cell.

| Check | Who verifies | Acceptable evidence | Do not record | Status | Evidence |
|---|---|---|---|---|---|
| Operator completion date | Hosting operator | The date these external rows were finished. | Credentials. | unverified | |
| Smoke operator | Hosting operator | The name of the person who would run the smoke shell. | Credentials. | unverified | |
| Dedicated non-production bucket | Bucket administrator | A sanitized inventory record: bucket name, and a statement that it was created empty for this smoke test. | Account ID, endpoint URL, and credentials. | unverified | |
| Bucket purpose | Bucket administrator | The same sanitized inventory record showing the bucket has no other use, plus the date of that check. | Account ID, endpoint URL, and credentials. | unverified | |
| Absent from production configuration | Hosting operator | An inspection result naming the live host secret store and stating whether the bucket name appeared. Repository templates are not that store. | Variable values and credentials. | unverified | |
| Absent from scheduled backup jobs | Hosting operator | An inspection result naming each host scheduler, Render job, and external backup job, and stating whether any job names this bucket. The missing GitHub Actions `schedule` entry does not cover those systems. | Job secrets and credentials. | unverified | |
| Absent from the live Render service | Hosting operator | An inspection result naming the service, or stating that no Render service exists, and stating whether any variable names this bucket. | Variable values and credentials. | unverified | |
| `logical/` contains no objects | Bucket administrator | An inspection result with the listing time and a statement that the `logical/` prefix returned no keys. Take it before any smoke run. Do not use `python -m backup.smoke`. | Endpoint URL and credentials. | unverified | |
| `logical/latest.json` is absent | Bucket administrator | An inspection result with the head time and a statement that `logical/latest.json` was absent. | Endpoint URL and credentials. | unverified | |
| `GetObject` allowed | Security/token administrator | A permission-policy summary naming the policy and stating that `GetObject` is allowed. | Access key, secret, account ID, and endpoint URL. | unverified | |
| `PutObject` allowed on the smoke keys only | Security/token administrator | A permission-policy summary stating that `PutObject` is limited to `logical/daily/smoke-*`. | Access key, secret, account ID, and endpoint URL. | unverified | |
| `ListBucket` allowed on this bucket | Security/token administrator | A permission-policy summary stating that `ListBucket` is allowed on this bucket. | Access key, secret, account ID, and endpoint URL. | unverified | |
| `DeleteObject` prohibited | Security/token administrator | A permission-policy summary stating that `DeleteObject` is absent. | Access key, secret, account ID, and endpoint URL. | unverified | |
| `CreateBucket` prohibited | Security/token administrator | A permission-policy summary stating that `CreateBucket` is absent. | Access key, secret, account ID, and endpoint URL. | unverified | |
| Bucket administration prohibited | Security/token administrator | A permission-policy summary stating that bucket administration is absent. | Access key, secret, account ID, and endpoint URL. | unverified | |
| `PutObject` on `logical/latest.json` prohibited | Security/token administrator | A permission-policy summary stating that `PutObject` on `logical/latest.json` is absent. | Access key, secret, account ID, and endpoint URL. | unverified | |
| `AWS_*` unset in the smoke shell | Hosting operator | An inspection result of the smoke shell stating `unset` for `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_PROFILE`, `AWS_CONFIG_FILE`, and `AWS_SHARED_CREDENTIALS_FILE`. | Any values those names hold. | unverified | |
| Different cleanup operator | Cleanup operator | The cleanup person's name and the cleanup principal's name. That person and principal are different from the smoke operator and the smoke token. | The cleanup principal's secrets. | unverified | |
| Separate live-test authorization | A separate approver who is not the smoke operator | The approver's name and the date, written only after every evidence cell above is filled and only by editing the decision gate below. | Credentials. | not given | |

## Decision gate

Filling an evidence cell does not change this gate. This handoff
leaves both lines as written.

Evidence complete: `no`

Live-test authorization: `not given`

Do not run `python -m backup.smoke` while either line still has that
value.

## Cleanup

The smoke token cannot delete. After an authorized run, a different
authorized principal deletes only the two keys that run reported:

- `logical/daily/<id>.dump`
- `logical/daily/<id>.json`

On success those keys are the two lines after `backup smoke completed`
on stdout. After a failure that starts an object operation, they are
the two key lines on stderr. A configuration or client-construction
failure prints no keys, and there is nothing to delete. Do not delete
`logical/latest.json` or any other object. Do not use the smoke token
for this deletion.

## Harness contract

Run the command from `apps/SKape-os/backend`:

`python -m backup.smoke`

The process reads these variables and no others:

| Variable | Accepted value |
|---|---|
| `SKAPE_R2_SMOKE` | Exactly `1`. Anything else exits with `backup smoke is not enabled` and does not construct a client. |
| `SKAPE_R2_ENDPOINT` | `https://` plus 32 lowercase hex digits plus `.r2.cloudflarestorage.com`. |
| `SKAPE_R2_REGION` | Exactly `auto`. |
| `SKAPE_R2_BUCKET` | 3–63 characters, `[a-z0-9][a-z0-9-]{1,61}[a-z0-9]`, starting with `smoke-`. A hyphen segment equal to `prod` or `production` is rejected. |
| `SKAPE_R2_ACCESS_KEY_ID` | 16–128 characters from `A–Z`, `a–z`, and `0–9`. |
| `SKAPE_R2_SECRET_ACCESS_KEY` | 32–256 characters from `A–Z`, `a–z`, `0–9`, `/`, `+`, and `=`. |

Any other shape exits with `backup smoke configuration is invalid`
before a client exists. Failure text does not include the secret, the
endpoint, or the bucket name.

Before the first object operation the harness chooses one UTC id,
`smoke-YYYYMMDDTHHMMSSZ-` plus 6 lowercase hex characters. The only
keys it may write are:

- `logical/daily/<id>.dump`
- `logical/daily/<id>.json`

It then heads `logical/latest.json`, exercises the dump key, exercises
the json key, and heads `logical/latest.json` again. Each exercise
heads the key, creates it with `If-None-Match: *`, requires the
duplicate create to fail, reads it back, replaces it with `If-Match`,
requires a stale `If-Match` to fail, and reads the replacement. The
second latest head must match the first. The harness does not write
`logical/latest.json`, call `publish_remote_backup`, create a bucket,
delete an object, or open a database.

Success prints `backup smoke completed` and both keys on stdout.
A failure after the run has started prints one fixed message and then
both keys on stderr. A configuration or client-construction failure
prints only the fixed message.

Stop and do not start another run when stderr shows any of these:

- `backup smoke object already exists`
- `backup object store failed`, including a missing-key HTTP 403 or an ETag that is not a quoted 32-hex value
- `backup smoke pointer changed`
- `backup smoke duplicate create succeeded`
- `backup smoke stale etag was accepted`
- `backup smoke download did not match`
- `backup smoke failed`

Cleanup follows the procedure above. The smoke token cannot delete.
