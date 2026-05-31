from __future__ import annotations

from typing import Optional, Tuple

from app.tenants.tenant_configs import get_tenant_or_none, is_valid_tenant_id, list_tenant_ids, TenantConfig


def ask_for_company_id() -> str:
    allowed = ", ".join(list_tenant_ids())
    return (
        "Before I can escalate this to IT, I need the company ID.\n"
        f"Please reply with one of: {allowed}"
    )


def pick_candidate_company_id(
    *,
    x_company_id: Optional[str],
    request_company_id: Optional[str],
    message: str,
) -> str:
    # same precedence you used: Header > Body > (fallback to message)
    return (x_company_id or request_company_id or message).strip()


def validate_and_get_tenant(candidate_company_id: str) -> Tuple[Optional[TenantConfig], bool]:
    """
    Returns: (tenant_or_none, is_valid_id_format)

    - is_valid_id_format=False -> not in our tenant list at all
    - tenant_or_none=None but valid=True should not happen with current config,
      but we keep it for safety (same as old code).
    """
    if not is_valid_tenant_id(candidate_company_id):
        return None, False
    return get_tenant_or_none(candidate_company_id), True
