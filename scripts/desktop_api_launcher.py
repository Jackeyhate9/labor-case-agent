"""Frozen entry point for the loopback-only FastAPI desktop sidecar."""

from __future__ import annotations

import logging
import multiprocessing
import os
import sqlite3
import sys
import traceback
from datetime import datetime
from pathlib import Path


API_HOST = "127.0.0.1"
API_PORT = int(os.environ.get("API_PORT", "17831"))


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[1]


def _local_root() -> Path:
    configured = os.environ.get("LABOR_CASE_AGENT_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "LaborCaseAgent"


def configure_environment() -> tuple[Path, Path]:
    local_root = _local_root()
    data_dir = local_root / "data"
    storage_dir = data_dir / "cases"
    model_dir = local_root / "models"
    log_dir = local_root / "logs"
    for path in (data_dir, storage_dir, model_dir, log_dir):
        path.mkdir(parents=True, exist_ok=True)

    database_path = (data_dir / "labor_case_agent.db").resolve().as_posix()
    os.environ.setdefault("APP_ENV", "desktop")
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{database_path}")
    os.environ.setdefault("STORAGE_ROOT", str(storage_dir.resolve()))
    os.environ.setdefault("MODEL_ROOT", str(model_dir.resolve()))
    os.environ.setdefault("SYSTEM_SETTINGS_FILE", str((data_dir / "system-settings.json").resolve()))
    os.environ.setdefault("CORS_ORIGINS", "http://tauri.localhost,tauri://localhost,http://127.0.0.1:3000")
    os.environ.setdefault("LLM_PROVIDER", "disabled")
    os.environ.setdefault("EMBEDDING_PROVIDER", "disabled")
    os.environ.setdefault("REQUIRE_COMPLIANCE_ACCEPTANCE", "1")

    unlimited_ocr = model_dir / "Unlimited-OCR"
    if unlimited_ocr.is_dir():
        os.environ.setdefault("UNLIMITED_OCR_MODEL_PATH", str(unlimited_ocr.resolve()))

    logging.basicConfig(
        filename=log_dir / "api.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return data_dir, model_dir


def create_pre_migration_backup(database_path: Path, data_dir: Path) -> Path:
    recovery_dir = data_dir / "pre-migration"
    recovery_dir.mkdir(parents=True, exist_ok=True)
    destination = recovery_dir / (
        f"labor-case-before-migration-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite3"
    )
    source = sqlite3.connect(database_path)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    for stale in sorted(
        recovery_dir.glob("labor-case-before-migration-*.sqlite3"),
        reverse=True,
    )[3:]:
        stale.unlink(missing_ok=True)
    return destination


def upgrade_database(bundle_root: Path) -> None:
    """Upgrade both Alembic-managed v0.1 DBs and early desktop preview DBs."""
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect

    alembic_ini = bundle_root / "apps" / "api" / "alembic.ini"
    migrations = bundle_root / "apps" / "api" / "alembic"
    alembic_config = AlembicConfig(str(alembic_ini))
    alembic_config.set_main_option("script_location", str(migrations))

    database_path = Path(os.environ["DATABASE_URL"].removeprefix("sqlite:///"))
    probe = create_engine(os.environ["DATABASE_URL"])
    try:
        tables = set(inspect(probe).get_table_names())
        with probe.connect() as connection:
            current_revision = MigrationContext.configure(connection).get_current_revision()
    finally:
        probe.dispose()
    head_revision = ScriptDirectory.from_config(alembic_config).get_current_head()
    if tables and current_revision != head_revision:
        create_pre_migration_backup(database_path, database_path.parent)
    if tables and "alembic_version" not in tables:
        # Some v0.1 preview/desktop builds created the documented base schema
        # with SQLAlchemy create_all and therefore lack only Alembic's stamp.
        # Refuse unknown databases instead of guessing or deleting user data.
        required_v01_tables = {"cases", "evidence", "facts"}
        if not required_v01_tables.issubset(tables):
            raise RuntimeError("Existing database is not a recognized Labor Case Agent v0.1 schema")
        alembic_command.stamp(alembic_config, "0001_initial")
    alembic_command.upgrade(alembic_config, "head")


def main() -> None:
    multiprocessing.freeze_support()
    configure_environment()
    bundle_root = _bundle_root()
    source_api = bundle_root / "apps" / "api"
    if source_api.is_dir():
        sys.path.insert(0, str(source_api))

    # Upgrade an existing desktop database before importing the ASGI app.
    # SQLAlchemy create_all only creates missing tables and cannot add v0.2
    # columns to a database created by v0.1.
    upgrade_database(bundle_root)

    import uvicorn
    from app import main as api_main

    # The API self-check derives the repository root from this module path.
    # A frozen build includes read-only knowledge/samples beneath _MEIPASS.
    if getattr(sys, "frozen", False):
        api_main.__file__ = str(bundle_root / "apps" / "api" / "app" / "main.py")

    uvicorn.run(
        api_main.app,
        host=API_HOST,
        port=API_PORT,
        access_log=False,
        log_level="warning",
        # The Windows `--noconsole` PyInstaller bootloader sets stderr to
        # None; Uvicorn's default color formatter calls stderr.isatty().
        log_config=None,
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        details = traceback.format_exc()
        try:
            failure_log = _local_root() / "logs" / "startup-error.log"
            failure_log.parent.mkdir(parents=True, exist_ok=True)
            failure_log.write_text(details, encoding="utf-8")
        except OSError:
            pass
        logging.exception("Desktop API bootstrap failed")
        raise
