from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime, timezone

from app.schemas.chat_models import Intent
from app.tenants.tenant_gate import validate_and_get_tenant
from app.jira.handoff_service import (
    ensure_internal_tags,
    get_internal_tags,
    build_vpn_payload_preview,
    build_generic_payload_preview,
)
from app.email.pending_store import (
    store_pending_email,
    get_pending_email,
    clear_pending_email,
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bump_pending_attempt(
    *,
    memory: Any,
    message_id: str,
    pending: Dict[str, Any],
) -> None:
    try:
        pending["attempt_count"] = int(pending.get("attempt_count", 0) or 0) + 1
    except Exception:
        pending["attempt_count"] = 1

    pending["updated_at"] = _iso_now()

    store_pending_email(
        memory=memory,
        message_id=message_id,
        payload=pending,
    )


def _build_preview_from_pending(
    *,
    mid: str,
    tenant: Any,
    pending: Dict[str, Any],
) -> Tuple[Intent, float, List[str], Dict[str, Any], Dict[str, Any], List[str]]:
    intent = pending.get("intent", "UNKNOWN")
    confidence = float(pending.get("confidence", 0.0) or 0.0)
    handoff_summary = pending.get("handoff_summary") or {
        "category": intent,
        "state": "EMAIL_INGEST",
    }

    ensure_internal_tags(handoff_summary)
    internal_tags = get_internal_tags(handoff_summary)

    if intent == "VPN_ISSUE":
        jira_payload_preview, labels = build_vpn_payload_preview(
            session_id=mid,
            tenant=tenant,
            handoff_summary=handoff_summary,
        )
    else:
        jira_payload_preview, labels = build_generic_payload_preview(
            correlation_id=mid,
            tenant=tenant,
            handoff_summary=handoff_summary,
        )

    return (
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
        labels,
    )


# ---------------------------------------------------------------------
# Mode B: resolve pending email
# ---------------------------------------------------------------------

def process_email_resolution_to_jira_preview(
    *,
    memory: Any,
    message_id: str,
    company_id: str,
    logger: Any,
) -> Tuple[str, Optional[str], Intent, float, List[str], Dict[str, Any], Optional[Dict[str, Any]]]:

    mid = (message_id or "").strip()
    cid = (company_id or "").strip()

    if not mid or not cid:
        logger.info(
            f"email_resolve_invalid_input message_id={mid or None} company_id={cid or None}"
        )
        return (
            "pending_tenant",
            None,
            "UNKNOWN",
            0.0,
            [],
            {"category": "UNKNOWN", "state": "EMAIL_RESOLVE"},
            None,
        )

    pending = get_pending_email(memory=memory, message_id=mid)
    if not pending:
        logger.info(f"email_resolve_missing_pending message_id={mid}")
        return (
            "pending_tenant",
            None,
            "UNKNOWN",
            0.0,
            [],
            {"category": "UNKNOWN", "state": "EMAIL_RESOLVE"},
            None,
        )

    tenant, valid = validate_and_get_tenant(cid)
    if tenant is None:
        logger.info(
            f"email_resolve_invalid_tenant message_id={mid} company_id={cid} valid={valid}"
        )

        _bump_pending_attempt(
            memory=memory,
            message_id=mid,
            pending=pending,
        )

        intent = pending.get("intent", "UNKNOWN")
        confidence = float(pending.get("confidence", 0.0) or 0.0)
        handoff_summary = pending.get("handoff_summary") or {
            "category": intent,
            "state": "EMAIL_INGEST",
        }
        internal_tags = pending.get("internal_tags", [])

        return (
            "pending_tenant",
            None,
            intent,
            confidence,
            internal_tags,
            handoff_summary,
            None,
        )

    (
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
        labels,
    ) = _build_preview_from_pending(
        mid=mid,
        tenant=tenant,
        pending=pending,
    )

    clear_pending_email(memory=memory, message_id=mid)

    logger.info(
        f"email_resolved message_id={mid} tenant_id={tenant.tenant_id} "
        f"intent={intent} conf={confidence:.2f} labels={labels}"
    )

    return (
        "processed",
        tenant.tenant_id,
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
    )


# ---------------------------------------------------------------------
# Mode B: reprocess pending email
# ---------------------------------------------------------------------

def process_pending_email_reprocess_to_jira_preview(
    *,
    memory: Any,
    message_id: str,
    logger: Any,
) -> Tuple[str, Optional[str], Intent, float, List[str], Dict[str, Any], Optional[Dict[str, Any]]]:

    mid = (message_id or "").strip()

    if not mid:
        logger.info("email_reprocess_invalid_input message_id=None")
        return (
            "pending_tenant",
            None,
            "UNKNOWN",
            0.0,
            [],
            {"category": "UNKNOWN", "state": "EMAIL_REPROCESS"},
            None,
        )

    pending = get_pending_email(memory=memory, message_id=mid)
    if not pending:
        logger.info(f"email_reprocess_missing_pending message_id={mid}")
        return (
            "pending_tenant",
            None,
            "UNKNOWN",
            0.0,
            [],
            {"category": "UNKNOWN", "state": "EMAIL_REPROCESS"},
            None,
        )

    candidate_company_id = (
        pending.get("candidate_company_id")
        or pending.get("inferred_from_email")
        or ""
    )
    cid = str(candidate_company_id or "").strip()

    tenant, valid = (
        validate_and_get_tenant(cid)
        if cid
        else (None, False)
    )

    if tenant is None:
        logger.info(
            f"email_reprocess_still_pending message_id={mid} "
            f"candidate_company_id={cid or None} valid={valid}"
        )

        _bump_pending_attempt(
            memory=memory,
            message_id=mid,
            pending=pending,
        )

        intent = pending.get("intent", "UNKNOWN")
        confidence = float(pending.get("confidence", 0.0) or 0.0)
        handoff_summary = pending.get("handoff_summary") or {
            "category": intent,
            "state": "EMAIL_REPROCESS",
        }
        internal_tags = pending.get("internal_tags", [])

        return (
            "pending_tenant",
            None,
            intent,
            confidence,
            internal_tags,
            handoff_summary,
            None,
        )

    (
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
        labels,
    ) = _build_preview_from_pending(
        mid=mid,
        tenant=tenant,
        pending=pending,
    )

    clear_pending_email(memory=memory, message_id=mid)

    logger.info(
        f"email_reprocessed message_id={mid} tenant_id={tenant.tenant_id} "
        f"intent={intent} conf={confidence:.2f} labels={labels}"
    )

    return (
        "processed",
        tenant.tenant_id,
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
    )