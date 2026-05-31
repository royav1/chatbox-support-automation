import logging
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tenants.tenant_configs import (
    TenantConfig,
    get_tenant_or_none,
    list_tenants,
)
from app.tenants.tenant_registry import save_tenant_to_registry
from app.storage.usage_event_log import log_usage_event

router = APIRouter()
logger = logging.getLogger("chatbox")

DEFAULT_TENANT_LABELS = ("it-support",)
DEFAULT_TENANT_COMPONENT = "Customer Support"


class TenantCreateRequest(BaseModel):
    tenant_id: str = Field(min_length=3, max_length=128)
    display_name: str = Field(min_length=3, max_length=256)

    jira_project_key: str = Field(min_length=2, max_length=32)
    jira_issue_type: str = Field(min_length=2, max_length=64)

    default_labels: List[str] = Field(default_factory=list)
    component: Optional[str] = Field(default=None, max_length=128)

    label_map: Dict[str, List[str]] = Field(default_factory=dict)


class TenantOut(BaseModel):
    tenant_id: str
    display_name: str
    jira_project_key: str
    jira_issue_type: str
    default_labels: List[str] = Field(default_factory=list)
    component: Optional[str] = None
    label_map: Dict[str, List[str]] = Field(default_factory=dict)


class TenantListResponse(BaseModel):
    tenants: List[TenantOut] = Field(default_factory=list)


class TenantLabelConfigUpdate(BaseModel):
    default_labels: Optional[List[str]] = None
    label_map: Optional[Dict[str, List[str]]] = None


class TenantLabelConfigOut(BaseModel):
    tenant_id: str
    default_labels: List[str] = Field(default_factory=list)
    label_map: Dict[str, List[str]] = Field(default_factory=dict)


def _normalize_labels(labels: List[str]) -> Tuple[str, ...]:
    return tuple(label.strip() for label in labels if label.strip())


def _normalize_label_map(label_map: Dict[str, List[str]]) -> Dict[str, Tuple[str, ...]]:
    return {
        key.strip().lower(): _normalize_labels(labels)
        for key, labels in label_map.items()
        if key.strip() and _normalize_labels(labels)
    }


def _to_out(config: TenantConfig) -> TenantOut:
    return TenantOut(
        tenant_id=config.tenant_id,
        display_name=config.display_name,
        jira_project_key=config.jira_project_key,
        jira_issue_type=config.jira_issue_type,
        default_labels=list(config.default_labels or ()),
        component=config.component,
        label_map={
            str(k): list(v or ())
            for k, v in (config.label_map or {}).items()
        },
    )


def _to_label_config_out(config: TenantConfig) -> TenantLabelConfigOut:
    return TenantLabelConfigOut(
        tenant_id=config.tenant_id,
        default_labels=list(config.default_labels or ()),
        label_map={
            str(k): list(v or ())
            for k, v in (config.label_map or {}).items()
        },
    )


@router.get("/tenants", response_model=TenantListResponse)
def get_tenants() -> TenantListResponse:
    return TenantListResponse(
        tenants=[_to_out(t) for t in list_tenants()]
    )


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: str) -> TenantOut:
    tenant = get_tenant_or_none(tenant_id.strip())
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _to_out(tenant)


@router.get("/tenants/{tenant_id}/labels", response_model=TenantLabelConfigOut)
def get_tenant_labels(tenant_id: str) -> TenantLabelConfigOut:
    tenant = get_tenant_or_none(tenant_id.strip())
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _to_label_config_out(tenant)


@router.patch("/tenants/{tenant_id}/labels", response_model=TenantLabelConfigOut)
def update_tenant_labels(
    tenant_id: str,
    request: TenantLabelConfigUpdate,
) -> TenantLabelConfigOut:
    tenant = get_tenant_or_none(tenant_id.strip())
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    default_labels = (
        _normalize_labels(request.default_labels)
        if request.default_labels is not None
        else tuple(tenant.default_labels or ())
    )
    label_map = (
        _normalize_label_map(request.label_map)
        if request.label_map is not None
        else dict(tenant.label_map or {})
    )

    updated = TenantConfig(
        tenant_id=tenant.tenant_id,
        display_name=tenant.display_name,
        jira_project_key=tenant.jira_project_key,
        jira_issue_type=tenant.jira_issue_type,
        default_labels=default_labels,
        component=tenant.component,
        label_map=label_map,
    )

    saved = save_tenant_to_registry(updated)
    try:
        log_usage_event(
            tenant_id=saved.tenant_id,
            event_type="label_mapping_updated",
            message_id=saved.tenant_id,
            source="tenant_api",
            meta={
                "default_labels_updated": request.default_labels is not None,
                "label_map_updated": request.label_map is not None,
                "label_map_keys": sorted((request.label_map or {}).keys()),
            },
        )
    except Exception:
        logger.exception(f"usage_log_label_mapping_updated_failed tenant_id={saved.tenant_id}")

    logger.info(f"tenant_labels_updated tenant_id={saved.tenant_id}")
    return _to_label_config_out(saved)


@router.post("/tenants", response_model=TenantOut)
def create_or_update_tenant(request: TenantCreateRequest) -> TenantOut:
    tenant_id = request.tenant_id.strip()
    is_new_tenant = get_tenant_or_none(tenant_id) is None
    default_labels = _normalize_labels(request.default_labels)
    component = request.component.strip() if request.component else ""

    if not default_labels:
        default_labels = DEFAULT_TENANT_LABELS

    label_map = _normalize_label_map(request.label_map)

    config = TenantConfig(
        tenant_id=tenant_id,
        display_name=request.display_name.strip(),
        jira_project_key=request.jira_project_key.strip(),
        jira_issue_type=request.jira_issue_type.strip(),
        default_labels=default_labels,
        component=component or DEFAULT_TENANT_COMPONENT,
        label_map=label_map,
    )

    saved = save_tenant_to_registry(config)

    if is_new_tenant:
        try:
            log_usage_event(
                tenant_id=saved.tenant_id,
                event_type="tenant_created",
                message_id=saved.tenant_id,
                source="tenant_api",
                meta={
                    "display_name": saved.display_name,
                    "jira_project_key": saved.jira_project_key,
                    "component": saved.component,
                },
            )
        except Exception:
            logger.exception(f"usage_log_tenant_created_failed tenant_id={saved.tenant_id}")

    logger.info(
        f"tenant_persisted tenant_id={saved.tenant_id} "
        f"jira_project_key={saved.jira_project_key}"
    )

    return _to_out(saved)
