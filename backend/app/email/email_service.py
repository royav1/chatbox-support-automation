from __future__ import annotations
from typing import Any, Optional
from app.schemas.email_models import EmailIngestRequest, EmailIngestResponse
from app.email.email_router import process_email_to_jira_preview
from app.email.pending_processor import (
    process_email_resolution_to_jira_preview,
    process_pending_email_reprocess_to_jira_preview,
)

from app.email.email_helpers import (
    try_get_receipt,
    try_set_receipt,
    try_clear_pending,
    try_get_pending,
    try_log_billable_event,
    try_log_email_ingested_event,
)


# ---------------------------------------------------------------------
# INGEST SERVICE
# ---------------------------------------------------------------------

def ingest_email_service(
    *,
    memory: Any,
    request: EmailIngestRequest,
    x_company_id: Optional[str],
    logger: Any,
) -> EmailIngestResponse:
    message_id = (request.message_id or "").strip()

    # ---- Idempotency ----
    if memory.is_email_processed(message_id):
        receipt = try_get_receipt(memory, message_id)
        logger.info(f"email_duplicate_skipped message_id={message_id}")

        if receipt:
            receipt_out = dict(receipt)
            receipt_out["status"] = "duplicate_skipped"
            receipt_out["message_id"] = message_id
            try:
                return EmailIngestResponse(**receipt_out)
            except Exception:
                pass

        return EmailIngestResponse(
            status="duplicate_skipped",
            message_id=message_id,
            tenant_id=None,
            intent="UNKNOWN",
            confidence=0.0,
            internal_tags=[],
            handoff_summary=None,
            jira_payload_preview=None,
        )

    # ---- Processing ----
    (
        status,
        tenant_id,
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
    ) = process_email_to_jira_preview(
        memory=memory,
        req=request,
        x_company_id=x_company_id,
        logger=logger,
    )

    response = EmailIngestResponse(
        status=status,
        message_id=message_id,
        tenant_id=tenant_id,
        intent=intent,
        confidence=float(confidence),
        internal_tags=internal_tags,
        handoff_summary=handoff_summary,
        jira_payload_preview=jira_payload_preview,
    )

    if status == "pending_tenant":
        logger.info(f"email_pending_saved message_id={message_id}")
        return response

    if status == "processed":
        memory.mark_email_processed(message_id)
        try_set_receipt(memory, message_id, response.model_dump())
        try_clear_pending(memory, message_id)

        try_log_email_ingested_event(
            tenant_id=tenant_id,
            message_id=message_id,
            intent=intent,
            confidence=float(confidence),
            internal_tags=internal_tags,
        )

        try_log_billable_event(
            tenant_id=tenant_id,
            message_id=message_id,
            source="email_ingest",
            intent=intent,
            confidence=float(confidence),
            internal_tags=internal_tags,
        )

    return response


# ---------------------------------------------------------------------
# RESOLVE SERVICE
# ---------------------------------------------------------------------

def resolve_email_service(
    *,
    memory: Any,
    message_id: str,
    company_id: str,
    logger: Any,
) -> EmailIngestResponse:
    message_id = (message_id or "").strip()

    if memory.is_email_processed(message_id):
        receipt = try_get_receipt(memory, message_id)
        logger.info(f"email_resolve_duplicate message_id={message_id}")

        if receipt:
            receipt_out = dict(receipt)
            receipt_out["status"] = "duplicate_skipped"
            receipt_out["message_id"] = message_id
            try:
                return EmailIngestResponse(**receipt_out)
            except Exception:
                pass

        return EmailIngestResponse(
            status="duplicate_skipped",
            message_id=message_id,
            tenant_id=None,
            intent="UNKNOWN",
            confidence=0.0,
            internal_tags=[],
            handoff_summary=None,
            jira_payload_preview=None,
        )

    (
        status,
        tenant_id,
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
    ) = process_email_resolution_to_jira_preview(
        memory=memory,
        message_id=message_id,
        company_id=company_id,
        logger=logger,
    )

    response = EmailIngestResponse(
        status=status,
        message_id=message_id,
        tenant_id=tenant_id,
        intent=intent,
        confidence=float(confidence),
        internal_tags=internal_tags,
        handoff_summary=handoff_summary,
        jira_payload_preview=jira_payload_preview,
    )

    if status == "pending_tenant":
        logger.info(f"email_resolve_still_pending message_id={message_id}")
        return response

    if status == "processed":
        memory.mark_email_processed(message_id)
        try_set_receipt(memory, message_id, response.model_dump())
        try_clear_pending(memory, message_id)

        logger.info(
            f"email_resolved_processed message_id={message_id} tenant_id={tenant_id}"
        )

        try_log_billable_event(
            tenant_id=tenant_id,
            message_id=message_id,
            source="email_resolve",
            intent=intent,
            confidence=float(confidence),
            internal_tags=internal_tags,
        )

    return response


# ---------------------------------------------------------------------
# REPROCESS SERVICE
# ---------------------------------------------------------------------

def reprocess_pending_email_service(
    *,
    memory: Any,
    message_id: str,
    logger: Any,
) -> EmailIngestResponse:
    message_id = (message_id or "").strip()

    if memory.is_email_processed(message_id):
        receipt = try_get_receipt(memory, message_id)
        logger.info(f"email_reprocess_duplicate message_id={message_id}")

        if receipt:
            receipt_out = dict(receipt)
            receipt_out["status"] = "duplicate_skipped"
            receipt_out["message_id"] = message_id
            try:
                return EmailIngestResponse(**receipt_out)
            except Exception:
                pass

        return EmailIngestResponse(
            status="duplicate_skipped",
            message_id=message_id,
            tenant_id=None,
            intent="UNKNOWN",
            confidence=0.0,
            internal_tags=[],
            handoff_summary=None,
            jira_payload_preview=None,
        )

    pending = try_get_pending(memory, message_id)
    if not pending:
        logger.info(f"email_reprocess_missing_pending message_id={message_id}")
        return EmailIngestResponse(
            status="pending_tenant",
            message_id=message_id,
            tenant_id=None,
            intent="UNKNOWN",
            confidence=0.0,
            internal_tags=[],
            handoff_summary={"category": "UNKNOWN", "state": "EMAIL_REPROCESS"},
            jira_payload_preview=None,
        )

    (
        status,
        tenant_id,
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
    ) = process_pending_email_reprocess_to_jira_preview(
        memory=memory,
        message_id=message_id,
        logger=logger,
    )

    response = EmailIngestResponse(
        status=status,
        message_id=message_id,
        tenant_id=tenant_id,
        intent=intent,
        confidence=float(confidence),
        internal_tags=internal_tags,
        handoff_summary=handoff_summary,
        jira_payload_preview=jira_payload_preview,
    )

    if status == "pending_tenant":
        logger.info(f"email_reprocess_still_pending message_id={message_id}")
        return response

    if status == "processed":
        memory.mark_email_processed(message_id)
        try_set_receipt(memory, message_id, response.model_dump())
        try_clear_pending(memory, message_id)

        logger.info(
            f"email_reprocessed_processed message_id={message_id} tenant_id={tenant_id}"
        )

        try_log_billable_event(
            tenant_id=tenant_id,
            message_id=message_id,
            source="email_reprocess",
            intent=intent,
            confidence=float(confidence),
            internal_tags=internal_tags,
        )

    return response
