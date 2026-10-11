"""Local PostgreSQL backup checks.

This package is not imported by the API process. It does not open a
database connection, upload a backup, or delete retained copies.
``backup.runner`` starts a client only when a caller asks it to, and
that runner applies a finite timeout, process cleanup, and redacted
errors. ``backup.r2`` uploads a verified backup only when a caller
invokes it with an object store. It does not create a network client
and it does not delete objects. ``backup.r2_client`` adapts an injected
S3 client to that store. Its configuration names explicit credentials,
path-style addressing, checksum mode, finite timeouts, and a bounded
retry budget. It does not construct the client, read ambient
credentials, or delete objects. A download larger than 5 GiB is
rejected before it is read.
"""
