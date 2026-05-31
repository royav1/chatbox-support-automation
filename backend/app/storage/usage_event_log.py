from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


@dataclass(frozen=True)
class UsageEvent:
    ts: str
    tenant_id: str
    event_type: str
    message_id: str
    source: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    meta: Optional[Dict[str, Any]] = None


class UsageEventLog:
    """
    SQLite-backed append-only usage event log (billing/audit trail).
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()

    def init_db(self) -> None:
        _ensure_parent_dir(self.db_path)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS usage_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT NOT NULL,
                        tenant_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        message_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        intent TEXT,
                        confidence REAL,
                        meta_json TEXT
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_usage_events_tenant_ts ON usage_events(tenant_id, ts);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_usage_events_message ON usage_events(message_id);"
                )
                conn.commit()
            finally:
                conn.close()

    def append(self, event: UsageEvent) -> None:
        # lazy init safety
        self.init_db()

        meta_json = None
        if event.meta is not None:
            try:
                meta_json = json.dumps(event.meta, ensure_ascii=False)
            except Exception:
                meta_json = None

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO usage_events(ts, tenant_id, event_type, message_id, source, intent, confidence, meta_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.ts,
                        event.tenant_id,
                        event.event_type,
                        event.message_id,
                        event.source,
                        event.intent,
                        event.confidence,
                        meta_json,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def list_events(
        self,
        *,
        tenant_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        self.init_db()

        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                if tenant_id:
                    rows = conn.execute(
                        """
                        SELECT ts, tenant_id, event_type, message_id, source, intent, confidence, meta_json
                        FROM usage_events
                        WHERE tenant_id = ?
                        ORDER BY id DESC
                        LIMIT ? OFFSET ?
                        """,
                        (tenant_id, limit, offset),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT ts, tenant_id, event_type, message_id, source, intent, confidence, meta_json
                        FROM usage_events
                        ORDER BY id DESC
                        LIMIT ? OFFSET ?
                        """,
                        (limit, offset),
                    ).fetchall()

                out: List[Dict[str, Any]] = []
                for r in rows:
                    meta = None
                    raw_meta = r["meta_json"]
                    if raw_meta:
                        try:
                            meta = json.loads(raw_meta)
                        except Exception:
                            meta = None

                    out.append(
                        {
                            "ts": r["ts"],
                            "tenant_id": r["tenant_id"],
                            "event_type": r["event_type"],
                            "message_id": r["message_id"],
                            "source": r["source"],
                            "intent": r["intent"],
                            "confidence": r["confidence"],
                            "meta": meta,
                        }
                    )
                return out
            finally:
                conn.close()

    def summary(
        self,
        *,
        tenant_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.init_db()

        tid = (tenant_id or "").strip() or None
        et = (event_type or "").strip() or None

        where: List[str] = []
        params: List[Any] = []

        if tid:
            where.append("tenant_id = ?")
            params.append(tid)
        if et:
            where.append("event_type = ?")
            params.append(et)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        query_total = f"SELECT COUNT(*) as cnt FROM usage_events {where_sql};"
        query_breakdown = f"""
            SELECT event_type, COUNT(*) as cnt
            FROM usage_events
            {where_sql}
            GROUP BY event_type
            ORDER BY cnt DESC;
        """
        intent_where = where.copy()
        intent_params = params.copy()
        intent_where.append("event_type = ?")
        intent_params.append("email_ingested")
        intent_where.append("intent IS NOT NULL")
        intent_where.append("TRIM(intent) != ''")
        intent_where_sql = "WHERE " + " AND ".join(intent_where)

        query_intent_breakdown = f"""
            SELECT intent, COUNT(*) as cnt
            FROM usage_events
            {intent_where_sql}
            GROUP BY intent
            ORDER BY cnt DESC;
        """

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                total_row = conn.execute(query_total, tuple(params)).fetchone()
                total = int(total_row["cnt"]) if total_row else 0

                rows = conn.execute(query_breakdown, tuple(params)).fetchall()
                breakdown: Dict[str, int] = {}
                for r in rows:
                    try:
                        breakdown[str(r["event_type"])] = int(r["cnt"])
                    except Exception:
                        continue

                intent_rows = conn.execute(
                    query_intent_breakdown,
                    tuple(intent_params),
                ).fetchall()
                intent_breakdown: Dict[str, int] = {}
                for r in intent_rows:
                    try:
                        intent_breakdown[str(r["intent"])] = int(r["cnt"])
                    except Exception:
                        continue

                return {
                    "tenant_id": tid,
                    "event_type_filter": et,
                    "total": total,
                    "by_event_type": breakdown,
                    "by_intent": intent_breakdown,
                }
            finally:
                conn.close()


# ---------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------

_USAGE_DB_PATH = os.getenv("USAGE_DB_PATH", os.path.join("data", "usage_events.db"))
_usage_log = UsageEventLog(db_path=_USAGE_DB_PATH)


def init_usage_db() -> None:
    _usage_log.init_db()


def log_usage_event(
    *,
    tenant_id: str,
    event_type: str,
    message_id: str,
    source: str,
    intent: Optional[str] = None,
    confidence: Optional[float] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    event = UsageEvent(
        ts=_utc_now_iso(),
        tenant_id=(tenant_id or "").strip(),
        event_type=(event_type or "").strip(),
        message_id=(message_id or "").strip(),
        source=(source or "").strip(),
        intent=intent,
        confidence=confidence,
        meta=meta,
    )
    if not event.tenant_id or not event.event_type or not event.message_id or not event.source:
        return
    _usage_log.append(event)


def list_usage_events(
    *,
    tenant_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    return _usage_log.list_events(tenant_id=tenant_id, limit=limit, offset=offset)


def get_usage_summary(
    *,
    tenant_id: Optional[str] = None,
    event_type: Optional[str] = None,
) -> Dict[str, Any]:
    return _usage_log.summary(tenant_id=tenant_id, event_type=event_type)
