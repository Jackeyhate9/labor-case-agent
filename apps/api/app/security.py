from __future__ import annotations

import logging
import re
from pathlib import Path


DANGEROUS_EXTENSIONS = {
    ".ade", ".adp", ".app", ".bat", ".cmd", ".com", ".cpl", ".dll",
    ".exe", ".hta", ".ins", ".isp", ".jar", ".js", ".jse", ".lnk",
    ".msc", ".msi", ".msp", ".mst", ".pif", ".ps1", ".reg", ".scr",
    ".sct", ".shb", ".sys", ".vb", ".vbe", ".vbs", ".ws", ".wsc",
    ".wsf", ".wsh",
}
IDENTITY_RE = re.compile(r"(?<!\d)(\d{6})\d{8}([0-9Xx]{4})(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")


def validate_safe_extension(filename: str) -> None:
    suffixes = {suffix.lower() for suffix in Path(filename).suffixes}
    dangerous = sorted(suffixes & DANGEROUS_EXTENSIONS)
    if dangerous:
        from .services import ServiceError

        raise ServiceError("DANGEROUS_FILE_EXTENSION", f"Executable/script extension is not accepted: {dangerous[-1]}")


def validate_no_executable_disguise(content: bytes) -> None:
    executable_magic = content.startswith(b"MZ") or content.startswith(b"\x7fELF")
    if executable_magic:
        from .services import ServiceError

        raise ServiceError("FILE_CONTENT_MISMATCH", "Executable content cannot be uploaded as evidence")


def redact_sensitive(value: str) -> tuple[str, bool]:
    redacted = IDENTITY_RE.sub(r"\1********\2", value)
    redacted = PHONE_RE.sub(r"\1****\2", redacted)
    return redacted, redacted != value


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Preserve structured logging arguments (Uvicorn's access formatter
        # requires a five-item tuple). Redact string fields in place instead of
        # flattening the formatted message and discarding its schema.
        if isinstance(record.msg, str):
            record.msg = redact_sensitive(record.msg)[0]
        if isinstance(record.args, tuple):
            record.args = tuple(redact_sensitive(item)[0] if isinstance(item, str) else item for item in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                key: redact_sensitive(item)[0] if isinstance(item, str) else item
                for key, item in record.args.items()
            }
        return True


def install_log_filters() -> None:
    for logger_name in ("labor_case_agent", "uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(logger_name)
        if not any(isinstance(item, SensitiveDataFilter) for item in logger.filters):
            logger.addFilter(SensitiveDataFilter())
