from typing import Tuple, Dict, Any, Optional, List

from app.schemas.chat_models import VpnContext, VpnState
from app.flows.vpn.vpn_nlp import (
    extract_os,
    extract_client,
    extract_symptom,
    extract_error_code,
    looks_like_success,
    looks_like_failure,
)


def handoff_summary(ctx: VpnContext) -> Dict[str, Any]:
    return {
        "category": "VPN_ISSUE",
        "state": ctx.state.value,
        "os": ctx.os.value if ctx.os else None,
        "client": ctx.client,
        "symptom": ctx.symptom.value if ctx.symptom else None,
        "error_code": ctx.error_code,
        "attempt_count": ctx.attempt_count,
        "steps_given": ctx.steps_given,
    }


def _steps_for_error(os_value: Optional[str], error_code: Optional[str]) -> List[str]:
    if error_code in {"619", "809", "812"}:
        return [
            "Check internet connectivity (open a normal website)",
            "Verify system time/date is correct",
            "Try a different network (mobile hotspot) to rule out firewall/router blocks",
            "Restart the VPN client",
            "Reboot the machine and try again",
        ]

    if error_code == "CERTIFICATE":
        return [
            "Restart the VPN client",
            "Check if a certificate prompt appears and accept it (if applicable)",
            "If certificate is expired/missing, IT may need to re-issue it",
        ]

    if error_code == "AUTH_FAILED":
        return [
            "Re-type username/password (check Caps Lock)",
            "If SSO: sign out/in via browser and retry",
            "If password was changed recently, wait a few minutes then retry",
        ]

    if error_code == "TIMEOUT":
        return [
            "Try a different network (hotspot) to avoid blocked VPN ports",
            "Restart the VPN client",
            "Reboot and retry",
        ]

    return [
        "Restart the VPN client",
        "Reboot the machine",
        "Try a different network (hotspot)",
    ]


def _give_steps(ctx: VpnContext) -> Tuple[VpnContext, str]:
    ctx.attempt_count += 1

    steps = _steps_for_error(ctx.os.value if ctx.os else None, ctx.error_code)
    ctx.steps_given = steps
    ctx.state = VpnState.VPN_CHECK_RESULT

    steps_text = "\n".join(f"{i + 1}) {s}" for i, s in enumerate(steps))
    reply = (
        f"Thanks. Try these steps:\n{steps_text}\n\n"
        "After trying them, reply with what happened "
        "(works now / still failing + any new error)."
    )
    return ctx, reply


def _ask_next_missing(ctx: VpnContext) -> Tuple[VpnContext, str, bool, Optional[Dict[str, Any]]]:
    if ctx.os is None:
        ctx.state = VpnState.VPN_ASK_OS
        ctx.last_question = "OS"
        return ctx, "Which OS are you on (Windows / Mac / Linux)?", False, None

    if ctx.client is None:
        ctx.state = VpnState.VPN_ASK_CLIENT
        ctx.last_question = "CLIENT"
        return (
            ctx,
            "Do you know which VPN application you use? (AnyConnect / GlobalProtect / FortiClient / Not sure)",
            False,
            None,
        )

    if ctx.symptom is None:
        ctx.state = VpnState.VPN_ASK_SYMPTOM
        ctx.last_question = "SYMPTOM"
        return ctx, (
            "What happens when you try to connect?\n"
            "• Can’t connect at all\n"
            "• Connects but no internal access\n"
            "• Disconnects / unstable"
        ), False, None

    if ctx.error_code is None:
        ctx.state = VpnState.VPN_ASK_ERROR_CODE
        ctx.last_question = "ERROR_CODE"
        return ctx, (
            "Do you see an error code or message?\n"
            "(e.g., 619 / 809 / certificate / auth failed)"
        ), False, None

    ctx.state = VpnState.VPN_GIVE_STEPS
    ctx.last_question = None
    return ctx, "", False, None


def _handoff_reply(payload: Dict[str, Any]) -> str:
    return (
        "I’m going to escalate this to IT support.\n"
        "Here’s what I collected for the handoff:\n"
        f"- OS: {payload['os']}\n"
        f"- VPN client: {payload['client']}\n"
        f"- Symptom: {payload['symptom']}\n"
        f"- Error: {payload['error_code']}\n"
        f"- Attempts: {payload['attempt_count']}\n"
        f"- Steps tried: {', '.join(payload['steps_given']) if payload['steps_given'] else 'N/A'}\n\n"
        "This case is now with IT. If you want to start a new troubleshooting attempt, create a new session (or delete this session)."
    )


def handle_vpn_message(
    message: str,
    ctx: VpnContext,
) -> Tuple[VpnContext, str, bool, Optional[Dict[str, Any]]]:
    msg = message.strip()

    # ✅ TERMINAL LOCK: once handed off, keep returning the same handoff response
    if ctx.state == VpnState.VPN_HANDOFF:
        payload = handoff_summary(ctx)
        return ctx, _handoff_reply(payload), True, payload

    # ---- Best-effort extraction from any message ----
    if ctx.os is None:
        os_guess = extract_os(msg)
        if os_guess:
            ctx.os = os_guess

    if ctx.client is None:
        client_guess = extract_client(msg)
        if client_guess:
            ctx.client = client_guess

    if ctx.symptom is None:
        symptom_guess = extract_symptom(msg)
        if symptom_guess:
            ctx.symptom = symptom_guess

    code_guess = extract_error_code(msg)
    if code_guess and ctx.error_code is None:
        ctx.error_code = code_guess

    # ---- Guard: success/failure phrases only matter in VPN_CHECK_RESULT ----
    if ctx.state != VpnState.VPN_CHECK_RESULT:
        if looks_like_failure(msg) or looks_like_success(msg):
            ctx2, reply, handoff, summary = _ask_next_missing(ctx)
            if reply:
                return ctx2, reply, handoff, summary

    # ---- State machine ----
    if ctx.state == VpnState.VPN_START:
        if ctx.os is None:
            ctx.state = VpnState.VPN_ASK_OS
        elif ctx.client is None:
            ctx.state = VpnState.VPN_ASK_CLIENT
        elif ctx.symptom is None:
            ctx.state = VpnState.VPN_ASK_SYMPTOM
        elif ctx.error_code is None:
            ctx.state = VpnState.VPN_ASK_ERROR_CODE
        else:
            ctx.state = VpnState.VPN_GIVE_STEPS

    if ctx.state == VpnState.VPN_ASK_OS:
        if ctx.os is None:
            ctx.last_question = "OS"
            return ctx, "Which OS are you on (Windows / Mac / Linux)?", False, None
        ctx.last_question = None
        ctx.state = VpnState.VPN_ASK_CLIENT

    if ctx.state == VpnState.VPN_ASK_CLIENT:
        if ctx.client is None:
            ctx.last_question = "CLIENT"
            return (
                ctx,
                "Do you know which VPN application you use? (AnyConnect / GlobalProtect / FortiClient / Not sure)",
                False,
                None,
            )
        ctx.last_question = None
        ctx.state = VpnState.VPN_ASK_SYMPTOM

    if ctx.state == VpnState.VPN_ASK_SYMPTOM:
        if ctx.symptom is None:
            ctx.last_question = "SYMPTOM"
            return ctx, (
                "What happens when you try to connect?\n"
                "• Can’t connect at all\n"
                "• Connects but no internal access\n"
                "• Disconnects / unstable"
            ), False, None
        ctx.last_question = None
        ctx.state = VpnState.VPN_ASK_ERROR_CODE

    if ctx.state == VpnState.VPN_ASK_ERROR_CODE:
        if ctx.error_code is None:
            ctx.last_question = "ERROR_CODE"
            return ctx, (
                "Do you see an error code or message?\n"
                "(e.g., 619 / 809 / certificate / auth failed)"
            ), False, None
        ctx.last_question = None
        ctx.state = VpnState.VPN_GIVE_STEPS

    if ctx.state == VpnState.VPN_GIVE_STEPS:
        ctx, reply = _give_steps(ctx)
        return ctx, reply, False, None

    if ctx.state == VpnState.VPN_CHECK_RESULT:
        if looks_like_success(msg):
            ctx.state = VpnState.VPN_START
            ctx.attempt_count = 0
            ctx.error_code = None
            ctx.steps_given = []
            ctx.last_question = None
            return (
                ctx,
                "Nice — glad it’s working now. "
                "If it happens again, tell me the OS, client, and error code and we’ll troubleshoot quickly.",
                False,
                None,
            )

        if looks_like_failure(msg):
            if ctx.attempt_count >= 2:
                ctx.state = VpnState.VPN_HANDOFF
                payload = handoff_summary(ctx)
                return ctx, _handoff_reply(payload), True, payload

            new_code = extract_error_code(msg)
            if new_code:
                ctx.error_code = new_code

            ctx.state = VpnState.VPN_GIVE_STEPS
            ctx, reply = _give_steps(ctx)
            return ctx, reply, False, None

        return ctx, (
            "Did the steps work?\n"
            "Reply with 'works now' or 'still failing' and include any error message you see."
        ), False, None

    # fallback: do NOT reset to VPN_START, move into the first question state
    ctx.state = VpnState.VPN_ASK_OS
    ctx.last_question = "OS"
    return ctx, "Let’s start over. What OS are you on (Windows / Mac / Linux)?", False, None
