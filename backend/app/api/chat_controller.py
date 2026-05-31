from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from app.schemas.chat_models import ChatRequest, ChatResponse, VpnState
from app.services.responder import respond
from app.storage.store_factory import get_memory, cleanup_if_supported
from app.tenants.tenant_gate import validate_and_get_tenant

from app.api.pending_handoff import try_handle_pending_handoff
from app.api.intent_router import route_intent
from app.api.vpn_handler import handle_vpn
from app.jira.handoff_service import get_internal_tags
from app.storage.usage_event_log import log_usage_event


def handle_chat(request: ChatRequest, x_company_id: Optional[str], logger: Any) -> ChatResponse:
    memory = get_memory()

    expired = cleanup_if_supported(memory)
    if expired:
        logger.info(f"cleanup_expired removed={expired}")

    session_id, created = memory.get_or_create_session(request.session_id)

    # Always store user message
    memory.add_message(session_id, "user", request.message)

    # 1) Pending-handoff gate (if needed)
    pending_response = try_handle_pending_handoff(
        memory=memory,
        session_id=session_id,
        request=request,
        x_company_id=x_company_id,
        logger=logger,
    )
    if pending_response is not None:
        return pending_response

    # 2) Terminal lock check
    vpn_ctx = None
    try:
        vpn_ctx = memory.get_vpn_context(session_id)
    except Exception:
        vpn_ctx = None

    if vpn_ctx is not None and getattr(vpn_ctx, "state", None) == VpnState.VPN_HANDOFF:
        logger.info(f"chat_blocked_handoff session_id={session_id} state={vpn_ctx.state}")
        raise HTTPException(
            status_code=409,
            detail="This session was escalated to IT support and is now closed. Start a new session or delete this session.",
        )

    # 3) Resolve tenant (Header > Body > Session)
    session_company_id = None
    try:
        session_company_id = memory.get_company_id(session_id)
    except Exception:
        session_company_id = None

    company_id = x_company_id or getattr(request, "company_id", None) or session_company_id
    tenant = None
    try:
        tenant = validate_and_get_tenant(company_id)[0] if company_id else None
    except Exception:
        tenant = None

    if tenant is not None:
        try:
            memory.set_company_id(session_id, tenant.tenant_id)
        except Exception:
            pass

    logger.info(
        f"chat_request session_id={session_id} created={created} msg_len={len(request.message)} "
        f"company_id={tenant.tenant_id if tenant else None}"
    )

    # 4) Intent routing
    intent, confidence = route_intent(memory=memory, session_id=session_id, message=request.message)

    # 5) Handle
    handoff_summary = None
    jira_payload_preview = None

    if intent == "VPN_ISSUE":
        reply, handoff, handoff_summary, jira_payload_preview = handle_vpn(
            memory=memory,
            session_id=session_id,
            message=request.message,
            tenant=tenant,
            logger=logger,
        )
    else:
        reply, handoff = respond(intent)

    if handoff and jira_payload_preview and tenant is not None:
        try:
            log_usage_event(
                tenant_id=tenant.tenant_id,
                event_type="jira_preview_generated",
                message_id=session_id,
                source="chat",
                intent=str(intent),
                confidence=float(confidence),
                meta={
                    "internal_tags": get_internal_tags(handoff_summary),
                },
            )
            logger.info(
                f"chat_usage_logged session_id={session_id} company_id={tenant.tenant_id} intent={intent}"
            )
        except Exception as e:
            logger.info(f"chat_usage_log_failed session_id={session_id} err={type(e).__name__}")

    memory.add_message(session_id, "assistant", reply)

    logger.info(
        f"chat_classified session_id={session_id} intent={intent} confidence={confidence:.2f} handoff={handoff}"
    )

    return ChatResponse(
        session_id=session_id,
        intent=intent,
        confidence=confidence,
        reply=reply,
        handoff=handoff,
        handoff_summary=handoff_summary,
        jira_payload_preview=jira_payload_preview,
    )
