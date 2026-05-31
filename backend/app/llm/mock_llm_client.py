from __future__ import annotations

import re

from app.llm.llm_models import LlmClassificationResult


def mock_classify_email(text: str) -> LlmClassificationResult:
    """
    Mock LLM classifier.

    This simulates structured LLM output without API cost.
    Later we can replace this with OpenAI while keeping the same return shape.
    """
    t = (text or "").lower()

    if "vpn" in t:
        error_code = None
        m = re.search(r"\b(?:error\s*)?(\d{3})\b", t)
        if m:
            error_code = m.group(1)

        symptom = None
        if "disconnect" in t:
            symptom = "disconnects"
        elif "no access" in t or "connected but" in t:
            symptom = "connects_no_access"
        elif "cannot connect" in t or "can't connect" in t or "cant connect" in t:
            symptom = "cannot_connect"

        internal_tags = ["vpn"]
        if symptom == "disconnects":
            internal_tags.append("stability")
        elif symptom == "connects_no_access":
            internal_tags.append("access")
        elif symptom == "cannot_connect":
            internal_tags.append("connectivity")

        if error_code:
            internal_tags.append(f"error_{error_code}")

        internal_tags.append("escalated")

        return LlmClassificationResult(
            intent="VPN_ISSUE",
            confidence=0.92,
            reason="Mock LLM detected VPN-related issue.",
            extracted_fields={
                "symptom": symptom,
                "error_code": error_code,
            },
            internal_tags=internal_tags,
        )

    password_signals = [
        "password",
        "locked out",
        "forgot",
        "reset",
        "account access",
        "cannot log in",
        "can't log in",
        "cant log in",
        "login issue",
        "sign in",
        "locked account",
        "account locked",
        "password expired",
    ]

    if any(signal in t for signal in password_signals):
        return LlmClassificationResult(
            intent="PASSWORD_RESET",
            confidence=0.90,
            reason="Mock LLM detected password reset issue.",
            extracted_fields={},
            internal_tags=["password", "escalated"],
        )

    email_signals = [
        "outlook",
        "email",
        "gmail",
        "send emails",
        "receive emails",
        "calendar",
        "calendar sync",
        "meeting invite",
        "email sync",
        "mail sync",
        "exchange",
        "shared mailbox",
        "outlook calendar",
    ]

    if any(signal in t for signal in email_signals):
        return LlmClassificationResult(
            intent="EMAIL_ISSUE",
            confidence=0.88,
            reason="Mock LLM detected email issue.",
            extracted_fields={},
            internal_tags=["email", "escalated"],
        )

    if len(t.strip()) < 8:
        return LlmClassificationResult(
            intent="UNKNOWN",
            confidence=0.45,
            reason="Mock LLM could not infer enough information.",
            extracted_fields={},
            internal_tags=["unknown", "escalated"],
        )

    return LlmClassificationResult(
        intent="GENERAL",
        confidence=0.70,
        reason="Mock LLM classified as general IT issue.",
        extracted_fields={},
        internal_tags=["general", "escalated"],
    )
