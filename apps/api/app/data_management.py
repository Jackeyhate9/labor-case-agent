from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import delete

from .app_paths import application_home
from .database import Base, SessionLocal, engine
from .llm_config import config_path as llm_config_path
from .llm_config import secret_path as llm_secret_path
from .services import STORAGE_ROOT, ServiceError
from .settings import settings_path


MAGIC = b"LCA1"
PBKDF2_ITERATIONS = 600_000
BACKUP_FORMAT = 1


def backup_root() -> Path:
    root = Path(os.getenv("BACKUP_ROOT", application_home() / "backups")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _database_path() -> Path:
    if engine.url.get_backend_name() != "sqlite" or not engine.url.database:
        raise ServiceError("BACKUP_UNSUPPORTED", "V1 backup currently supports SQLite only", 409)
    return Path(engine.url.database).resolve()


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < 12:
        raise ServiceError(
            "BACKUP_PASSPHRASE_WEAK",
            "Backup passphrase must contain at least 12 characters",
            422,
        )
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    ).derive(passphrase.encode("utf-8"))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sqlite_snapshot(destination: Path) -> None:
    source = sqlite3.connect(_database_path())
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()


def _zip_payload() -> bytes:
    entries: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="labor-case-backup-") as temporary:
        snapshot = Path(temporary) / "database.sqlite3"
        _sqlite_snapshot(snapshot)
        entries["database.sqlite3"] = snapshot.read_bytes()

    for name, path in (
        ("settings/system-settings.json", settings_path()),
        ("settings/llm-config.json", llm_config_path()),
    ):
        if path.is_file():
            entries[name] = path.read_bytes()

    if STORAGE_ROOT.is_dir():
        for path in sorted(STORAGE_ROOT.rglob("*")):
            if path.is_file():
                relative = path.relative_to(STORAGE_ROOT).as_posix()
                entries[f"cases/{relative}"] = path.read_bytes()

    manifest = {
        "format": BACKUP_FORMAT,
        "created_at": datetime.now(UTC).isoformat(),
        "app_version": os.getenv("APP_VERSION", "0.2.0"),
        "api_keys_included": False,
        "files": [
            {"path": path, "size": len(value), "sha256": _sha256(value)}
            for path, value in sorted(entries.items())
        ],
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, value in entries.items():
            archive.writestr(path, value)
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    return stream.getvalue()


def create_encrypted_backup(passphrase: str) -> dict[str, Any]:
    payload = _zip_payload()
    salt = os.urandom(16)
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_key(passphrase, salt)).encrypt(nonce, payload, MAGIC)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = backup_root() / f"labor-case-backup-{timestamp}-{uuid.uuid4().hex[:8]}.lca-backup"
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(MAGIC + salt + nonce + ciphertext)
    temporary.replace(output)
    return {
        "filename": output.name,
        "path": str(output),
        "size": output.stat().st_size,
        "encrypted": True,
        "api_keys_included": False,
    }


def resolve_backup(filename: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise ServiceError("BACKUP_NOT_FOUND", "Backup file not found", 404)
    path = (backup_root() / filename).resolve()
    if path.parent != backup_root() or not path.is_file():
        raise ServiceError("BACKUP_NOT_FOUND", "Backup file not found", 404)
    return path


def _decrypt_backup(value: bytes, passphrase: str) -> bytes:
    if len(value) < 48 or value[:4] != MAGIC:
        raise ServiceError("BACKUP_INVALID", "The selected file is not a Labor Case Agent backup", 422)
    salt, nonce, ciphertext = value[4:20], value[20:32], value[32:]
    try:
        return AESGCM(_derive_key(passphrase, salt)).decrypt(nonce, ciphertext, MAGIC)
    except Exception as exc:
        raise ServiceError(
            "BACKUP_DECRYPTION_FAILED",
            "The backup passphrase is incorrect or the backup is damaged",
            422,
        ) from exc


def _validated_entries(payload: bytes) -> tuple[dict[str, bytes], dict[str, Any]]:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries: dict[str, bytes] = {}
            for info in archive.infolist():
                path = Path(info.filename)
                if path.is_absolute() or ".." in path.parts or info.is_dir():
                    if info.is_dir():
                        continue
                    raise ServiceError("BACKUP_INVALID", "Backup contains an unsafe path", 422)
                entries[info.filename] = archive.read(info)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ServiceError("BACKUP_INVALID", "Backup archive is damaged", 422) from exc
    try:
        manifest = json.loads(entries.pop("manifest.json").decode("utf-8"))
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise ServiceError("BACKUP_INVALID", "Backup manifest is missing or invalid", 422) from exc
    if manifest.get("format") != BACKUP_FORMAT:
        raise ServiceError("BACKUP_VERSION_UNSUPPORTED", "Backup format is not supported", 409)
    expected = {item["path"]: item for item in manifest.get("files", [])}
    if set(entries) != set(expected):
        raise ServiceError("BACKUP_INVALID", "Backup file list does not match its manifest", 422)
    for path, value in entries.items():
        if len(value) != expected[path]["size"] or _sha256(value) != expected[path]["sha256"]:
            raise ServiceError("BACKUP_INVALID", f"Backup integrity check failed: {path}", 422)
    return entries, manifest


def _validate_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA quick_check").fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        connection.close()
    required = {"cases", "evidence", "facts"}
    if not result or result[0] != "ok" or not required.issubset(tables):
        raise ServiceError("BACKUP_INVALID", "Backup database failed validation", 422)


def restore_encrypted_backup(value: bytes, passphrase: str, confirmation: str) -> dict[str, Any]:
    if confirmation != "RESTORE":
        raise ServiceError("RESTORE_CONFIRMATION_REQUIRED", "Type RESTORE to confirm", 422)
    entries, manifest = _validated_entries(_decrypt_backup(value, passphrase))
    database = entries["database.sqlite3"]
    with tempfile.TemporaryDirectory(prefix="labor-case-restore-") as temporary:
        stage = Path(temporary)
        database_path = stage / "database.sqlite3"
        database_rollback = stage / "database.rollback.sqlite3"
        database_path.write_bytes(database)
        _validate_database(database_path)
        _sqlite_snapshot(database_rollback)
        cases_stage = stage / "cases"
        cases_stage.mkdir(parents=True, exist_ok=True)
        for name, content in entries.items():
            if name.startswith("cases/"):
                target = cases_stage / name.removeprefix("cases/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)

        rollback = STORAGE_ROOT.with_name(f"{STORAGE_ROOT.name}.restore-rollback")
        if rollback.exists():
            shutil.rmtree(rollback)
        settings_targets = (
            ("settings/system-settings.json", settings_path()),
            ("settings/llm-config.json", llm_config_path()),
        )
        previous_settings = {
            target: target.read_bytes() if target.is_file() else None
            for _, target in settings_targets
        }
        try:
            engine.dispose()
            source = sqlite3.connect(database_path)
            destination = sqlite3.connect(_database_path())
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()

            if STORAGE_ROOT.exists():
                STORAGE_ROOT.replace(rollback)
            shutil.copytree(cases_stage, STORAGE_ROOT)

            for archive_name, target in settings_targets:
                if archive_name in entries:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary_target = target.with_suffix(target.suffix + ".restore")
                    temporary_target.write_bytes(entries[archive_name])
                    temporary_target.replace(target)
        except Exception:
            engine.dispose()
            source = sqlite3.connect(database_rollback)
            destination = sqlite3.connect(_database_path())
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
            if STORAGE_ROOT.exists():
                shutil.rmtree(STORAGE_ROOT)
            if rollback.exists():
                rollback.replace(STORAGE_ROOT)
            for target, content in previous_settings.items():
                if content is None:
                    target.unlink(missing_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
            raise
        else:
            if rollback.exists():
                shutil.rmtree(rollback)

    return {
        "restored": True,
        "created_at": manifest["created_at"],
        "api_key_reentry_required": True,
    }


def clear_all_case_data(confirmation: str) -> dict[str, Any]:
    if confirmation != "DELETE ALL CASES":
        raise ServiceError(
            "DELETE_CONFIRMATION_REQUIRED",
            "Type DELETE ALL CASES to confirm",
            422,
        )
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
        session.commit()
    removed_files = 0
    if STORAGE_ROOT.exists():
        removed_files = sum(1 for path in STORAGE_ROOT.rglob("*") if path.is_file())
        shutil.rmtree(STORAGE_ROOT)
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    return {"cleared": True, "removed_files": removed_files}


def data_management_status() -> dict[str, Any]:
    database = _database_path()
    backups = sorted(backup_root().glob("*.lca-backup"), reverse=True)
    return {
        "database_path": str(database),
        "storage_root": str(STORAGE_ROOT),
        "backup_root": str(backup_root()),
        "database_size": database.stat().st_size if database.is_file() else 0,
        "backup_count": len(backups),
        "latest_backup": backups[0].name if backups else None,
        "backup_encryption": "AES-256-GCM / PBKDF2-SHA256",
    }
