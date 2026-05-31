from __future__ import annotations

from typing import Any, Optional, Tuple

from app.schemas.chat_models import VpnState
from app.flows.vpn.vpn_flow import handle_vpn_message
from app.tenants.tenant_gate import ask_for_company_id
from app.jira.handoff_service import (
    ensure_internal_tags,
    build_vpn_payload_preview,
    get_internal_tags,
)


def handle_vpn(
    *,
    memory: Any,
    session_id: str,
    message: str,
    tenant: Any,  # TenantConfig or None
    logger: Any,
) -> Tuple[str, bool, Optional[dict], Optional[dict]]:
    """
    Runs VPN flow for the given message and returns:
      (reply, handoff, handoff_summary, jira_payload_preview)
    Handles:
    - missing-tenant at handoff => store pending + rollback ctx + ask company_id
    - tenant present at handoff => finalize + build jira preview (+labels)
    """
    handoff_summary = None
    jira_payload_preview = None

    ctx = memory.get_vpn_context(session_id)
    ctx, reply, handoff, handoff_summary = handle_vpn_message(message, ctx)

    # If flow requested handoff but tenant missing -> pending gate
    if handoff and handoff_summary and tenant is None:
        ensure_internal_tags(handoff_summary)

        try:
            memory.set_pending_handoff_summary(session_id, handoff_summary)
        except Exception:
            pass

        ctx.state = VpnState.VPN_CHECK_RESULT
        memory.set_vpn_context(session_id, ctx)

        logger.info(
            f"handoff_blocked_missing_company session_id={session_id} "
            f"rolled_back_state={ctx.state} tags={get_internal_tags(handoff_summary)}"
        )

        return ask_for_company_id(), False, handoff_summary, None

    # Normal persistence
    memory.set_vpn_context(session_id, ctx)

    logger.info(
        f"vpn_flow session_id={session_id} state={ctx.state} os={ctx.os} "
        f"client={getattr(ctx, 'client', None)} symptom={getattr(ctx, 'symptom', None)} "
        f"error={ctx.error_code} attempts={ctx.attempt_count} handoff={handoff}"
    )

    # If tenant exists and handoff -> finalize + payload
    if handoff and handoff_summary and tenant is not None:
        ensure_internal_tags(handoff_summary)

        if getattr(ctx, "state", None) != VpnState.VPN_HANDOFF:
            ctx.state = VpnState.VPN_HANDOFF
            memory.set_vpn_context(session_id, ctx)

        jira_payload_preview, labels = build_vpn_payload_preview(
            session_id=session_id,
            tenant=tenant,
            handoff_summary=handoff_summary,
        )

        logger.info(
            f"jira_payload_preview_built session_id={session_id} company_id={tenant.tenant_id} "
            f"summary={jira_payload_preview['fields']['summary']}"
        )
        try:
            logger.info(f"internal_tags session_id={session_id} tags={get_internal_tags(handoff_summary)}")
        except Exception:
            pass
        try:
            logger.info(f"jira_labels session_id={session_id} company_id={tenant.tenant_id} labels={labels}")
        except Exception:
            pass

    return reply, handoff, handoff_summary, jira_payload_preview
