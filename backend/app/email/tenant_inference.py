from __future__ import annotations

from typing import Optional, Dict

from app.tenants.tenant_configs import TENANTS


# Optional aliases (nice for demos):
#   user+bank@gmail.com -> bank_demo
#   user+auto@gmail.com -> auto_demo
TENANT_ALIASES: Dict[str, str] = {
    "bank": "bank_demo",
    "auto": "auto_demo",
}


def _extract_plus_token(to_email: str) -> Optional[str]:
    """
    Extract plus-address token from an email.
    Examples:
      "roy+bank_demo@gmail.com" -> "bank_demo"
      "roy+bank@gmail.com"      -> "bank"
      "roy@gmail.com"           -> None
    """
    if not to_email:
        return None

    s = to_email.strip().lower()
    if "@" not in s:
        return None

    local, _domain = s.split("@", 1)
    if "+" not in local:
        return None

    _base, token = local.split("+", 1)
    token = token.strip()
    return token or None


def infer_tenant_id_from_to_email(to_email: str) -> Optional[str]:
    """
    Infer a tenant_id from to_email using plus-addressing.

    Priority:
      1) Direct tenant_id token: +bank_demo / +auto_demo
      2) Alias token: +bank / +auto (optional)
    """
    token = _extract_plus_token(to_email)
    if not token:
        return None

    # direct tenant id
    if token in TENANTS:
        return token

    # alias
    mapped = TENANT_ALIASES.get(token)
    if mapped in TENANTS:
        return mapped

    return None
