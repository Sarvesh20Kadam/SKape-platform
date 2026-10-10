"""Expected Alembic revisions, read from the script directory only.

This module does not open a database connection and does not run
migrations. Production readiness compares a database to these heads.
The script location is an absolute path. Alembic's config loader is
not used, because the repository ini prepends the working directory
to ``sys.path``.
"""

import configparser
from pathlib import Path

from alembic.script import ScriptDirectory
from alembic.util import CommandError


_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _BACKEND_ROOT / "alembic.ini"


class SchemaRevisionError(RuntimeError):
    """The migration scripts do not define a usable head."""


def _script_location(config_path=None):
    """Resolve ``script_location`` from an ini file, relative to that file."""

    selected = Path(config_path) if config_path else _ALEMBIC_INI
    if not selected.is_file():
        raise SchemaRevisionError(
            "Alembic configuration is unavailable."
        )
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(selected, encoding="utf-8"):
        raise SchemaRevisionError(
            "Alembic configuration is unavailable."
        )
    if not parser.has_option("alembic", "script_location"):
        raise SchemaRevisionError(
            "Alembic configuration is unavailable."
        )
    raw = parser.get("alembic", "script_location").strip()
    if not raw:
        raise SchemaRevisionError(
            "Alembic configuration is unavailable."
        )
    here = selected.resolve().parent
    location = Path(raw.replace("%(here)s", str(here)))
    if not location.is_absolute():
        location = here / location
    return location.resolve()


def expected_schema_revisions(config_path=None):
    """Return the head revision ids from an Alembic script directory."""

    location = _script_location(config_path)
    try:
        script = ScriptDirectory(str(location))
    except CommandError:
        raise SchemaRevisionError(
            "Alembic script directory has no head."
        ) from None
    heads = frozenset(script.get_heads())
    if not heads:
        raise SchemaRevisionError(
            "Alembic script directory has no head."
        )
    return heads


def schema_revisions_match(current, expected):
    """True when the database revisions are exactly the expected heads."""

    found = frozenset(str(item) for item in current if item)
    required = frozenset(str(item) for item in expected if item)
    return bool(required) and found == required
