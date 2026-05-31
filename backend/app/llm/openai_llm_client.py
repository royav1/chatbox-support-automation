from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.llm.llm_models import LlmClassificationResult

logger = logging.getLogger("chatbox")


ALLOWED_INTENTS = {
    "VPN_ISSUE",
    "PASSWORD_RESET",
    "EMAIL_ISSUE",
    "GENERAL",
    "UNKNOWN",
}

ALLOWED_INTERNAL_TAGS = {
    "vpn",
    "password",
    "email",
    "general",
    "unknown",
    "connectivity",
    "stability",
    "access",
    "escalated",
    "error_619",
    "error_809",
    "error_812",
    "error_691",
    "error_720",
    "error_721",
    "certificate",
    "auth_failed",
    "timeout",
}


def _get_openai_client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        logger.info("email_llm_openai_missing_api_key")
        return None

    timeout_raw = os.getenv("OPENAI_TIMEOUT_SECONDS", "20")

    try:
        timeout = float(timeout_raw)
    except Exception:
        logger.info(
            f"email_llm_config_invalid key=OPENAI_TIMEOUT_SECONDS "
            f"value={timeout_raw} fallback=20"
        )
        timeout = 20.0

    return OpenAI(api_key=api_key, timeout=timeout)


def _build_json_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intent": {
                "type": "string",
                "enum": sorted(ALLOWED_INTENTS),
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
            },
            "reason": {
                "type": "string",
            },
            "extracted_fields": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "symptom": {
                        "type": ["string", "null"],
                        "enum": [
                            "cannot_connect",
                            "connects_no_access",
                            "disconnects",
                            "slow_connection",
                            "auth_failed",
                            "certificate",
                            "timeout",
                            None,
                        ],
                    },
                    "error_code": {
                        "type": ["string", "null"],
                    },
                },
                "required": ["symptom", "error_code"],
            },
            "internal_tags": {
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
        },
        "required": [
            "intent",
            "confidence",
            "reason",
            "extracted_fields",
            "internal_tags",
        ],
    }


def _sanitize_internal_tags(tags: Any) -> List[str]:
    if not isinstance(tags, list):
        return []

    clean: List[str] = []

    for tag in tags:
        if not isinstance(tag, str):
            continue

        normalized = tag.strip().lower().replace(" ", "_")
        if not normalized:
            continue

        if normalized in ALLOWED_INTERNAL_TAGS or normalized.startswith("error_"):
            if normalized not in clean:
                clean.append(normalized)

    return clean


def _sanitize_extracted_fields(intent: str, fields: Any) -> Dict[str, Any]:
    if not isinstance(fields, dict):
        return {}

    if intent != "VPN_ISSUE":
        return {}

    symptom = fields.get("symptom")
    error_code = fields.get("error_code")

    if symptom is not None:
        symptom = str(symptom).strip()
        if not symptom:
            symptom = None

    if error_code is not None:
        error_code = str(error_code).strip()
        if not error_code:
            error_code = None

    return {
        "symptom": symptom,
        "error_code": error_code,
    }


def _parse_openai_json(raw_text: str) -> Dict[str, Any]:
    if not raw_text or not raw_text.strip():
        raise ValueError("empty_openai_response")

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid_openai_json: {e}") from e


def openai_classify_email(text: str) -> Optional[LlmClassificationResult]:
    client = _get_openai_client()

    if client is None:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

    system_prompt = """
You classify IT support emails for an internal multi-tenant support automation system.

Return only structured JSON matching the schema.

Allowed intents:
- VPN_ISSUE
- PASSWORD_RESET
- EMAIL_ISSUE
- GENERAL
- UNKNOWN

Rules:
- Use VPN_ISSUE only for VPN/connectivity-to-company-network problems.
- Use PASSWORD_RESET for password reset, locked account, forgotten password, login access reset.
- Use EMAIL_ISSUE for Outlook/Gmail/mail sending/receiving/sync issues.
- Use GENERAL for clear IT issues that do not fit the above.
- Use UNKNOWN when the message is too vague.

Confidence:
- 0.90-1.00: very clear
- 0.75-0.89: likely
- 0.50-0.74: uncertain
- below 0.50: unclear

For VPN_ISSUE only, extract:
- symptom: one of cannot_connect, connects_no_access, disconnects, slow_connection, auth_failed, certificate, timeout, or null
- error_code: numeric code as a string if present, otherwise null

internal_tags:
- Always include "escalated".
- Add useful tags only from: vpn, password, email, general, unknown, connectivity, stability, access, certificate, auth_failed, timeout.
- For VPN numeric error codes, add "error_<code>", for example "error_619".
""".strip()

    user_prompt = f"""
Classify this support email:

{text or ""}
""".strip()

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "email_classification",
                "schema": _build_json_schema(),
                "strict": True,
            }
        },
    )

    raw_output = response.output_text
    data = _parse_openai_json(raw_output)

    intent = str(data.get("intent", "UNKNOWN")).strip()

    if intent not in ALLOWED_INTENTS:
        intent = "UNKNOWN"

    extracted_fields = _sanitize_extracted_fields(
        intent=intent,
        fields=data.get("extracted_fields", {}),
    )

    internal_tags = _sanitize_internal_tags(data.get("internal_tags", []))

    if "escalated" not in internal_tags:
        internal_tags.append("escalated")

    return LlmClassificationResult(
        intent=intent,
        confidence=float(data.get("confidence", 0.0)),
        reason=data.get("reason"),
        extracted_fields=extracted_fields,
        internal_tags=internal_tags,
    )