"""Local PostgreSQL backup checks.

This package is not imported by the API process. It does not open a
database connection, upload a backup, or delete retained copies. It
does not start ``pg_dump`` or ``pg_restore``.
"""
