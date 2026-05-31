from __future__ import annotations

from typing import Any, Dict, Optional, List

from app.email.email_helpers import try_list_pending, try_get_pending


def list_pending_emails_service(memory: Any) -> List[str]:
    return try_list_pending(memory)


def get_pending_email_details_service(
    *,
    memory: Any,
    message_id: str,
) -> Optional[Dict[str, Any]]:
    return try_get_pending(memory, message_id)