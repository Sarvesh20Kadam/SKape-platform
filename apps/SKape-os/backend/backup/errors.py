"""Failures whose messages do not include secrets or database URLs."""


class BackupError(RuntimeError):
    """A backup check failed closed."""
