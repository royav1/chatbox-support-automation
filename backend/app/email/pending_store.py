from __future__ import annotations

from typing import Any, Optional, Dict


# ---------------------------------------------------------------------
# Safe store wrappers (works for MemoryStore + RedisMemoryStore)
# ---------------------------------------------------------------------

def store_pending_email(
    *,
    memory: Any,
    message_id: str,
    payload: Dict[str, Any],
) -> None:
    setter = getattr(memory, "set_pending_email", None)
    if callable(setter):
        try:
            setter(message_id, payload)
        except Exception:
            pass


def get_pending_email(
    *,
    memory: Any,
    message_id: str,
) -> Optional[Dict[str, Any]]:
    getter = getattr(memory, "get_pending_email", None)
    if callable(getter):
        try:
            obj = getter(message_id)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def clear_pending_email(
    *,
    memory: Any,
    message_id: str,
) -> None:
    clearer = getattr(memory, "clear_pending_email", None)
    if callable(clearer):
        try:
            clearer(message_id)
        except Exception:
            pass
