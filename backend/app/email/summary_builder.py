from __future__ import annotations

from typing import Dict, Any

from app.schemas.chat_models import Intent
from app.schemas.email_models import EmailIngestRequest
from app.flows.vpn.vpn_nlp import (
    extract_os,
    extract_client,
    extract_symptom,
    extract_error_code,
)


# ---------------------------------------------------------------------
# VPN Summary Builder
# ---------------------------------------------------------------------

def build_vpn_handoff_summary_from_email(req: EmailIngestRequest) -> Dict[str, Any]:
    text = f"{req.subject}\n{req.body}".strip()

    os_guess = extract_os(text)
    client_guess = extract_client(text)
    symptom_guess = extract_symptom(text)
    code_guess = extract_error_code(text)

    return {
        "category": "VPN_ISSUE",
        "state": "EMAIL_INGEST",
        "os": os_guess.value if os_guess else None,
        "client": client_guess,
        "symptom": symptom_guess.value if symptom_guess else None,
        "error_code": code_guess,
        "attempt_count": 0,
        "steps_given": [],
        "email": {
            "message_id": req.message_id,
            "from": req.from_email,
            "to": req.to_email,
            "subject": req.subject,
        },
    }


# ---------------------------------------------------------------------
# Generic Summary Builder
# ---------------------------------------------------------------------

def build_generic_handoff_summary_from_email(
    req: EmailIngestRequest,
    intent: Intent,
) -> Dict[str, Any]:
    return {
        "category": intent,
        "state": "EMAIL_INGEST",
        "email": {
            "message_id": req.message_id,
            "from": req.from_email,
            "to": req.to_email,
            "subject": req.subject,
        },
        "body": req.body,
    }


# ---------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------

def build_handoff_summary_from_email(
    req: EmailIngestRequest,
    intent: Intent,
) -> Dict[str, Any]:
    """
    Unified summary builder.
    """
    if intent == "VPN_ISSUE":
        return build_vpn_handoff_summary_from_email(req)

    return build_generic_handoff_summary_from_email(req, intent)
