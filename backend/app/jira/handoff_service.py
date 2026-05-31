from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.jira.jira_payloads import (
    build_vpn_incident_payload,
    build_generic_incident_payload,
)
from app.jira.jira_label_mapping import map_internal_tags_to_jira_labels
from app.tagging.internal_tags import attach_internal_tags
from app.tenants.tenant_configs import TenantConfig


def ensure_internal_tags(summary: Dict[str, Any]) -> Dict[str, Any]:
    # idempotent
    try:
        return attach_internal_tags(summary)
    except Exception:
        return summary


def get_internal_tags(summary: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(summary, dict):
        return []
    tags = summary.get("internal_tags")
    return tags if isinstance(tags, list) else []


def build_labels_for_tenant(tenant: TenantConfig, summary: Dict[str, Any]) -> List[str]:
    internal_tags = get_internal_tags(summary)
    return map_internal_tags_to_jira_labels(tenant, internal_tags or [])


def build_vpn_payload_preview(
    *,
    session_id: str,
    tenant: TenantConfig,
    handoff_summary: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Returns: (jira_payload_preview, labels_used)
    """
    ensure_internal_tags(handoff_summary)
    labels = build_labels_for_tenant(tenant, handoff_summary)

    payload = build_vpn_incident_payload(
        session_id=session_id,
        handoff_summary=handoff_summary,
        project_key=tenant.jira_project_key,
        issue_type=tenant.jira_issue_type,
        labels=labels,
    )
    return payload, labels


def build_generic_payload_preview(
    *,
    correlation_id: str,
    tenant: TenantConfig,
    handoff_summary: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Generic (non-VPN) Jira payload preview.
    Used by email ingestion for PASSWORD_RESET / EMAIL_ISSUE / GENERAL / UNKNOWN.
    """
    ensure_internal_tags(handoff_summary)
    labels = build_labels_for_tenant(tenant, handoff_summary)

    payload = build_generic_incident_payload(
        correlation_id=correlation_id,
        handoff_summary=handoff_summary,
        project_key=tenant.jira_project_key,
        issue_type=tenant.jira_issue_type,
        labels=labels,
    )
    return payload, labels
