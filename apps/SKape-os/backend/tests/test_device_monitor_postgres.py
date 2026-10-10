"""PostgreSQL concurrency tests for device monitoring.

These tests use disposable databases created from SKAPE_TEST_DATABASE_URL.
Alembic reads its script location from alembic.ini. Each migration sets
DATABASE_URL to that new database for the command, then restores the
previous value. Migrations run only against that new database.

Run this module serially. A pytest-xdist worker fails the module.
"""

import os
import re
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.crud.alert import create_alert, get_active_device_alert
from app.crud.device import heartbeat_device, mark_stale_devices_offline
from app.models.alert import Alert
from app.models.device import Device
from app.models.organization import Organization
from app.services.device_monitor import (
    MONITOR_ADVISORY_LOCK_KEY,
    run_monitor_cycle,
)


ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
PARENT_REVISION = "e3a91c7b2d44"
HEAD_REVISION = "f6b1c0a84e22"
DISPOSABLE_NAME = re.compile(r"^skape_test_[0-9a-f]{16}$")
FORBIDDEN_DATABASES = frozenset(
    {"skape", "postgres", "template0", "template1"}
)
LOCK_WAIT_SECONDS = 5.0
INDEX_NAME = "uq_alerts_unresolved_device_offline"
CHECK_NAME = "ck_devices_online_requires_last_seen"
_SECRET_URL = re.compile(r"postgresql(?:\+\w+)?://\S+", re.IGNORECASE)

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
            "PostgreSQL device-monitor tests must run serially"
        )
    if not _URL:
        pytest.fail("SKAPE_TEST_DATABASE_URL is required")
    _assert_safe_admin_url(_URL)


class Lab:
    def __init__(self, engine, url, name):
        self.engine = engine
        self.url = url
        self.name = name
        self.sessions = []
        self.connections = []
        self.workers = []
        self.releases = []
        self._session_factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
        )

    def session(self):
        db = self._session_factory()
        self.sessions.append(db)
        return db

    def referee(self):
        connection = self.engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        )
        self.connections.append(connection)
        return connection

    def track(self, thread, box, release):
        self.workers.append((thread, box))
        if release not in self.releases:
            self.releases.append(release)

    def close(self):
        """Roll back and close every session and referee connection.

        Listener removal happens first so a pause hook cannot block
        cleanup. Errors are returned so the caller can attach them to
        the original test failure.
        """

        errors = []
        for db in self.sessions:
            errors.extend(_remove_listeners(db))
            try:
                db.rollback()
            except Exception as exc:
                errors.append(exc)
            try:
                db.close()
            except Exception as exc:
                errors.append(exc)
        for connection in self.connections:
            try:
                connection.close()
            except Exception as exc:
                errors.append(exc)
        self.sessions.clear()
        self.connections.clear()
        return errors


def _assert_safe_admin_url(url):
    parsed = make_url(url)
    if not parsed.drivername.startswith("postgresql"):
        pytest.fail(
            "SKAPE_TEST_DATABASE_URL must be a PostgreSQL URL"
        )
    database = parsed.database or ""
    if database in FORBIDDEN_DATABASES:
        pytest.fail(
            f"refusing admin database {database!r}"
        )
    if DISPOSABLE_NAME.fullmatch(database):
        pytest.fail(
            "admin database must not use a disposable test name"
        )
    if not database:
        pytest.fail("SKAPE_TEST_DATABASE_URL has no database name")
    return parsed


def _admin_marker(connection):
    return connection.execute(
        text("SELECT to_regclass('public.alembic_version')")
    ).scalar()


def _assert_identity(connection, expected_name):
    current = connection.execute(
        text("SELECT current_database()")
    ).scalar()
    if (
        current != expected_name
        or not DISPOSABLE_NAME.fullmatch(current or "")
    ):
        raise RuntimeError(
            f"refusing database operation on {current!r}"
        )


def _error_note(exc):
    message = _SECRET_URL.sub("postgresql://...", str(exc))
    return f"cleanup: {type(exc).__name__}: {message}"


def _for_report(exc):
    if _SECRET_URL.search(str(exc)):
        return RuntimeError(_error_note(exc))
    return exc


def _surface(errors, pending=None):
    """Raise cleanup errors, or attach them to the original failure."""

    if pending is None:
        pending = sys.exc_info()[1]
    if not errors:
        return
    if pending is not None:
        for error in errors:
            pending.add_note(_error_note(error))
        return
    reported = [_for_report(error) for error in errors]
    if len(reported) == 1:
        raise reported[0]
    raise ExceptionGroup(
        "disposable database cleanup failed",
        reported,
    )


def _assert_admin_unchanged(admin_engine, database, marker):
    with admin_engine.connect() as admin:
        current = admin.execute(
            text("SELECT current_database()")
        ).scalar()
        if current != database or current in FORBIDDEN_DATABASES:
            raise RuntimeError(
                f"admin connection changed to {current!r}"
            )
        if DISPOSABLE_NAME.fullmatch(current or ""):
            raise RuntimeError(
                f"admin connection is a disposable database {current!r}"
            )
        if _admin_marker(admin) != marker:
            raise RuntimeError(
                "admin database schema marker changed"
            )


def _database_in_use(exc):
    message = str(exc).lower()
    return (
        "being accessed by other users" in message
        or "object_in_use" in message
    )


def _drop_database(admin_engine, name):
    if not DISPOSABLE_NAME.fullmatch(name):
        raise RuntimeError(
            f"refusing to drop database {name!r}"
        )
    deadline = time.monotonic() + 5
    while True:
        try:
            with admin_engine.connect() as connection:
                current = connection.execute(
                    text("SELECT current_database()")
                ).scalar()
                if (
                    current in FORBIDDEN_DATABASES
                    or current == name
                    or DISPOSABLE_NAME.fullmatch(current or "")
                ):
                    raise RuntimeError(
                        f"refusing to drop from connection {current!r}"
                    )
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) "
                        "FROM pg_stat_activity "
                        "WHERE datname = :name "
                        "AND pid <> pg_backend_pid()"
                    ),
                    {"name": name},
                )
                connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{name}"')
                )
            return
        except RuntimeError:
            raise
        except OperationalError as exc:
            if (
                not _database_in_use(exc)
                or time.monotonic() >= deadline
            ):
                raise
            time.sleep(0.1)


@contextmanager
def disposable_database(migrate_to):
    """Create a new database, migrate only that database, then drop it."""

    parsed = _assert_safe_admin_url(_URL)
    name = f"skape_test_{uuid.uuid4().hex[:16]}"
    if not DISPOSABLE_NAME.fullmatch(name):
        raise RuntimeError(
            f"refusing generated database name {name!r}"
        )

    created = False
    marker = None
    marker_known = False
    admin_engine = None
    engine = None
    lab = None
    body_error = None
    try:
        admin_engine = create_engine(
            _URL,
            isolation_level="AUTOCOMMIT",
            poolclass=NullPool,
        )
        with admin_engine.connect() as admin:
            current = admin.execute(
                text("SELECT current_database()")
            ).scalar()
            if current != parsed.database or current in FORBIDDEN_DATABASES:
                raise RuntimeError(
                    f"refusing admin connection to {current!r}"
                )
            marker = _admin_marker(admin)
            marker_known = True
            admin.execute(text(f'CREATE DATABASE "{name}"'))
            created = True

        target_url = parsed.set(database=name).render_as_string(
            hide_password=False
        )
        engine = create_engine(
            target_url,
            isolation_level="READ COMMITTED",
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
        )
        with engine.connect() as connection:
            _assert_identity(connection, name)
        if migrate_to is not None:
            _migrate(engine, target_url, name, migrate_to)

        lab = Lab(engine, target_url, name)
        try:
            yield lab
        except BaseException as exc:
            body_error = exc
            raise
    finally:
        errors = []
        if marker_known and admin_engine is not None:
            try:
                _assert_admin_unchanged(
                    admin_engine,
                    parsed.database,
                    marker,
                )
            except Exception as exc:
                errors.append(exc)
        if lab is not None:
            errors.extend(
                _collect_workers(lab.workers, lab.releases, lab)
            )
            if any(thread.is_alive() for thread, _box in lab.workers):
                errors.append(
                    RuntimeError(
                        "sessions and event listeners were left in "
                        "place because a worker was still running"
                    )
                )
            else:
                errors.extend(lab.close())
        if engine is not None:
            try:
                engine.dispose()
            except Exception as exc:
                errors.append(exc)
        if created and admin_engine is not None:
            try:
                _drop_database(admin_engine, name)
            except Exception as exc:
                errors.append(exc)
        if admin_engine is not None:
            try:
                admin_engine.dispose()
            except Exception as exc:
                errors.append(exc)
        _surface(errors, body_error)


def _alembic_config(url, name):
    if not DISPOSABLE_NAME.fullmatch(name):
        raise RuntimeError(
            f"refusing Alembic config for {name!r}"
        )
    configured = make_url(url)
    if configured.database != name:
        raise RuntimeError(
            "Alembic URL does not match the disposable database"
        )
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option(
        "sqlalchemy.url",
        url.replace("%", "%%"),
    )
    cfg.set_main_option("prepend_sys_path", str(BACKEND_ROOT))
    if make_url(cfg.get_main_option("sqlalchemy.url")).database != name:
        raise RuntimeError(
            "Alembic is not pointed at the disposable database"
        )
    return cfg


def _revision(engine, name):
    with engine.connect() as connection:
        _assert_identity(connection, name)
        present = connection.execute(
            text("SELECT to_regclass('public.alembic_version')")
        ).scalar()
        if present is None:
            return None
        return connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()


def _index_definition(engine, name):
    with engine.connect() as connection:
        _assert_identity(connection, name)
        return connection.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' "
                "AND indexname = :index_name"
            ),
            {"index_name": INDEX_NAME},
        ).scalar()


def _check_definition(engine, name):
    with engine.connect() as connection:
        _assert_identity(connection, name)
        return connection.execute(
            text(
                "SELECT pg_get_constraintdef(oid) "
                "FROM pg_constraint "
                "WHERE conname = :check_name"
            ),
            {"check_name": CHECK_NAME},
        ).scalar()


@contextmanager
def _migration_environment(url, name):
    """Expose one disposable database as DATABASE_URL, then restore it."""

    parsed = make_url(url)
    if (
        not DISPOSABLE_NAME.fullmatch(name)
        or parsed.database != name
    ):
        raise RuntimeError(
            "refusing to select a migration database"
        )
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _migrate(engine, url, name, revision):
    with engine.connect() as connection:
        _assert_identity(connection, name)
    before = _revision(engine, name)
    with _migration_environment(url, name):
        command.upgrade(_alembic_config(url, name), revision)
    with engine.connect() as connection:
        _assert_identity(connection, name)
    after = _revision(engine, name)
    expected = HEAD_REVISION if revision == "head" else revision
    if after != expected:
        raise RuntimeError(
            f"migration stopped at {after!r}, expected {expected!r}"
        )
    if revision == HEAD_REVISION and before == HEAD_REVISION:
        raise RuntimeError(
            "refusing to treat an already-migrated database as fresh"
        )
    return after


def _downgrade(lab, revision):
    with lab.engine.connect() as connection:
        _assert_identity(connection, lab.name)
    if _revision(lab.engine, lab.name) != HEAD_REVISION:
        raise RuntimeError(
            "downgrade preflight expected the monitor revision"
        )
    if _index_definition(lab.engine, lab.name) is None:
        raise RuntimeError("downgrade preflight missing unique index")
    if _check_definition(lab.engine, lab.name) is None:
        raise RuntimeError("downgrade preflight missing check")
    with _migration_environment(lab.url, lab.name):
        command.downgrade(
            _alembic_config(lab.url, lab.name),
            revision,
        )
    with lab.engine.connect() as connection:
        _assert_identity(connection, lab.name)
    if _revision(lab.engine, lab.name) != revision:
        raise RuntimeError("downgrade did not land on the parent revision")
    if _index_definition(lab.engine, lab.name) is not None:
        raise RuntimeError("unique index survived downgrade")
    if _check_definition(lab.engine, lab.name) is not None:
        raise RuntimeError("check constraint survived downgrade")


def _runtime_text(exc):
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, RuntimeError):
            return str(current)
        current = current.__cause__ or current.__context__
    return ""


def _assert_constraints_absent(lab):
    if _index_definition(lab.engine, lab.name) is not None:
        raise AssertionError("unique index was created")
    if _check_definition(lab.engine, lab.name) is not None:
        raise AssertionError("check constraint was created")


def _assert_clocks(db):
    db_now = db.execute(text("SELECT clock_timestamp()")).scalar()
    if db_now.tzinfo is None:
        db_now = db_now.replace(tzinfo=timezone.utc)
    skew = abs(
        (db_now - datetime.now(timezone.utc)).total_seconds()
    )
    if skew >= 5:
        pytest.fail(
            "PostgreSQL and application clocks differ by "
            f"{skew:.3f} seconds"
        )


def _pid(db):
    return db.execute(text("SELECT pg_backend_pid()")).scalar()


def _txid(db):
    return db.execute(text("SELECT txid_current()")).scalar()


def _seed_organization(db, slug):
    organization = Organization(
        name=slug,
        slug=slug,
        is_active=True,
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)
    return organization


def _seed_stale_device(db, organization, device_key):
    _assert_clocks(db)
    device = Device(
        device_id=device_key,
        name=device_key,
        device_type="sensor",
        status="offline",
        organization_id=organization.id,
        is_active=True,
    )
    db.add(device)
    db.commit()
    db.execute(
        text(
            "UPDATE devices "
            "SET status = 'online', "
            "last_seen_at = clock_timestamp() "
            "- interval '5 minutes' "
            "WHERE id = :device_id"
        ),
        {"device_id": device.id},
    )
    db.commit()
    db.refresh(device)
    return device


def _listen(db, identifier, fn):
    event.listen(db, identifier, fn)
    db.info.setdefault("_skape_listeners", []).append((identifier, fn))


def _remove_listeners(db):
    errors = []
    for identifier, fn in db.info.pop("_skape_listeners", []):
        try:
            event.remove(db, identifier, fn)
        except Exception as exc:
            errors.append(exc)
    return errors


def _pause_after_flush(db, paused, release):
    state = {"fired": False}

    def _pause(_session, _flush_context):
        if state["fired"]:
            return
        state["fired"] = True
        paused.set()
        if not release.wait(15):
            raise TimeoutError("lock holder was not released")

    _listen(db, "after_flush", _pause)
    return _pause


def _pause_after_device_update(db, paused, release):
    """Pause after the stale device UPDATE and before alert creation.

    ``after_cursor_execute`` is a connection event. Capturing
    ``session.connection()`` before ``mark_stale_devices_offline``
    misses the UPDATE: that function rolls back a clean session, and
    the next statement can use a different connection object.
    ``do_orm_execute`` wraps this session's ``Session.execute``.
    ``invoke_statement`` runs the UPDATE without entering the hook
    again, so the pause starts only after that statement is in the
    open transaction.
    """

    state = {"fired": False}

    def _pause(orm_execute_state):
        if state["fired"] or not orm_execute_state.is_update:
            return
        table = getattr(orm_execute_state.statement, "table", None)
        if getattr(table, "name", None) != "devices":
            return
        state["fired"] = True
        result = orm_execute_state.invoke_statement()
        paused.set()
        if not release.wait(15):
            raise TimeoutError("lock holder was not released")
        return result

    _listen(db, "do_orm_execute", _pause)
    return _pause


def _start(fn):
    box = {}

    def target():
        try:
            box["result"] = fn(box)
        except BaseException as exc:
            box["error"] = exc

    thread = threading.Thread(
        target=target,
        name="skape-pg-worker",
        daemon=True,
    )
    thread.start()
    return thread, box


def _take_worker_error(box, errors):
    error = box.get("error")
    if error is None or box.get("reported"):
        return
    box["reported"] = True
    errors.append(error)


def _terminate_other_backends(lab):
    try:
        with lab.engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            _assert_identity(connection, lab.name)
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = current_database() "
                    "AND pid <> pg_backend_pid()"
                )
            )
    except Exception as exc:
        return [exc]
    return []


def _collect_workers(pairs, releases, lab):
    """Unblock and join workers. Return errors without raising them."""

    signaled = []
    for release in releases:
        if release in signaled:
            continue
        release.set()
        signaled.append(release)
    errors = []
    pending = []
    for thread, box in pairs:
        thread.join(15)
        if thread.is_alive():
            pending.append((thread, box))
        else:
            _take_worker_error(box, errors)
    if not pending or lab is None:
        return errors
    errors.extend(_terminate_other_backends(lab))
    still = []
    for thread, box in pending:
        thread.join(10)
        if thread.is_alive():
            still.append((thread, box))
        else:
            _take_worker_error(box, errors)
    for _thread, box in still:
        errors.append(
            RuntimeError(
                "worker still running after the release signal and "
                "backend termination; it cannot be force-stopped"
            )
        )
        _take_worker_error(box, errors)
    return errors


def _join_workers(pairs, releases, lab):
    _surface(_collect_workers(pairs, releases, lab))


def _wait_for_lock(referee, waiter_pid, holder_pid, wait_event):
    deadline = datetime.now(timezone.utc).timestamp() + LOCK_WAIT_SECONDS
    last = None
    while datetime.now(timezone.utc).timestamp() < deadline:
        row = referee.execute(
            text(
                """
                SELECT
                    waiter.wait_event_type,
                    waiter.wait_event,
                    waiter.state AS waiter_state,
                    pg_blocking_pids(:waiter) AS blockers,
                    holder.state AS holder_state,
                    EXISTS (
                        SELECT 1 FROM pg_locks
                        WHERE pid = :waiter AND NOT granted
                    ) AS waiting
                FROM pg_stat_activity AS waiter
                LEFT JOIN pg_stat_activity AS holder
                    ON holder.pid = :holder
                WHERE waiter.pid = :waiter
                """
            ),
            {"waiter": waiter_pid, "holder": holder_pid},
        ).one()
        blockers = list(row.blockers or [])
        last = {
            "wait_event_type": row.wait_event_type,
            "wait_event": row.wait_event,
            "waiter_state": row.waiter_state,
            "holder_state": row.holder_state,
            "blockers": blockers,
            "waiting": row.waiting,
        }
        if (
            row.wait_event_type == "Lock"
            and row.wait_event == wait_event
            and row.waiting
            and holder_pid in blockers
            and row.holder_state in {"idle in transaction", "active"}
        ):
            return last
        threading.Event().wait(0.02)
    pytest.fail(
        f"pid {waiter_pid} did not reach a {wait_event} lock wait "
        f"behind pid {holder_pid}: {last}"
    )


def _wait_until(event, label):
    if not event.wait(15):
        pytest.fail(f"timed out waiting for {label}")


def _require_pid(box):
    if "pid" not in box:
        if "error" in box:
            raise box["error"]
        pytest.fail("worker did not publish its backend pid")
    return box["pid"]


def _device_row(connection, device_pk):
    return connection.execute(
        text(
            "SELECT status, last_seen_at FROM devices WHERE id = :id"
        ),
        {"id": device_pk},
    ).one()


def _offline_alerts(connection, device_pk):
    return connection.execute(
        text(
            "SELECT id, is_resolved FROM alerts "
            "WHERE device_id = :device_id "
            "AND alert_type = 'device_offline' "
            "ORDER BY id"
        ),
        {"device_id": device_pk},
    ).all()


def test_heartbeat_lock_keeps_a_newer_contact_online():
    with disposable_database("head") as lab:
        setup = lab.session()
        organization = _seed_organization(setup, "heartbeat-wins")
        device = _seed_stale_device(
            setup, organization, "pump-heartbeat-wins"
        )
        device_pk = device.id
        seen_before = device.last_seen_at
        setup.close()

        heartbeat = lab.session()
        monitor = lab.session()
        referee = lab.referee()
        paused = threading.Event()
        release = threading.Event()
        _pause_after_flush(heartbeat, paused, release)
        workers = []
        try:
            def run_heartbeat(box):
                box["pid"] = _pid(heartbeat)
                return heartbeat_device(
                    heartbeat, "pump-heartbeat-wins"
                )

            monitor_started = threading.Event()

            def run_monitor(box):
                box["pid"] = _pid(monitor)
                monitor_started.set()
                return mark_stale_devices_offline(
                    monitor, timeout_seconds=30
                )

            heartbeat_thread, heartbeat_box = _start(run_heartbeat)
            workers.append((heartbeat_thread, heartbeat_box))
            lab.track(heartbeat_thread, heartbeat_box, release)
            _wait_until(paused, "heartbeat flush")
            monitor_thread, monitor_box = _start(run_monitor)
            workers.append((monitor_thread, monitor_box))
            lab.track(monitor_thread, monitor_box, release)
            _wait_until(monitor_started, "monitor pid")
            _wait_for_lock(
                referee,
                _require_pid(monitor_box),
                _require_pid(heartbeat_box),
                "transactionid",
            )
            release.set()
            _join_workers(workers, [release], lab)
            workers = []
            assert monitor_box["result"] == []
            stored = _device_row(referee, device_pk)
            assert stored.status == "online"
            assert stored.last_seen_at > seen_before
            assert _offline_alerts(referee, device_pk) == []
        finally:
            _join_workers(workers, [release], lab)


def test_monitor_lock_commits_offline_then_heartbeat_resolves_it():
    with disposable_database("head") as lab:
        setup = lab.session()
        organization = _seed_organization(setup, "monitor-first")
        device = _seed_stale_device(
            setup, organization, "pump-monitor-first"
        )
        device_pk = device.id
        seen_before = device.last_seen_at
        setup.close()

        monitor = lab.session()
        heartbeat = lab.session()
        referee = lab.referee()
        paused = threading.Event()
        release = threading.Event()
        workers = []
        try:
            def run_monitor(box):
                box["pid"] = _pid(monitor)
                _pause_after_device_update(monitor, paused, release)
                run_monitor_cycle(monitor, timeout_seconds=30)

            heartbeat_started = threading.Event()

            def run_heartbeat(box):
                box["pid"] = _pid(heartbeat)
                heartbeat_started.set()
                return heartbeat_device(
                    heartbeat, "pump-monitor-first"
                )

            monitor_thread, monitor_box = _start(run_monitor)
            workers.append((monitor_thread, monitor_box))
            lab.track(monitor_thread, monitor_box, release)
            _wait_until(paused, "stale update")
            heartbeat_thread, heartbeat_box = _start(run_heartbeat)
            workers.append((heartbeat_thread, heartbeat_box))
            lab.track(heartbeat_thread, heartbeat_box, release)
            _wait_until(heartbeat_started, "heartbeat pid")
            _wait_for_lock(
                referee,
                _require_pid(heartbeat_box),
                _require_pid(monitor_box),
                "transactionid",
            )
            release.set()
            _join_workers(workers, [release], lab)
            workers = []
            stored = _device_row(referee, device_pk)
            assert stored.status == "online"
            assert stored.last_seen_at > seen_before
            alerts = _offline_alerts(referee, device_pk)
            assert len(alerts) == 1
            assert alerts[0].is_resolved is True
        finally:
            _join_workers(workers, [release], lab)


def _open_alert_race(lab, slug, hold):
    setup = lab.session()
    organization = _seed_organization(setup, slug)
    device = Device(
        device_id=slug,
        name=slug,
        device_type="sensor",
        status="offline",
        organization_id=organization.id,
        is_active=True,
    )
    setup.add(device)
    setup.commit()
    device_pk = device.id
    organization_id = organization.id
    setup.close()

    holder = lab.session()
    waiter = lab.session()
    referee = lab.referee()
    paused = threading.Event()
    release = threading.Event()
    _pause_after_flush(holder, paused, release)
    workers = []

    def alert_kwargs(db):
        return {
            "db": db,
            "device_id": device_pk,
            "organization_id": organization_id,
            "severity": "critical",
            "alert_type": "device_offline",
            "title": "Device Offline",
            "message": slug,
        }

    try:
        def run_holder(box):
            box["pid"] = _pid(holder)
            created = create_alert(**alert_kwargs(holder))
            box["created"] = created[1]
            box["alert_id"] = created[0].id
            hold(holder)

        def run_waiter(box):
            box["pid"] = _pid(waiter)
            other = Alert(
                device_id=device_pk,
                organization_id=organization_id,
                severity="warning",
                alert_type="high_temperature",
                title="Hot",
                message="Warm",
                is_resolved=False,
            )
            waiter.add(other)
            waiter.flush()
            box["txid"] = _txid(waiter)
            waiter_started.set()
            found = create_alert(**alert_kwargs(waiter))
            box["txid_after"] = _txid(waiter)
            box["nested"] = waiter.in_nested_transaction()
            box["in_transaction"] = waiter.in_transaction()
            box["created"] = found[1]
            box["alert_id"] = found[0].id
            waiter.commit()

        waiter_started = threading.Event()
        holder_thread, holder_box = _start(run_holder)
        workers.append((holder_thread, holder_box))
        lab.track(holder_thread, holder_box, release)
        _wait_until(paused, "holder alert flush")
        waiter_thread, waiter_box = _start(run_waiter)
        workers.append((waiter_thread, waiter_box))
        lab.track(waiter_thread, waiter_box, release)
        _wait_until(waiter_started, "waiter pid")
        _wait_for_lock(
            referee,
            _require_pid(waiter_box),
            _require_pid(holder_box),
            "transactionid",
        )
        release.set()
        _join_workers(workers, [release], lab)
        workers = []
        return referee, device_pk, holder_box, waiter_box
    finally:
        _join_workers(workers, [release], lab)


def test_losing_alert_insert_waits_and_keeps_its_outer_transaction():
    with disposable_database("head") as lab:
        referee, device_pk, holder_box, waiter_box = _open_alert_race(
            lab,
            "alert-loser",
            lambda holder: holder.commit(),
        )
        assert holder_box["created"] is True
        assert waiter_box["created"] is False
        assert waiter_box["alert_id"] == holder_box["alert_id"]
        assert waiter_box["txid_after"] == waiter_box["txid"]
        assert waiter_box["nested"] is False
        assert waiter_box["in_transaction"] is True
        alerts = _offline_alerts(referee, device_pk)
        assert len(alerts) == 1
        assert alerts[0].id == holder_box["alert_id"]
        assert alerts[0].is_resolved is False
        other = referee.execute(
            text(
                "SELECT count(*) FROM alerts "
                "WHERE alert_type = 'high_temperature'"
            )
        ).scalar()
        assert other == 1


def test_waiting_alert_insert_succeeds_when_holder_rolls_back():
    with disposable_database("head") as lab:
        referee, device_pk, holder_box, waiter_box = _open_alert_race(
            lab,
            "alert-rollback",
            lambda holder: holder.rollback(),
        )
        assert holder_box["created"] is True
        assert waiter_box["created"] is True
        assert waiter_box["alert_id"] != holder_box["alert_id"]
        assert waiter_box["txid_after"] == waiter_box["txid"]
        assert waiter_box["nested"] is False
        assert waiter_box["in_transaction"] is True
        alerts = _offline_alerts(referee, device_pk)
        assert len(alerts) == 1
        assert alerts[0].id == waiter_box["alert_id"]
        assert alerts[0].is_resolved is False


def test_uncommitted_alert_blocks_stale_update_until_commit():
    """An open alert insert locks the device row through its foreign key.

    The monitor's stale update waits for that lock. After the inserter
    commits, the monitor reuses the alert and commits the offline status.
    """

    with disposable_database("head") as lab:
        setup = lab.session()
        organization = _seed_organization(setup, "alert-blocks-update")
        device = _seed_stale_device(
            setup, organization, "pump-alert-blocks"
        )
        device_pk = device.id
        organization_id = organization.id
        seen_before = device.last_seen_at
        setup.close()

        inserter = lab.session()
        monitor = lab.session()
        referee = lab.referee()
        paused = threading.Event()
        release = threading.Event()
        workers = []
        try:
            def run_inserter(box):
                box["pid"] = _pid(inserter)
                alert = Alert(
                    device_id=device_pk,
                    organization_id=organization_id,
                    severity="critical",
                    alert_type="device_offline",
                    title="Device Offline",
                    message="Competing",
                    is_resolved=False,
                )
                inserter.add(alert)
                inserter.flush()
                box["alert_id"] = alert.id
                paused.set()
                if not release.wait(15):
                    raise TimeoutError(
                        "alert inserter was not released"
                    )
                inserter.commit()

            monitor_started = threading.Event()

            def run_monitor(box):
                box["pid"] = _pid(monitor)
                monitor_started.set()
                run_monitor_cycle(monitor, timeout_seconds=30)

            inserter_thread, inserter_box = _start(run_inserter)
            workers.append((inserter_thread, inserter_box))
            lab.track(inserter_thread, inserter_box, release)
            _wait_until(paused, "competing alert flush")
            monitor_thread, monitor_box = _start(run_monitor)
            workers.append((monitor_thread, monitor_box))
            lab.track(monitor_thread, monitor_box, release)
            _wait_until(monitor_started, "monitor pid")
            _wait_for_lock(
                referee,
                _require_pid(monitor_box),
                _require_pid(inserter_box),
                "transactionid",
            )
            release.set()
            _join_workers(workers, [release], lab)
            workers = []
            stored = _device_row(referee, device_pk)
            assert stored.status == "offline"
            assert stored.last_seen_at == seen_before
            alerts = _offline_alerts(referee, device_pk)
            assert len(alerts) == 1
            assert alerts[0].id == inserter_box["alert_id"]
            assert alerts[0].is_resolved is False
        finally:
            _join_workers(workers, [release], lab)


def test_savepoint_conflict_keeps_uncommitted_offline_status(
    monkeypatch,
):
    """The winning alert is already committed, and the first lookup misses.

    The monitor update and the losing insert then share one transaction.
    A simultaneous uncommitted insert cannot occupy that window: its
    foreign key takes a key-share lock that blocks the status update.
    """

    with disposable_database("head") as lab:
        setup = lab.session()
        organization = _seed_organization(setup, "savepoint-status")
        device = _seed_stale_device(
            setup, organization, "pump-savepoint"
        )
        device_pk = device.id
        organization_id = organization.id
        seen_before = device.last_seen_at
        winner = Alert(
            device_id=device_pk,
            organization_id=organization_id,
            severity="critical",
            alert_type="device_offline",
            title="Device Offline",
            message="Winner",
            is_resolved=False,
        )
        setup.add(winner)
        setup.commit()
        winner_id = winner.id
        setup.close()

        calls = {"count": 0}
        observed = {}

        def hide_first_lookup(**kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return None
            return get_active_device_alert(**kwargs)

        def observe_pending_status(**kwargs):
            db = kwargs["db"]
            observed["txid"] = _txid(db)
            result = create_alert(**kwargs)
            observed["txid_after"] = _txid(db)
            observed["nested"] = db.in_nested_transaction()
            observed["status"] = db.execute(
                text("SELECT status FROM devices WHERE id = :id"),
                {"id": device_pk},
            ).scalar()
            observed["created"] = result[1]
            observed["alert_id"] = result[0].id
            return result

        monkeypatch.setattr(
            "app.crud.alert.get_active_device_alert",
            hide_first_lookup,
        )
        monkeypatch.setattr(
            "app.services.device_monitor.create_alert",
            observe_pending_status,
        )

        monitor = lab.session()
        run_monitor_cycle(monitor, timeout_seconds=30)
        referee = lab.referee()
        assert calls["count"] == 2
        assert observed["created"] is False
        assert observed["alert_id"] == winner_id
        assert observed["txid_after"] == observed["txid"]
        assert observed["nested"] is False
        assert observed["status"] == "offline"
        stored = _device_row(referee, device_pk)
        assert stored.status == "offline"
        assert stored.last_seen_at == seen_before
        alerts = _offline_alerts(referee, device_pk)
        assert [(row.id, row.is_resolved) for row in alerts] == [
            (winner_id, False)
        ]


def test_failed_monitor_cycle_is_invisible_until_retry(monkeypatch):
    with disposable_database("head") as lab:
        setup = lab.session()
        organization = _seed_organization(setup, "monitor-rollback")
        device = _seed_stale_device(
            setup, organization, "pump-rollback"
        )
        device_pk = device.id
        organization_id = organization.id
        setup.close()
        referee = lab.referee()

        def fail_alert(**_kwargs):
            stored = _device_row(referee, device_pk)
            assert stored.status == "online"
            assert _offline_alerts(referee, device_pk) == []
            raise RuntimeError("monitor failed")

        monkeypatch.setattr(
            "app.services.device_monitor.create_alert",
            fail_alert,
        )
        monitor = lab.session()
        with pytest.raises(RuntimeError, match="monitor failed"):
            run_monitor_cycle(monitor, timeout_seconds=30)

        stored = _device_row(referee, device_pk)
        assert stored.status == "online"
        assert _offline_alerts(referee, device_pk) == []

        monkeypatch.undo()
        run_monitor_cycle(monitor, timeout_seconds=30)
        stored = _device_row(referee, device_pk)
        assert stored.status == "offline"
        alerts = _offline_alerts(referee, device_pk)
        assert len(alerts) == 1
        assert alerts[0].is_resolved is False
        organization_id_stored = referee.execute(
            text("SELECT organization_id FROM alerts WHERE id = :id"),
            {"id": alerts[0].id},
        ).scalar()
        assert organization_id_stored == organization_id


def _rows(connection):
    devices = connection.execute(
        text(
            "SELECT id, device_id, status, "
            "last_seen_at IS NULL AS missing_seen "
            "FROM devices ORDER BY id"
        )
    ).all()
    alerts = connection.execute(
        text(
            "SELECT id, device_id, alert_type, is_resolved "
            "FROM alerts ORDER BY id"
        )
    ).all()
    return devices, alerts


def _assert_monitor_constraints(lab):
    indexdef = _index_definition(lab.engine, lab.name)
    checkdef = _check_definition(lab.engine, lab.name)
    assert indexdef is not None
    assert "UNIQUE" in indexdef.upper()
    assert "device_offline" in indexdef
    assert "is_resolved" in indexdef
    assert checkdef is not None
    assert "last_seen_at IS NOT NULL" in checkdef
    assert "online" in checkdef


def test_postgres_migration_upgrades_and_downgrades():
    with disposable_database("head") as lab:
        assert _revision(lab.engine, lab.name) == HEAD_REVISION
        _assert_monitor_constraints(lab)
        db = lab.session()
        organization = _seed_organization(db, "migration-clean")
        organization_id = organization.id
        device = Device(
            device_id="kept-pump",
            name="Kept",
            device_type="sensor",
            status="offline",
            organization_id=organization.id,
            is_active=True,
        )
        db.add(device)
        db.commit()
        alert = Alert(
            device_id=device.id,
            organization_id=organization.id,
            severity="critical",
            alert_type="device_offline",
            title="Device Offline",
            message="Kept",
            is_resolved=False,
        )
        db.add(alert)
        db.commit()
        kept_device_id = device.id
        kept_alert_id = alert.id

        rejected_device = Device(
            device_id="missing-seen",
            name="Missing",
            device_type="sensor",
            status="online",
            organization_id=organization_id,
            is_active=True,
            last_seen_at=None,
        )
        db.add(rejected_device)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(
            Alert(
                device_id=kept_device_id,
                organization_id=organization_id,
                severity="critical",
                alert_type="device_offline",
                title="Duplicate",
                message="Duplicate",
                is_resolved=False,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

        referee = lab.referee()
        before_devices, before_alerts = _rows(referee)
        _downgrade(lab, PARENT_REVISION)
        after_devices, after_alerts = _rows(referee)
        assert list(after_devices) == list(before_devices)
        assert list(after_alerts) == list(before_alerts)
        _assert_constraints_absent(lab)

        follow = lab.session()
        follow.add(
            Device(
                device_id="missing-seen",
                name="Missing",
                device_type="sensor",
                status="online",
                organization_id=organization_id,
                is_active=True,
                last_seen_at=None,
            )
        )
        follow.add(
            Alert(
                device_id=kept_device_id,
                organization_id=organization_id,
                severity="critical",
                alert_type="device_offline",
                title="Duplicate",
                message="Duplicate",
                is_resolved=False,
            )
        )
        follow.commit()
        preserved = follow.get(Device, kept_device_id)
        preserved_alert = follow.get(Alert, kept_alert_id)
        assert preserved.device_id == "kept-pump"
        assert preserved.status == "offline"
        assert preserved_alert.is_resolved is False


def _refuse_upgrade(lab, message):
    if _revision(lab.engine, lab.name) != PARENT_REVISION:
        raise AssertionError("preflight revision was not the parent")
    _assert_constraints_absent(lab)
    referee = lab.referee()
    before = _rows(referee)
    with pytest.raises(Exception) as caught:
        with _migration_environment(lab.url, lab.name):
            command.upgrade(
                _alembic_config(lab.url, lab.name),
                "head",
            )
    assert message in _runtime_text(caught.value)
    with lab.engine.connect() as connection:
        _assert_identity(connection, lab.name)
    assert _revision(lab.engine, lab.name) == PARENT_REVISION
    _assert_constraints_absent(lab)
    assert _rows(referee) == before


def test_postgres_migration_refuses_duplicate_alerts():
    with disposable_database(PARENT_REVISION) as lab:
        db = lab.session()
        organization = _seed_organization(db, "duplicate-alerts")
        device = Device(
            device_id="duplicate-pump",
            name="Duplicate",
            device_type="sensor",
            status="offline",
            organization_id=organization.id,
            is_active=True,
        )
        db.add(device)
        db.commit()
        for number in (1, 2):
            db.add(
                Alert(
                    device_id=device.id,
                    organization_id=organization.id,
                    severity="critical",
                    alert_type="device_offline",
                    title=f"Copy {number}",
                    message="Unresolved",
                    is_resolved=False,
                )
            )
        db.commit()
        db.close()
        _refuse_upgrade(lab, "not deleted or merged")


def test_postgres_migration_refuses_online_device_without_last_seen():
    with disposable_database(PARENT_REVISION) as lab:
        db = lab.session()
        organization = _seed_organization(db, "missing-seen")
        device = Device(
            device_id="untouched-pump",
            name="Untouched",
            device_type="sensor",
            status="online",
            organization_id=organization.id,
            is_active=True,
            last_seen_at=None,
        )
        db.add(device)
        db.commit()
        db.add(
            Alert(
                device_id=device.id,
                organization_id=organization.id,
                severity="critical",
                alert_type="device_offline",
                title="Device Offline",
                message="Single",
                is_resolved=False,
            )
        )
        db.commit()
        db.close()
        _refuse_upgrade(lab, "Rows were not changed")


def _disposable_database_names():
    engine = create_engine(
        _URL,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        with engine.connect() as connection:
            current = connection.execute(
                text("SELECT current_database()")
            ).scalar()
            if (
                current in FORBIDDEN_DATABASES
                or DISPOSABLE_NAME.fullmatch(current or "")
            ):
                raise RuntimeError(
                    f"refusing to list databases from {current!r}"
                )
            rows = connection.execute(
                text(
                    "SELECT datname FROM pg_database "
                    "WHERE datname ~ '^skape_test_[0-9a-f]{16}$' "
                    "ORDER BY datname"
                )
            ).scalars()
            return tuple(rows)
    finally:
        engine.dispose()


def test_drop_error_keeps_the_body_exception_and_drops_the_database(
    monkeypatch,
):
    original_drop = _drop_database

    def fail_drop(admin_engine, name):
        original_drop(admin_engine, name)
        raise RuntimeError("drop failed")

    monkeypatch.setattr(
        sys.modules[__name__],
        "_drop_database",
        fail_drop,
    )
    before = _disposable_database_names()
    with pytest.raises(RuntimeError, match="body failed") as caught:
        with disposable_database(None):
            raise RuntimeError("body failed")
    notes = getattr(caught.value, "__notes__", [])
    assert any("drop failed" in note for note in notes)
    assert _disposable_database_names() == before


def test_drop_error_fails_the_test_when_the_body_passes(monkeypatch):
    original_drop = _drop_database

    def fail_drop(admin_engine, name):
        original_drop(admin_engine, name)
        raise RuntimeError("drop failed")

    monkeypatch.setattr(
        sys.modules[__name__],
        "_drop_database",
        fail_drop,
    )
    before = _disposable_database_names()
    with pytest.raises(RuntimeError, match="drop failed"):
        with disposable_database(None):
            pass
    assert _disposable_database_names() == before


def test_body_failure_joins_workers_without_replacing_the_error():
    release = threading.Event()
    started = threading.Event()
    holder = {}

    def run(box):
        started.set()
        if not release.wait(15):
            raise TimeoutError("worker was not released")
        box["finished"] = True

    before = _disposable_database_names()
    with pytest.raises(RuntimeError, match="body failed") as caught:
        with disposable_database(None) as lab:
            thread, box = _start(run)
            lab.track(thread, box, release)
            holder["thread"] = thread
            holder["box"] = box
            if not started.wait(15):
                raise AssertionError("worker did not start")
            raise RuntimeError("body failed")
    assert holder["box"].get("finished") is True
    assert holder["thread"].is_alive() is False
    notes = " ".join(getattr(caught.value, "__notes__", []))
    assert "still running" not in notes
    assert _disposable_database_names() == before


def _device_status(connection, device_pk):
    return connection.execute(
        text("SELECT status FROM devices WHERE id = :device_id"),
        {"device_id": device_pk},
    ).scalar()


def _unresolved_offline_alerts(connection, device_pk):
    return connection.execute(
        text(
            "SELECT count(*) FROM alerts "
            "WHERE device_id = :device_id "
            "AND alert_type = 'device_offline' "
            "AND NOT is_resolved"
        ),
        {"device_id": device_pk},
    ).scalar()


def test_competing_monitor_cycles_do_not_duplicate_offline_alerts():
    """A second cycle skips while the advisory lock is held."""

    with disposable_database("head") as lab:
        holder = lab.session()
        organization = _seed_organization(holder, "single-flight")
        device = _seed_stale_device(
            holder,
            organization,
            "pump-single-flight",
        )
        device_pk = device.id
        acquired = holder.execute(
            text(
                "SELECT pg_try_advisory_lock("
                "CAST(:lock_key AS bigint))"
            ),
            {"lock_key": MONITOR_ADVISORY_LOCK_KEY},
        ).scalar()
        assert acquired is True

        rival = lab.session()
        referee = lab.referee()
        release = threading.Event()

        def compete(_box):
            run_monitor_cycle(rival)

        thread, box = _start(compete)
        lab.track(thread, box, release)
        thread.join(15)
        if thread.is_alive():
            raise AssertionError(
                "competing monitor cycle did not finish"
            )
        if box.get("error") is not None:
            raise box["error"]

        assert _device_status(referee, device_pk) == "online"
        assert _unresolved_offline_alerts(referee, device_pk) == 0


def test_monitor_cycle_proceeds_after_the_advisory_lock_is_released():
    """The next cycle performs the offline work once the lock is free."""

    with disposable_database("head") as lab:
        holder = lab.session()
        organization = _seed_organization(holder, "lock-release")
        device = _seed_stale_device(
            holder,
            organization,
            "pump-lock-release",
        )
        device_pk = device.id
        acquired = holder.execute(
            text(
                "SELECT pg_try_advisory_lock("
                "CAST(:lock_key AS bigint))"
            ),
            {"lock_key": MONITOR_ADVISORY_LOCK_KEY},
        ).scalar()
        assert acquired is True
        rival = lab.session()
        run_monitor_cycle(rival)
        referee = lab.referee()
        assert _device_status(referee, device_pk) == "online"
        assert _unresolved_offline_alerts(referee, device_pk) == 0

        released = holder.execute(
            text(
                "SELECT pg_advisory_unlock("
                "CAST(:lock_key AS bigint))"
            ),
            {"lock_key": MONITOR_ADVISORY_LOCK_KEY},
        ).scalar()
        assert released is True

        run_monitor_cycle(rival)
        assert _device_status(referee, device_pk) == "offline"
        assert _unresolved_offline_alerts(referee, device_pk) == 1

        run_monitor_cycle(lab.session())
        assert _unresolved_offline_alerts(referee, device_pk) == 1
