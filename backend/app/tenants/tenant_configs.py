from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: str
    display_name: str

    jira_project_key: str
    jira_issue_type: str

    # Tenant default labels always added.
    # Under Option A, these should be broad organizational / ownership labels only,
    # not issue-domain labels like "vpn".
    default_labels: Tuple[str, ...] = ()

    # Optional
    component: Optional[str] = None

    # internal-tag -> jira labels mapping (per tenant)
    # Example: "stability" -> ("vpn-disconnect",)
    label_map: Dict[str, Tuple[str, ...]] = None  # type: ignore[assignment]


def _vpn_demo_label_map(
    network_label: str,
    business_labels: Dict[str, Tuple[str, ...]],
) -> Dict[str, Tuple[str, ...]]:
    return {
        "vpn": ("vpn",),
        "connectivity": (network_label,),
        "error_619": ("error-619",),
        "escalated": ("escalated",),
        **business_labels,
    }


DEMO_TENANTS: Tuple[TenantConfig, ...] = (
    TenantConfig(
        tenant_id="bank_demo",
        display_name="Bank Demo",
        jira_project_key="BANK",
        jira_issue_type="Incident",
        default_labels=("it-support",),
        component="Banking Infrastructure",
        label_map=_vpn_demo_label_map(
            "bank-network",
            {
                "mfa_login": ("mfa-login",),
                "branch_employee_portal": ("branch-portal",),
                "mobile_payment_system": ("payment-system",),
            },
        ),
    ),
    TenantConfig(
        tenant_id="auto_demo",
        display_name="Auto Demo",
        jira_project_key="AUTO",
        jira_issue_type="Incident",
        default_labels=("it-support",),
        component="Garage Operations",
        label_map=_vpn_demo_label_map(
            "auto-network",
            {
                "spare_parts_ordering": ("spare-parts",),
                "parts_supplier_portal": ("supplier-portal",),
                "garage_inventory_sync": ("inventory-sync",),
            },
        ),
    ),
    TenantConfig(
        tenant_id="health_demo",
        display_name="Health Demo",
        jira_project_key="HEALTH",
        jira_issue_type="Incident",
        default_labels=("it-support",),
        component="Healthcare Systems",
        label_map=_vpn_demo_label_map(
            "health-network",
            {
                "gift_card_management": ("gift-card",),
                "patient_records_portal": ("patient-portal",),
                "appointment_booking_system": ("appointments",),
            },
        ),
    ),
    TenantConfig(
        tenant_id="fox_clothes_demo",
        display_name="Fox Clothes Demo",
        jira_project_key="FOX",
        jira_issue_type="Incident",
        default_labels=("it-support",),
        component="Retail Operations",
        label_map=_vpn_demo_label_map(
            "fox-network",
            {
                "store_pos_system": ("pos-system",),
                "warehouse_inventory_sync": ("inventory-sync",),
                "online_order_management": ("online-orders",),
            },
        ),
    ),
    TenantConfig(
        tenant_id="candyshop_demo",
        display_name="Candyshop Demo",
        jira_project_key="CANDY",
        jira_issue_type="Incident",
        default_labels=("it-support",),
        component="Retail Operations",
        label_map={},
    ),
    TenantConfig(
        tenant_id="hatifim_demo",
        display_name="Hatifim Demo",
        jira_project_key="HATIFIM",
        jira_issue_type="Incident",
        default_labels=("it-support",),
        component="Customer Support",
        label_map={},
    ),
)


TENANTS: Dict[str, TenantConfig] = {
    config.tenant_id: config
    for config in DEMO_TENANTS
}


def list_tenant_ids() -> Tuple[str, ...]:
    return tuple(TENANTS.keys())


def is_valid_tenant_id(tenant_id: str) -> bool:
    return tenant_id in TENANTS


def get_tenant_or_none(tenant_id: Optional[str]) -> Optional[TenantConfig]:
    if not tenant_id:
        return None
    return TENANTS.get(tenant_id)


def upsert_tenant(config: TenantConfig) -> TenantConfig:
    TENANTS[config.tenant_id] = config
    return config


def list_tenants() -> Tuple[TenantConfig, ...]:
    return tuple(TENANTS.values())
