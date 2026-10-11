"""Local PostgreSQL backup checks.

This package is not imported by the API process. It does not open a
database connection, upload a backup, or delete retained copies.
``backup.runner`` starts a client only when a caller asks it to, and
that runner applies a finite timeout, process cleanup, and redacted
errors.
"""
