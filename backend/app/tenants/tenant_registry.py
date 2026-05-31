from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.tenants.tenant_configs import DEMO_TENANTS, TenantConfig, upsert_tenant

_TENANT_DB_PATH = os.getenv("TENANT_DB_PATH", os.path.join("data", "tenants.db"))
_lock = threading.Lock()


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def init_tenant_registry_db() -> None:
    _ensure_parent_dir(_TENANT_DB_PATH)

    with _lock:
        conn = sqlite3.connect(_TENANT_DB_PATH)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    jira_project_key TEXT NOT NULL,
                    jira_issue_type TEXT NOT NULL,
                    default_labels_json TEXT NOT NULL,
                    component TEXT,
                    label_map_json TEXT NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()


def _config_to_row(config: TenantConfig) -> Tuple[Any, ...]:
    return (
        config.tenant_id,
        config.display_name,
        config.jira_project_key,
        config.jira_issue_type,
        json.dumps(list(config.default_labels or ()), ensure_ascii=False),
        config.component,
        json.dumps(
            {k: list(v or ()) for k, v in (config.label_map or {}).items()},
            ensure_ascii=False,
        ),
    )


def _row_to_config(row: sqlite3.Row) -> Optional[TenantConfig]:
    try:
        default_labels_raw = json.loads(row["default_labels_json"] or "[]")
        label_map_raw = json.loads(row["label_map_json"] or "{}")

        default_labels = tuple(str(x).strip() for x in default_labels_raw if str(x).strip())

        label_map: Dict[str, Tuple[str, ...]] = {}
        if isinstance(label_map_raw, dict):
            for key, labels in label_map_raw.items():
                k = str(key).strip().lower()
                if not k:
                    continue
                if isinstance(labels, list):
                    label_map[k] = tuple(str(x).strip() for x in labels if str(x).strip())

        return TenantConfig(
            tenant_id=str(row["tenant_id"]).strip(),
            display_name=str(row["display_name"]).strip(),
            jira_project_key=str(row["jira_project_key"]).strip(),
            jira_issue_type=str(row["jira_issue_type"]).strip(),
            default_labels=default_labels,
            component=str(row["component"]).strip() if row["component"] else None,
            label_map=label_map,
        )
    except Exception:
        return None


def save_tenant_to_registry(config: TenantConfig) -> TenantConfig:
    init_tenant_registry_db()

    with _lock:
        conn = sqlite3.connect(_TENANT_DB_PATH)
        try:
            conn.execute(
                """
                INSERT INTO tenants(
                    tenant_id,
                    display_name,
                    jira_project_key,
                    jira_issue_type,
                    default_labels_json,
                    component,
                    label_map_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    jira_project_key = excluded.jira_project_key,
                    jira_issue_type = excluded.jira_issue_type,
                    default_labels_json = excluded.default_labels_json,
                    component = excluded.component,
                    label_map_json = excluded.label_map_json;
                """,
                _config_to_row(config),
            )
            conn.commit()
        finally:
            conn.close()

    upsert_tenant(config)
    return config


def seed_missing_demo_tenants() -> int:
    init_tenant_registry_db()

    seeded = 0
    with _lock:
        conn = sqlite3.connect(_TENANT_DB_PATH)
        try:
            for config in DEMO_TENANTS:
                exists = conn.execute(
                    "SELECT 1 FROM tenants WHERE tenant_id = ? LIMIT 1;",
                    (config.tenant_id,),
                ).fetchone()
                if exists:
                    continue

                conn.execute(
                    """
                    INSERT INTO tenants(
                        tenant_id,
                        display_name,
                        jira_project_key,
                        jira_issue_type,
                        default_labels_json,
                        component,
                        label_map_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    _config_to_row(config),
                )
                seeded += 1

            conn.commit()
        finally:
            conn.close()

    return seeded


def load_tenants_from_registry() -> List[TenantConfig]:
    init_tenant_registry_db()

    with _lock:
        conn = sqlite3.connect(_TENANT_DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT
                    tenant_id,
                    display_name,
                    jira_project_key,
                    jira_issue_type,
                    default_labels_json,
                    component,
                    label_map_json
                FROM tenants
                ORDER BY tenant_id ASC;
                """
            ).fetchall()
        finally:
            conn.close()

    configs: List[TenantConfig] = []
    for row in rows:
        config = _row_to_config(row)
        if config:
            upsert_tenant(config)
            configs.append(config)

    return configs


def bootstrap_tenant_registry() -> int:
    seed_missing_demo_tenants()
    loaded = load_tenants_from_registry()
    return len(loaded)
