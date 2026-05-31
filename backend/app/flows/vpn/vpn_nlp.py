import re
from typing import Optional

from app.schemas.chat_models import VpnOS, VpnSymptom


def _norm(text: str) -> str:
    return (text or "").lower().replace("’", "'").strip()


def extract_os(text: str) -> Optional[VpnOS]:
    t = _norm(text)

    if any(x in t for x in ["windows", "win", "win11", "win 11", "win10", "win 10", "win7", "win 7"]):
        return VpnOS.WINDOWS

    if any(x in t for x in ["mac", "macos", "osx", "os x", "macbook"]):
        return VpnOS.MAC

    if any(x in t for x in ["linux", "ubuntu", "debian", "fedora", "arch"]):
        return VpnOS.LINUX

    if any(x in t for x in ["android", "iphone", "ios", "ipad"]):
        return VpnOS.OTHER

    return None


def extract_client(text: str) -> Optional[str]:
    """
    Best-effort VPN client extraction.
    Returns a normalized client name or None.

    If the user does not know the client, return "Unknown" so the flow can continue.
    """
    t = _norm(text)

    unknown_patterns = [
        "not sure",
        "not shure",
        "don't know",
        "dont know",
        "i don't kno",
        "dont kno",
        "i don't know",
        "i dont know",
        "unknown",
        "no idea",
        "idk",
    ]

    if any(x in t for x in unknown_patterns):
        return "Unknown"

    if "anyconnect" in t or "any connect" in t or "cisco" in t:
        return "AnyConnect"

    if "globalprotect" in t or "global protect" in t:
        return "GlobalProtect"

    if "forticlient" in t or "forti" in t:
        return "FortiClient"

    return None


def extract_symptom(text: str) -> Optional[VpnSymptom]:
    """
    Extract high-level VPN symptom category.
    Handles common wording variations and small typos.
    """
    t = _norm(text)

    cannot_connect_patterns = [
        "can't connect",
        "cant connect",
        "cannot connect",
        "can not connect",
        "won't connect",
        "wont connect",
        "fails to connect",
        "failed to connect",
        "doesn't connect",
        "doesnt connect",
        "not connecting",
        "cant conect",
        "can't conect",
        "cannot conect",
        "conect",
    ]

    no_access_patterns = [
        "connects but",
        "connected but",
        "no access",
        "no internal access",
        "can't access internal",
        "cant access internal",
        "cannot access internal",
        "connected no access",
        "connected without access",
    ]

    disconnect_patterns = [
        "disconnects",
        "disconnect",
        "disconnecting",
        "drops",
        "keeps disconnecting",
        "keeps dropping",
        "unstable",
        "not stable",
        "connection drops",
    ]

    if any(x in t for x in cannot_connect_patterns):
        return VpnSymptom.CANNOT_CONNECT

    if any(x in t for x in no_access_patterns):
        return VpnSymptom.CONNECTS_NO_ACCESS

    if any(x in t for x in disconnect_patterns):
        return VpnSymptom.DISCONNECTS

    return None


def extract_error_code(text: str) -> Optional[str]:
    """
    Captures:
    - "619"
    - "error 619"
    - "error code: 809"
    Also supports keyword-style signals.
    """
    t = _norm(text)

    m = re.search(
        r"\b(?:error\s*code\s*[:\-]?\s*|error\s*[:\-]?\s*|code\s*[:\-]?\s*)?(\d{3,4})\b",
        t,
    )
    if m:
        return m.group(1)

    if any(k in t for k in ["certificate", "cert", "expired certificate"]):
        return "CERTIFICATE"

    if any(k in t for k in ["timeout", "timed out"]):
        return "TIMEOUT"

    if any(k in t for k in ["auth failed", "authentication failed", "login failed", "invalid credentials", "auth error"]):
        return "AUTH_FAILED"

    return None


def looks_like_success(text: str) -> bool:
    t = _norm(text)
    return any(k in t for k in ["works now", "fixed", "resolved", "it works", "connected", "success", "working now"])


def looks_like_failure(text: str) -> bool:
    t = _norm(text)
    return any(k in t for k in ["still", "doesn't", "doesnt", "not working", "failed", "same error", "nope", "no"])
