import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header

from app.schemas.chat_models import (
    ChatRequest,
    ChatResponse,
    SessionHistoryResponse,
    MessageItem,
)
from app.storage.store_factory import get_memory, cleanup_if_supported
from app.api.chat_controller import handle_chat

router = APIRouter()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("chatbox")


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
) -> ChatResponse:
    return handle_chat(request, x_company_id, logger)


@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
def get_session_history(session_id: str) -> SessionHistoryResponse:
    memory = get_memory()

    expired = cleanup_if_supported(memory)
    if expired:
        logger.info(f"cleanup_expired removed={expired}")

    if not memory.session_exists(session_id):
        logger.info(f"history_not_found session_id={session_id}")
        raise HTTPException(status_code=404, detail="Session not found")

    history = memory.get_history(session_id)
    last_intent = memory.get_last_intent(session_id)

    messages = [MessageItem(role=role, message=msg) for role, msg in history]

    logger.info(
        f"history_returned session_id={session_id} message_count={len(messages)} last_intent={last_intent}"
    )

    return SessionHistoryResponse(
        session_id=session_id,
        last_intent=last_intent,
        messages=messages,
        message_count=len(messages),
    )


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    memory = get_memory()

    expired = cleanup_if_supported(memory)
    if expired:
        logger.info(f"cleanup_expired removed={expired}")

    deleted = memory.delete_session(session_id)
    if not deleted:
        logger.info(f"delete_not_found session_id={session_id}")
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info(f"delete_session session_id={session_id}")
    return {"status": "deleted", "session_id": session_id}
