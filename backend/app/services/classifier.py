import re
from typing import Tuple, Optional
from app.schemas.chat_models import Intent

_VAGUE_PATTERNS = [
    r"\bstill\b",
    r"\bnot working\b",
    r"\bdoesn't work\b",
    r"\bdoesnt work\b",
    r"\bfails?\b",
    r"\berror\b",
    r"\bissue\b",
    r"\bproblem\b",
]

def _is_vague_followup(text: str) -> bool:
    # contains generic "still not working / error / problem" language
    if any(re.search(p, text) for p in _VAGUE_PATTERNS):
        return True
    # also treat "error 619", "error: 619" etc. as a follow-up indicator
    if re.search(r"\berror[: ]*\d+\b", text):
        return True
    return False

def classify(message: str, previous_intent: Optional[Intent] = None) -> Tuple[Intent, float]:
    text = message.lower().strip()

    # Strong explicit matches first
    if re.search(r"\bvpn\b", text):
        return "VPN_ISSUE", 0.80

    if re.search(
        r"password|reset|forgot|locked out|account access|cannot log in|can't log in|cant log in|"
        r"login issue|sign in|locked account|account locked|password expired",
        text,
    ):
        return "PASSWORD_RESET", 0.80

    if re.search(
        r"\bemail\b|outlook|gmail|can't send|cant send|can't receive|cant receive|"
        r"calendar|calendar sync|meeting invite|email sync|mail sync|exchange|"
        r"shared mailbox|outlook calendar",
        text,
    ):
        return "EMAIL_ISSUE", 0.75

    # Context fallback: vague follow-up -> reuse previous intent
    if previous_intent and _is_vague_followup(text):
        return previous_intent, 0.62

    # Fallbacks
    if len(text) < 8:
        return "UNKNOWN", 0.40

    return "GENERAL", 0.55
