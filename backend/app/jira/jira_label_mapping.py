from __future__ import annotations

from typing import Iterable, List, Set

from app.tenants.tenant_configs import TenantConfig


def map_internal_tags_to_jira_labels(
    tenant: TenantConfig,
    internal_tags: Iterable[str],
) -> List[str]:
    """
    Convert internal tags -> tenant-specific Jira labels.

    Rules:
    - Start with tenant.default_labels
    - Then add mapped labels from tenant.label_map
    - If an internal tag has no mapping, ignore it (internal-only stays internal)
    - Deduplicate while preserving order
    """

    out: List[str] = []
    seen: Set[str] = set()

    def _add(label: str) -> None:
        l = (label or "").strip()
        if not l:
            return
        if l not in seen:
            seen.add(l)
            out.append(l)

    # 1) tenant defaults first
    for l in tenant.default_labels or ():
        _add(l)

    # 2) mapped labels
    label_map = tenant.label_map or {}
    for tag in internal_tags:
        t = (tag or "").strip().lower()
        if not t:
            continue
        mapped = label_map.get(t)
        if not mapped:
            continue
        for l in mapped:
            _add(l)

    return out
