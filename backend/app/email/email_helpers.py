from __future__ import annotations
from typing import Any, Dict, Optional, List
from app.storage.usage_event_log import log_usage_event


# ---------------------------------------------------------------------
# Receipt helpers
# ---------------------------------------------------------------------

def try_get_receipt(memory: Any, message_id: str) -> Optional[Dict[str, Any]]:
    getter = getattr(memory, "get_email_receipt", None)
    if callable(getter):
        try:
            receipt = getter(message_id)
            return receipt if isinstance(receipt, dict) else None
        except Exception:
            return None
    return None


def try_set_receipt(memory: Any, message_id: str, receipt: Dict[str, Any]) -> None:
    setter = getattr(memory, "set_email_receipt", None)
    if callable(setter):
        try:
            setter(message_id, receipt)
        except Exception:
            pass


# ---------------------------------------------------------------------
# Pending helpers
# ---------------------------------------------------------------------

def try_clear_pending(memory: Any, message_id: str) -> None:
    clearer = getattr(memory, "clear_pending_email", None)
    if callable(clearer):
        try:
            clearer(message_id)
        except Exception:
            pass


def try_list_pending(memory: Any) -> List[str]:
    lister = getattr(memory, "list_pending_emails", None)
    if callable(lister):
        try:
            result = lister()
            return result if isinstance(result, list) else []
        except Exception:
            return []
    return []


def try_get_pending(memory: Any, message_id: str) -> Optional[Dict[str, Any]]:
    getter = getattr(memory, "get_pending_email", None)
    if callable(getter):
        try:
            payload = getter(message_id)
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------
# Billing / usage logging
# ---------------------------------------------------------------------

def try_log_billable_event(
    *,
    tenant_id: Optional[str],
    message_id: str,
    source: str,
    intent: Any,
    confidence: float,
    internal_tags: List[str],
) -> None:
    tid = (tenant_id or "").strip()
    mid = (message_id or "").strip()
    if not tid or not mid:
        return

    try:
        log_usage_event(
            tenant_id=tid,
            event_type="jira_preview_generated",
            message_id=mid,
            source=source,
            intent=str(intent) if intent is not None else None,
            confidence=float(confidence) if confidence is not None else None,
            meta={"internal_tags": internal_tags},
        )
    except Exception:
        pass


def try_log_email_ingested_event(
    *,
    tenant_id: Optional[str],
    message_id: str,
    intent: Any,
    confidence: float,
    internal_tags: List[str],
) -> None:
    tid = (tenant_id or "").strip()
    mid = (message_id or "").strip()
    if not tid or not mid:
        return

    try:
        log_usage_event(
            tenant_id=tid,
            event_type="email_ingested",
            message_id=mid,
            source="email_ingest",
            intent=str(intent) if intent is not None else None,
            confidence=float(confidence) if confidence is not None else None,
            meta={"internal_tags": internal_tags},
        )
    except Exception:
        pass
