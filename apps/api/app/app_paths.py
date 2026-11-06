from __future__ import annotations

import os
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def application_home() -> Path:
    configured = os.getenv("LABOR_CASE_AGENT_HOME", "").strip()
    if configured:
        return Path(configured).resolve()
    data_root = os.getenv("APP_DATA_ROOT", "").strip()
    if data_root:
        return Path(data_root).resolve().parent
    return PACKAGE_ROOT


def app_data_root() -> Path:
    configured = os.getenv("APP_DATA_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()
    return (application_home() / "data").resolve()


def public_storage_contract() -> dict[str, Any]:
    if os.getenv("APP_DATA_ROOT", "").strip():
        source = "app_data_root"
    elif os.getenv("LABOR_CASE_AGENT_HOME", "").strip():
        source = "application_home"
    else:
        source = "package_default"
    return {
        "home": str(application_home()),
        "data_root": str(app_data_root()),
        "source": source,
    }
