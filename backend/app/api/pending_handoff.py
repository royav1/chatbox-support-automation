from __future__ import annotations

from typing import Any, Optional

from app.schemas.chat_models import ChatRequest, ChatResponse, VpnState
from app.tenants.tenant_gate import (
    ask_for_company_id,
    pick_candidate_company_id,
    validate_and_get_tenant,
)
from app.jira.handoff_service import (
    ensure_internal_tags,
    build_vpn_payload_preview,
    get_internal_tags,
)
from app.storage.usage_event_log import log_usage_event


def try_handle_pending_handoff(
    *,
    memory: Any,
    session_id: str,
    request: ChatRequest,
    x_company_id: Optional[str],
    logger: Any,
) -> Optional[ChatResponse]:
    """
    If this session has a pending handoff summary waiting for tenant/company_id,
    handle it fully and return a ChatResponse. Otherwise return None.
    """
    try:
        pending = memory.get_pending_handoff_summary(session_id)
    except Exception:
        pending = None

    if pending is None:
        return None

    pending = ensure_internal_tags(pending)

    candidate_company_id = pick_candidate_company_id(
        x_company_id=x_company_id,
        request_company_id=getattr(request, "company_id", None),
        message=request.message,
    )

    tenant, valid = validate_and_get_tenant(candidate_company_id)

    if not valid:
        reply = ask_for_company_id()
        memory.add_message(session_id, "assistant", reply)
        logger.info(
            f"pending_handoff_company_invalid session_id={session_id} candidate={candidate_company_id}"
        )
        return ChatResponse(
            session_id=session_id,
            intent=memory.get_last_intent(session_id) or "VPN_ISSUE",
            confidence=0.99,
            reply=reply,
            handoff=False,
            handoff_summary=pending,
            jira_payload_preview=None,
        )

    if tenant is None:
        reply = ask_for_company_id()
        memory.add_message(session_id, "assistant", reply)
        logger.info(
            f"pending_handoff_company_none session_id={session_id} candidate={candidate_company_id}"
        )
        return ChatResponse(
            session_id=session_id,
            intent=memory.get_last_intent(session_id) or "VPN_ISSUE",
            confidence=0.99,
            reply=reply,
            handoff=False,
            handoff_summary=pending,
            jira_payload_preview=None,
        )

    # Persist tenant
    try:
        memory.set_company_id(session_id, tenant.tenant_id)
    except Exception:
        pass

    # Build Jira payload preview (+ labels)
    jira_payload_preview, labels = build_vpn_payload_preview(
        session_id=session_id,
        tenant=tenant,
        handoff_summary=pending,
    )

    # Finalize escalation: mark terminal + clear pending
    try:
        ctx = memory.get_vpn_context(session_id)
        ctx.state = VpnState.VPN_HANDOFF
        memory.set_vpn_context(session_id, ctx)
    except Exception:
        pass

    try:
        memory.clear_pending_handoff(session_id)
    except Exception:
        pass

    reply = (
        "Thanks. I’m escalating this to IT support now.\n"
        f"Company: {tenant.tenant_id}\n"
        "This session is now closed. If you want to start a new troubleshooting attempt, "
        "create a new session (or delete this session)."
    )
    memory.add_message(session_id, "assistant", reply)

    logger.info(
        f"pending_handoff_completed session_id={session_id} company_id={tenant.tenant_id} "
        f"summary={jira_payload_preview['fields']['summary']}"
    )

    try:
        intent = memory.get_last_intent(session_id) or "VPN_ISSUE"
        log_usage_event(
            tenant_id=tenant.tenant_id,
            event_type="jira_preview_generated",
            message_id=session_id,
            source="chat",
            intent=str(intent),
            confidence=0.99,
            meta={
                "internal_tags": get_internal_tags(pending),
            },
        )
        logger.info(
            f"pending_handoff_usage_logged session_id={session_id} company_id={tenant.tenant_id} intent={intent}"
        )
    except Exception as e:
        logger.info(f"pending_handoff_usage_log_failed session_id={session_id} err={type(e).__name__}")

    # Visibility logs
    try:
        logger.info(f"internal_tags session_id={session_id} tags={get_internal_tags(pending)}")
    except Exception:
        pass
    try:
        logger.info(f"jira_labels session_id={session_id} company_id={tenant.tenant_id} labels={labels}")
    except Exception:
        pass

    return ChatResponse(
        session_id=session_id,
        intent=memory.get_last_intent(session_id) or "VPN_ISSUE",
        confidence=0.99,
        reply=reply,
        handoff=True,
        handoff_summary=pending,
        jira_payload_preview=jira_payload_preview,
    )
