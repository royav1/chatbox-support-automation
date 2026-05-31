import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.schemas.email_models import EmailIngestRequest, EmailIngestResponse
from app.storage.store_factory import get_memory, cleanup_if_supported
from app.email.email_service import (
    ingest_email_service,
    resolve_email_service,
    reprocess_pending_email_service,
)
from app.email.email_pending_query import (
    list_pending_emails_service,
    get_pending_email_details_service,
)

router = APIRouter()
logger = logging.getLogger("chatbox")


# ---------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------

class EmailResolveRequest(BaseModel):
    message_id: str = Field(min_length=3, max_length=512)
    company_id: Optional[str] = Field(default=None)


class EmailReprocessRequest(BaseModel):
    message_id: str = Field(min_length=3, max_length=512)


class EmailPendingListResponse(BaseModel):
    pending: List[str] = Field(default_factory=list)


class EmailPendingDetailsResponse(BaseModel):
    pending: Dict[str, Any]


# ---------------------------------------------------------------------
# EMAIL INGEST
# ---------------------------------------------------------------------

@router.post("/email/ingest", response_model=EmailIngestResponse)
def ingest_email(
    request: EmailIngestRequest,
    x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
) -> EmailIngestResponse:

    memory = get_memory()
    expired = cleanup_if_supported(memory)
    if expired:
        logger.info(f"cleanup_expired removed={expired}")

    if not request.message_id:
        raise HTTPException(status_code=422, detail="message_id is required")

    return ingest_email_service(
        memory=memory,
        request=request,
        x_company_id=x_company_id,
        logger=logger,
    )


# ---------------------------------------------------------------------
# EMAIL RESOLVE
# ---------------------------------------------------------------------

@router.post("/email/resolve", response_model=EmailIngestResponse)
def resolve_email(
    request: EmailResolveRequest,
    x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
) -> EmailIngestResponse:

    memory = get_memory()
    expired = cleanup_if_supported(memory)
    if expired:
        logger.info(f"cleanup_expired removed={expired}")

    message_id = (request.message_id or "").strip()
    if not message_id:
        raise HTTPException(status_code=422, detail="message_id is required")

    company_id = (x_company_id or request.company_id or "").strip()
    if not company_id:
        raise HTTPException(
            status_code=422,
            detail="company_id is required (X-Company-Id header or body)",
        )

    return resolve_email_service(
        memory=memory,
        message_id=message_id,
        company_id=company_id,
        logger=logger,
    )


# ---------------------------------------------------------------------
# EMAIL REPROCESS PENDING
# ---------------------------------------------------------------------

@router.post("/email/reprocess", response_model=EmailIngestResponse)
def reprocess_pending_email(request: EmailReprocessRequest) -> EmailIngestResponse:
    memory = get_memory()
    expired = cleanup_if_supported(memory)
    if expired:
        logger.info(f"cleanup_expired removed={expired}")

    message_id = (request.message_id or "").strip()
    if not message_id:
        raise HTTPException(status_code=422, detail="message_id is required")

    # If already processed, service will return duplicate_skipped with receipt.
    if not memory.is_email_processed(message_id):
        pending = get_pending_email_details_service(
            memory=memory,
            message_id=message_id,
        )
        if not pending:
            logger.info(f"email_reprocess_not_found message_id={message_id}")
            raise HTTPException(status_code=404, detail="Pending email not found")

    return reprocess_pending_email_service(
        memory=memory,
        message_id=message_id,
        logger=logger,
    )


# ---------------------------------------------------------------------
# LIST PENDING
# ---------------------------------------------------------------------

@router.get("/email/pending", response_model=EmailPendingListResponse)
def list_pending_emails() -> EmailPendingListResponse:
    memory = get_memory()
    pending_ids = list_pending_emails_service(memory)
    return EmailPendingListResponse(pending=pending_ids)


# ---------------------------------------------------------------------
# PENDING DETAILS
# ---------------------------------------------------------------------

@router.get("/email/pending/{message_id}", response_model=EmailPendingDetailsResponse)
def get_pending_email_details(message_id: str) -> EmailPendingDetailsResponse:
    memory = get_memory()
    expired = cleanup_if_supported(memory)
    if expired:
        logger.info(f"cleanup_expired removed={expired}")

    mid = (message_id or "").strip()
    if not mid:
        raise HTTPException(status_code=422, detail="message_id is required")

    pending = get_pending_email_details_service(
        memory=memory,
        message_id=mid,
    )

    if not pending:
        logger.info(f"email_pending_details_not_found message_id={mid}")
        raise HTTPException(status_code=404, detail="Pending email not found")

    logger.info(f"email_pending_details_returned message_id={mid}")
    return EmailPendingDetailsResponse(pending=pending)