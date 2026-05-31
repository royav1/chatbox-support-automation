from __future__ import annotations

from typing import Any, Dict, List, Optional


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _normalize_error_code(raw: Optional[str]) -> Optional[str]:
    """
    Normalize error_code into a tag-friendly signal.
    Examples:
      "619" -> "error_619"
      "809" -> "error_809"
      "CERTIFICATE" -> "certificate"
      "AUTH_FAILED" -> "auth_failed"
      "TIMEOUT" -> "timeout"
      ""/None -> None
    """
    if not raw:
        return None

    s = _safe_str(raw).strip().lower()
    if not s:
        return None

    # numeric error codes
    if s.isdigit():
        return f"error_{s}"

    # keyword-style signals
    if "cert" in s:
        return "certificate"
    if "auth" in s:
        return "auth_failed"
    if "timeout" in s or "timed out" in s:
        return "timeout"

    # fallback: keep a safe form
    return s.replace(" ", "_")


def _problem_class_from_symptom(symptom: Optional[str]) -> str:
    """
    Dimension 2: Problem class (stable across companies).
    VPN symptom -> internal problem class
    """
    s = _safe_str(symptom).strip().lower()

    # Your VpnSymptom values are:
    # - cannot_connect
    # - connects_no_access
    # - disconnects
    if s == "cannot_connect":
        return "connectivity"
    if s == "connects_no_access":
        return "access"
    if s == "disconnects":
        return "stability"

    return "other"


def _dedupe_normalized(tags: List[str]) -> List[str]:
    """
    Deduplicate while preserving order.
    Also normalizes to lowercase/stripped, and drops empties.
    """
    seen = set()
    out: List[str] = []
    for t in tags:
        t2 = _safe_str(t).strip().lower()
        if not t2:
            continue
        if t2 not in seen:
            seen.add(t2)
            out.append(t2)
    return out


def build_internal_tags_for_vpn(handoff_summary: Dict[str, Any], *, include_process_tag: bool = True) -> List[str]:
    """
    Build internal-only tags for VPN handoff.

    Dimensions:
      1) Domain: vpn
      2) Problem class: connectivity / access / stability / other
      3) Technical signal: error_619 / certificate / auth_failed / timeout / ...
      4) Process: escalated (only when a handoff is being created)

    Output: stable ordered list of tags, no duplicates.
    """
    tags: List[str] = []

    # Dimension 1: Domain
    tags.append("vpn")

    # Dimension 2: Problem class (from symptom)
    symptom = handoff_summary.get("symptom")
    tags.append(_problem_class_from_symptom(symptom))

    # Dimension 3: Technical signal (from error_code)
    signal = _normalize_error_code(handoff_summary.get("error_code"))
    if signal:
        tags.append(signal)

    # Dimension 4: Process tag
    # We add it when this summary represents an escalation/handoff event.
    if include_process_tag:
        tags.append("escalated")

    return _dedupe_normalized(tags)


def build_internal_tags_for_generic(category: str) -> List[str]:
    """
    Minimal stable taxonomy for non-VPN categories (pre-LLM).

    We keep it intentionally small and consistent across tenants.
    Later the LLM can enrich signals (systems, apps, urgency, etc.)
    without changing the meaning of these base tags.
    """
    c = _safe_str(category).strip().upper()

    if c == "PASSWORD_RESET":
        return _dedupe_normalized(["password", "escalated"])

    if c == "EMAIL_ISSUE":
        return _dedupe_normalized(["email", "escalated"])

    if c == "GENERAL":
        return _dedupe_normalized(["general", "escalated"])

    # UNKNOWN or anything else
    return _dedupe_normalized(["unknown", "escalated"])


def attach_internal_tags(handoff_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mutates and returns the same dict for convenience.
    Ensures handoff_summary has "internal_tags".
    """
    if not isinstance(handoff_summary, dict):
        return handoff_summary  # type: ignore[return-value]

    category = _safe_str(handoff_summary.get("category")).strip().upper()

    if category == "VPN_ISSUE":
        handoff_summary["internal_tags"] = build_internal_tags_for_vpn(handoff_summary)
    else:
        handoff_summary["internal_tags"] = build_internal_tags_for_generic(category)

    return handoff_summary
