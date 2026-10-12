"""Logging helpers that keep secrets and database URLs out of logs."""

import logging
import re


LOGGER_NAME = "skape"

_URL = re.compile(
    r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"<>]+",
)
_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|authorization)\b"
    r"(\s*[:=]\s*)(\S+)"
)


def configure_logging():
    """Keep application loggers enabled after other tools configure logging."""

    names = [LOGGER_NAME]
    names.extend(
        name
        for name in logging.Logger.manager.loggerDict
        if name.startswith(f"{LOGGER_NAME}.")
    )
    for name in names:
        logger = logging.getLogger(name)
        logger.disabled = False
        logger.setLevel(logging.INFO)


def redact_sensitive(value):
    """Remove database URLs and assigned secrets from a log message."""

    if value is None:
        return ""
    text = _URL.sub("[redacted-url]", str(value))
    return _ASSIGNMENT.sub(r"\1\2[redacted]", text)


def get_logger(name):
    configure_logging()
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
