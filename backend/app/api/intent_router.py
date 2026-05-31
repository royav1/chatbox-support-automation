from __future__ import annotations

from typing import Any, Tuple

from app.schemas.chat_models import VpnState
from app.services.classifier import classify


def route_intent(
    *,
    memory: Any,
    session_id: str,
    message: str,
) -> Tuple[str, float]:
    """
    Decide intent/confidence and persist last_intent.
    Rule: if VPN flow already started (state != VPN_START), force VPN_ISSUE.
    """
    prev_intent = memory.get_last_intent(session_id)

    vpn_ctx = None
    try:
        vpn_ctx = memory.get_vpn_context(session_id)
    except Exception:
        vpn_ctx = None

    if vpn_ctx is not None and getattr(vpn_ctx, "state", None) and vpn_ctx.state != VpnState.VPN_START:
        intent, confidence = "VPN_ISSUE", 0.99
    else:
        intent, confidence = classify(message, previous_intent=prev_intent)

    memory.set_last_intent(session_id, intent)
    return intent, confidence
