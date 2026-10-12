"""PostgreSQL Alembic coverage for the unpushed migration chain.

These tests use the disposable database created by
``test_device_monitor_postgres``. Each test migrates only that
database with Alembic commands, then the fixture drops it.

The device-monitor revision already has PostgreSQL upgrade, downgrade,
and refusal tests in that module. This file does not repeat them.
"""

import importlib.util
import logging
import os
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


ORG_PARENT = "ed02ec83e267"
ORG_NOT_NULL = "4a4fc62a3a6a"
ORG_DEFAULT = "c4e8a1b92f30"
EMAIL_REVISION = "e3a91c7b2d44"
EMAIL_INDEX = "ix_users_email_lower"
REFUSAL = "Accounts were not merged:"

_URL = os.environ.get("SKAPE_TEST_DATABASE_URL", "").strip()
_REQUIRE = os.environ.get("SKAPE_REQUIRE_POSTGRES") == "1"

if not _URL and not _REQUIRE:
    pytestmark = pytest.mark.skip(
        reason="SKAPE_TEST_DATABASE_URL is not set"
    )


@pytest.fixture(autouse=True)
def _postgres_gate():
    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.fail(
            "PostgreSQL migration tests must run serially"
        )
    if not _URL:
        pytest.fail("SKAPE_TEST_DATABASE_URL is required")


def _lab():
    path = Path(__file__).with_name(
        "test_device_monitor_postgres.py"
    )
    spec = importlib.util.spec_from_file_location(
        "skape_migration_chain_lab",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade(module, lab, revision):
    with lab.engine.connect() as connection:
        module._assert_identity(connection, lab.name)
    with module._migration_environment(lab.url, lab.name):
        command.upgrade(
            module._alembic_config(lab.url, lab.name),
            revision,
        )
    with lab.engine.connect() as connection:
        module._assert_identity(connection, lab.name)
    stored = module._revision(lab.engine, lab.name)
    if stored != revision:
        raise AssertionError(
            f"migration stopped at {stored!r}, expected {revision!r}"
        )


def _downgrade(module, lab, revision):
    with lab.engine.connect() as connection:
        module._assert_identity(connection, lab.name)
    with module._migration_environment(lab.url, lab.name):
        command.downgrade(
            module._alembic_config(lab.url, lab.name),
            revision,
        )
    with lab.engine.connect() as connection:
        module._assert_identity(connection, lab.name)
    stored = module._revision(lab.engine, lab.name)
    if stored != revision:
        raise AssertionError(
            f"downgrade stopped at {stored!r}, expected {revision!r}"
        )


def _active_column(connection):
    row = connection.execute(
        text(
            "SELECT is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = 'organizations' "
            "AND column_name = 'is_active'"
        )
    ).one()
    return row.is_nullable, row.column_default


def _flags(connection):
    return dict(
        connection.execute(
            text(
                "SELECT slug, is_active FROM organizations "
                "ORDER BY slug"
            )
        ).all()
    )


def _default_is_true(value):
    if value is None:
        return False
    compact = str(value).lower().replace(" ", "")
    return compact == "true" or compact.startswith("true::")


def _email_index(connection):
    return connection.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' "
            "AND indexname = :index_name"
        ),
        {"index_name": EMAIL_INDEX},
    ).scalar()


def _email_fingerprint(connection):
    return connection.execute(
        text(
            "SELECT COUNT(*)::int, "
            "COUNT(DISTINCT lower(email))::int, "
            "md5(coalesce(string_agg("
            "id::text || ':' || md5(email), "
            "',' ORDER BY id), '')) "
            "FROM users"
        )
    ).one()


def _refuse(module, lab, revision):
    observed = None
    logging.disable(logging.CRITICAL)
    try:
        with module._migration_environment(lab.url, lab.name):
            try:
                command.upgrade(
                    module._alembic_config(lab.url, lab.name),
                    revision,
                )
            except Exception as exc:
                observed = exc
    finally:
        logging.disable(logging.NOTSET)
    if observed is None:
        raise AssertionError("upgrade succeeded")
    message = module._runtime_text(observed)
    if REFUSAL not in message:
        raise AssertionError("upgrade failed without the fixed refusal")
    if module._revision(lab.engine, lab.name) != ORG_DEFAULT:
        raise AssertionError("refused upgrade changed the revision")


def test_postgres_organization_nulls_become_true_and_stay_true():
    module = _lab()
    with module.disposable_database(ORG_PARENT) as lab:
        with lab.engine.begin() as connection:
            module._assert_identity(connection, lab.name)
            connection.execute(
                text(
                    "INSERT INTO organizations "
                    "(name, slug, is_active) VALUES "
                    "('Missing flag', 'missing-flag', NULL), "
                    "('Disabled flag', 'disabled-flag', FALSE)"
                )
            )
        _upgrade(module, lab, ORG_NOT_NULL)
        with lab.engine.connect() as connection:
            flags = _flags(connection)
            nullable, _default = _active_column(connection)
        if flags != {
            "missing-flag": True,
            "disabled-flag": False,
        }:
            raise AssertionError("active flags were not backfilled")
        if nullable != "NO":
            raise AssertionError("is_active remained nullable")
        with pytest.raises(IntegrityError):
            with lab.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO organizations "
                        "(name, slug, is_active) VALUES "
                        "('Rejected', 'rejected-flag', NULL)"
                    )
                )
        _downgrade(module, lab, ORG_PARENT)
        with lab.engine.begin() as connection:
            flags = _flags(connection)
            nullable, _default = _active_column(connection)
            connection.execute(
                text(
                    "INSERT INTO organizations "
                    "(name, slug, is_active) VALUES "
                    "('New null', 'new-null-flag', NULL)"
                )
            )
            restored = _flags(connection)
        if flags["missing-flag"] is not True:
            raise AssertionError("downgrade restored a null")
        if flags["disabled-flag"] is not False:
            raise AssertionError("downgrade changed a false flag")
        if nullable != "YES":
            raise AssertionError("downgrade left the column required")
        if restored["new-null-flag"] is not None:
            raise AssertionError("downgrade still rejects null")


def test_postgres_server_default_is_removed_without_dropping_not_null():
    module = _lab()
    with module.disposable_database(ORG_NOT_NULL) as lab:
        _upgrade(module, lab, ORG_DEFAULT)
        with lab.engine.begin() as connection:
            module._assert_identity(connection, lab.name)
            nullable, default = _active_column(connection)
            connection.execute(
                text(
                    "INSERT INTO organizations (name, slug) "
                    "VALUES ('Defaulted', 'defaulted-flag')"
                )
            )
            flags = _flags(connection)
        if nullable != "NO" or not _default_is_true(default):
            raise AssertionError("server default was not installed")
        if flags["defaulted-flag"] is not True:
            raise AssertionError("omitted flag did not use the default")
        _downgrade(module, lab, ORG_NOT_NULL)
        with lab.engine.connect() as connection:
            nullable, default = _active_column(connection)
            flags = _flags(connection)
        if nullable != "NO" or default is not None:
            raise AssertionError(
                "downgrade did not keep NOT NULL without a default"
            )
        if flags["defaulted-flag"] is not True:
            raise AssertionError("downgrade changed the defaulted row")
        with pytest.raises(IntegrityError):
            with lab.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO organizations (name, slug) "
                        "VALUES ('No default', 'no-default-flag')"
                    )
                )
        with lab.engine.connect() as connection:
            if "no-default-flag" in _flags(connection):
                raise AssertionError("rejected insert was kept")


def test_postgres_email_index_is_created_by_alembic():
    module = _lab()
    with module.disposable_database(ORG_DEFAULT) as lab:
        _upgrade(module, lab, EMAIL_REVISION)
        with lab.engine.connect() as connection:
            module._assert_identity(connection, lab.name)
            definition = _email_index(connection)
        if definition is None or "UNIQUE" not in definition.upper():
            raise AssertionError("unique email index is missing")
        if "lower" not in definition.lower():
            raise AssertionError("email index is not an expression index")
        _downgrade(module, lab, ORG_DEFAULT)
        with lab.engine.connect() as connection:
            if _email_index(connection) is not None:
                raise AssertionError("email index survived downgrade")


def test_postgres_case_variant_emails_do_not_change_rows():
    module = _lab()
    with module.disposable_database(ORG_DEFAULT) as lab:
        with lab.engine.begin() as connection:
            module._assert_identity(connection, lab.name)
            organization_id = connection.execute(
                text(
                    "INSERT INTO organizations "
                    "(name, slug, is_active) "
                    "VALUES ('Email org', 'email-org', TRUE) "
                    "RETURNING id"
                )
            ).scalar()
            connection.execute(
                text(
                    "INSERT INTO users ("
                    "name, email, hashed_password, "
                    "organization_id, is_active"
                    ") VALUES "
                    "('One', 'alpha.one@example.test', "
                    "'test-hash', :organization_id, TRUE), "
                    "('Two', 'ALPHA.ONE@example.test', "
                    "'test-hash', :organization_id, TRUE)"
                ),
                {"organization_id": organization_id},
            )
            before = _email_fingerprint(connection)
            if _email_index(connection) is not None:
                raise AssertionError("email index existed too early")
        _refuse(module, lab, EMAIL_REVISION)
        with lab.engine.connect() as connection:
            module._assert_identity(connection, lab.name)
            after = _email_fingerprint(connection)
            if _email_index(connection) is not None:
                raise AssertionError("refused upgrade created the index")
        if before != after:
            raise AssertionError("refused upgrade changed user rows")
        if before[0] != 2 or before[1] != 1:
            raise AssertionError("case-variant seed was not stored")
