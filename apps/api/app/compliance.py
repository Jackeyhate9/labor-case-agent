from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from .app_paths import app_data_root
from .services import ServiceError


VERSIONS = {
    "terms": "2026-07-29-v1",
    "privacy": "2026-07-29-v1",
    "ai_notice": "2026-07-29-v1",
}
_LOCK = RLock()


def consent_path() -> Path:
    path = Path(
        os.getenv(
            "COMPLIANCE_CONSENT_FILE",
            app_data_root() / "compliance-consent.json",
        )
    ).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_record() -> dict[str, Any] | None:
    path = consent_path()
    with _LOCK:
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ServiceError(
                "COMPLIANCE_RECORD_INVALID",
                "The local policy acceptance record is invalid",
                500,
            ) from exc
    return value if isinstance(value, dict) else None


def is_current_acceptance() -> bool:
    record = _load_record()
    return bool(
        record
        and record.get("accepted") is True
        and record.get("versions") == VERSIONS
        and record.get("accept_terms") is True
        and record.get("accept_sensitive_data_processing") is True
        and record.get("accept_ai_notice") is True
    )


def public_compliance_status() -> dict[str, Any]:
    publisher_name = os.getenv("PUBLISHER_NAME", "").strip()
    support_email = os.getenv("SUPPORT_EMAIL", "").strip()
    required = os.getenv("REQUIRE_COMPLIANCE_ACCEPTANCE", "0") == "1"
    record = _load_record()
    return {
        "acceptance_required": required and not is_current_acceptance(),
        "accepted": is_current_acceptance(),
        "accepted_at": record.get("accepted_at") if record else None,
        "versions": VERSIONS,
        "publisher": {
            "name": publisher_name or "发行主体待配置",
            "support_email": support_email or "客服邮箱待配置",
            "configured": bool(publisher_name and support_email),
        },
        "documents": [
            {"id": "terms", "title": "用户服务协议", "href": "/legal/terms"},
            {"id": "privacy", "title": "隐私政策", "href": "/legal/privacy"},
            {"id": "ai-notice", "title": "AI 与自动化处理说明", "href": "/legal/ai-notice"},
        ],
        "data_rights": {
            "backup": True,
            "restore": True,
            "delete_all": True,
            "withdraw_consent": True,
        },
    }


def accept_current_policies(value: dict[str, Any]) -> dict[str, Any]:
    supplied_versions = {
        "terms": value.get("terms_version"),
        "privacy": value.get("privacy_version"),
        "ai_notice": value.get("ai_notice_version"),
    }
    if supplied_versions != VERSIONS:
        raise ServiceError(
            "POLICY_VERSION_CHANGED",
            "The policy version changed; review the current documents before accepting",
            409,
        )
    acknowledgements = (
        "accept_terms",
        "accept_sensitive_data_processing",
        "accept_ai_notice",
    )
    if not all(value.get(name) is True for name in acknowledgements):
        raise ServiceError(
            "POLICY_ACCEPTANCE_INCOMPLETE",
            "All required acknowledgements must be selected",
            422,
        )
    record = {
        "accepted": True,
        "accepted_at": datetime.now(UTC).isoformat(),
        "versions": VERSIONS,
        **{name: True for name in acknowledgements},
        "edition": os.getenv("APP_EDITION", "distribution"),
    }
    path = consent_path()
    temporary = path.with_suffix(path.suffix + ".tmp")
    with _LOCK:
        temporary.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    return public_compliance_status()


def withdraw_policy_acceptance() -> dict[str, Any]:
    with _LOCK:
        consent_path().unlink(missing_ok=True)
    return public_compliance_status()
