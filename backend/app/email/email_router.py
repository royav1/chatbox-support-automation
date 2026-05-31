from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime, timezone

from app.schemas.chat_models import Intent
from app.schemas.email_models import EmailIngestRequest
from app.services.classifier import classify
from app.tenants.tenant_gate import validate_and_get_tenant
from app.jira.handoff_service import (
    ensure_internal_tags,
    get_internal_tags,
    build_vpn_payload_preview,
    build_generic_payload_preview,
)

from app.email.tenant_inference import infer_tenant_id_from_to_email
from app.email.summary_builder import build_handoff_summary_from_email
from app.email.pending_store import store_pending_email
from app.llm.llm_service import classify_email_with_llm


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_llm_provider_name() -> str:
    return os.getenv("LLM_PROVIDER", "mock").strip().lower() or "mock"


# ---------------------------------------------------------------------
# Main processor (INGEST)
# ---------------------------------------------------------------------

def process_email_to_jira_preview(
    *,
    memory: Any,
    req: EmailIngestRequest,
    x_company_id: Optional[str],
    logger: Any,
) -> Tuple[str, Optional[str], Intent, float, List[str], Dict[str, Any], Optional[Dict[str, Any]]]:

    # ---- Tenant resolution ----
    inferred_tenant = infer_tenant_id_from_to_email(req.to_email)

    candidate_company_id = (
        x_company_id
        or req.company_id
        or inferred_tenant
        or ""
    ).strip()

    tenant, valid = (
        validate_and_get_tenant(candidate_company_id)
        # `valid` is currently unused, kept for future differentiation
        # between missing vs invalid tenant (observability / validation improvements)
        if candidate_company_id
        else (None, False)
    )

    # ---- Intent classification ----
    text = f"{req.subject}\n{req.body}".strip()

    llm_result = classify_email_with_llm(text)
    if llm_result:
        intent = llm_result.intent
        confidence = float(llm_result.confidence)
        provider = _get_llm_provider_name()

        logger.info(
            f"email_llm_classified message_id={req.message_id} "
            f"intent={intent} conf={confidence:.2f} provider={provider}"
        )
    else:
        intent, confidence = classify(text, previous_intent=None)

    # ---- Build handoff summary ----
    handoff_summary = build_handoff_summary_from_email(req, intent)

    # ---- LLM field enrichment (safe, optional) ----
    if llm_result and llm_result.extracted_fields:
        fields = llm_result.extracted_fields

        # Only enrich for VPN for now (safe controlled scope)
        if intent == "VPN_ISSUE":
            if not handoff_summary.get("symptom") and fields.get("symptom"):
                handoff_summary["symptom"] = fields.get("symptom")

            if not handoff_summary.get("error_code") and fields.get("error_code"):
                handoff_summary["error_code"] = fields.get("error_code")

    ensure_internal_tags(handoff_summary)
    internal_tags = get_internal_tags(handoff_summary)

    # ---- LLM tag enrichment (safe, optional) ----
    if llm_result and llm_result.internal_tags:
        allowed_tags = {
            "vpn",
            "connectivity",
            "access",
            "stability",
            "certificate",
            "auth_failed",
            "timeout",
            "password",
            "email",
            "general",
            "unknown",
            "escalated",
        }

        llm_tags = [
            tag
            for tag in llm_result.internal_tags
            if isinstance(tag, str)
            and (
                tag in allowed_tags
                or (tag.startswith("error_") and tag.removeprefix("error_").isdigit())
            )
        ]

        # Merge without duplicates while preserving existing order
        for tag in llm_tags:
            if tag not in internal_tags:
                internal_tags.append(tag)

        # Keep summary consistent
        handoff_summary["internal_tags"] = internal_tags

    # ---- Missing tenant → pending ----
    if tenant is None:
        now = _iso_now()

        pending_payload: Dict[str, Any] = {
            "message_id": req.message_id,
            "status": "pending_tenant",
            "created_at": now,
            "updated_at": now,
            "attempt_count": 0,

            "intent": intent,
            "confidence": float(confidence),
            "internal_tags": internal_tags,
            "handoff_summary": handoff_summary,

            "candidate_company_id": candidate_company_id or None,
            "inferred_from_email": inferred_tenant,
        }

        store_pending_email(
            memory=memory,
            message_id=req.message_id,
            payload=pending_payload,
        )

        logger.info(
            f"email_pending_tenant message_id={req.message_id} "
            f"candidate_company_id={candidate_company_id or None} "
            f"inferred_from_email={inferred_tenant} "
            f"intent={intent} conf={confidence:.2f}"
        )

        return (
            "pending_tenant",
            None,
            intent,
            confidence,
            internal_tags,
            handoff_summary,
            None,
        )

    # ---- Build Jira payload preview ----
    if intent == "VPN_ISSUE":
        jira_payload_preview, labels = build_vpn_payload_preview(
            session_id=req.message_id,
            tenant=tenant,
            handoff_summary=handoff_summary,
        )
    else:
        jira_payload_preview, labels = build_generic_payload_preview(
            correlation_id=req.message_id,
            tenant=tenant,
            handoff_summary=handoff_summary,
        )

    logger.info(
        f"email_processed message_id={req.message_id} "
        f"tenant_id={tenant.tenant_id} "
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
