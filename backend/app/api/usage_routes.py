import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.storage.usage_event_log import (
    list_usage_events,
    get_usage_summary,
)

router = APIRouter()
logger = logging.getLogger("chatbox")


# ---------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------

class UsageEventOut(BaseModel):
    ts: str
    tenant_id: str
    event_type: str
    message_id: str
    source: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    meta: Optional[Dict[str, Any]] = None


class UsageEventsResponse(BaseModel):
    events: List[UsageEventOut] = Field(default_factory=list)


class UsageSummaryResponse(BaseModel):
    tenant_id: Optional[str] = None
    event_type_filter: Optional[str] = None
    total: int = 0
    by_event_type: Dict[str, int] = Field(default_factory=dict)
    by_intent: Dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------

@router.get("/usage/events", response_model=UsageEventsResponse)
def get_usage_events(
    tenant_id: Optional[str] = Query(default=None, min_length=3, max_length=128),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> UsageEventsResponse:
    """
    Returns raw billing/audit events.
    """
    tenant_id = (tenant_id or "").strip() or None

    events_raw = list_usage_events(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )

    out: List[UsageEventOut] = []
    for e in events_raw:
        try:
            out.append(UsageEventOut(**e))
        except Exception:
            continue

    logger.info(
        f"usage_events_list tenant_id={tenant_id or 'ALL'} "
        f"limit={limit} offset={offset} returned={len(out)}"
    )

    return UsageEventsResponse(events=out)


@router.get("/usage/summary", response_model=UsageSummaryResponse)
def usage_summary(
    tenant_id: Optional[str] = Query(default=None, min_length=3, max_length=128),
    event_type: Optional[str] = Query(default=None, min_length=3, max_length=64),
) -> UsageSummaryResponse:
    """
    Billing-friendly summary.

    Examples:
    - /api/usage/summary?tenant_id=bank_demo
    - /api/usage/summary?tenant_id=auto_demo
    - /api/usage/summary
    - /api/usage/summary?tenant_id=bank_demo&event_type=jira_preview_generated
    """
    tenant_id = (tenant_id or "").strip() or None
    event_type = (event_type or "").strip() or None

    summary_raw = get_usage_summary(
        tenant_id=tenant_id,
        event_type=event_type,
    )

    logger.info(
        f"usage_summary tenant_id={tenant_id or 'ALL'} "
        f"event_type={event_type or 'ALL'} total={summary_raw.get('total', 0)}"
    )

    return UsageSummaryResponse(**summary_raw)
