from __future__ import annotations

import json
import uuid
from typing import List, Tuple, Optional, Dict, Any

from redis import Redis
from app.schemas.chat_models import Intent, VpnContext


class RedisMemoryStore:
    """
    Redis-backed session store with TTL via Redis key expiration.

    Session keys:
      - session:{id}:messages
      - session:{id}:last_intent
      - session:{id}:vpn_context
      - session:{id}:company_id
      - session:{id}:pending_handoff

    Email ingestion (Mode A):
      - email:{message_id}:processed
      - email:{message_id}:receipt

    Email ingestion (Mode B):
      - email:{message_id}:pending
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", ttl_seconds: int = 30 * 60) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds

    # ---------- Internal helpers ----------

    def _norm_mid(self, message_id: Optional[str]) -> str:
        return (message_id or "").strip()

    # ---------- Key helpers ----------

    def _messages_key(self, session_id: str) -> str:
        return f"session:{session_id}:messages"

    def _intent_key(self, session_id: str) -> str:
        return f"session:{session_id}:last_intent"

    def _vpn_key(self, session_id: str) -> str:
        return f"session:{session_id}:vpn_context"

    def _company_key(self, session_id: str) -> str:
        return f"session:{session_id}:company_id"

    def _pending_handoff_key(self, session_id: str) -> str:
        return f"session:{session_id}:pending_handoff"

    # ----- Email keys -----

    def _email_processed_key(self, message_id: str) -> str:
        return f"email:{message_id}:processed"

    def _email_receipt_key(self, message_id: str) -> str:
        return f"email:{message_id}:receipt"

    def _email_pending_key(self, message_id: str) -> str:
        return f"email:{message_id}:pending"

    # ---------- Session TTL touch ----------

    def _touch(self, session_id: str) -> None:
        keys = [
            self._messages_key(session_id),
            self._intent_key(session_id),
            self._vpn_key(session_id),
            self._company_key(session_id),
            self._pending_handoff_key(session_id),
        ]
        for k in keys:
            self.redis.expire(k, self.ttl_seconds)

    # ---------- Sessions ----------

    def get_or_create_session(self, session_id: str | None) -> tuple[str, bool]:
        new_session_id = session_id or str(uuid.uuid4())
        mk = self._messages_key(new_session_id)
        existed = self.redis.exists(mk) == 1
        return new_session_id, not existed

    def session_exists(self, session_id: str) -> bool:
        return self.redis.exists(self._messages_key(session_id)) == 1

    def add_message(self, session_id: str, role: str, message: str) -> None:
        mk = self._messages_key(session_id)
        self.redis.rpush(
            mk,
            json.dumps({"role": role, "message": message}, ensure_ascii=False),
        )
        self._touch(session_id)

    def get_history(self, session_id: str) -> List[Tuple[str, str]]:
        mk = self._messages_key(session_id)
        raw_items = self.redis.lrange(mk, 0, -1)

        history: List[Tuple[str, str]] = []
        for raw in raw_items:
            try:
                obj = json.loads(raw)
                history.append((obj.get("role", ""), obj.get("message", "")))
            except Exception:
                continue

        self._touch(session_id)
        return history

    def get_last_intent(self, session_id: str) -> Optional[Intent]:
        val = self.redis.get(self._intent_key(session_id))
        self._touch(session_id)
        return val  # type: ignore[return-value]

    def set_last_intent(self, session_id: str, intent: Intent) -> None:
        self.redis.set(self._intent_key(session_id), intent)
        self._touch(session_id)

    # ---------- Tenant ----------

    def get_company_id(self, session_id: str) -> Optional[str]:
        val = self.redis.get(self._company_key(session_id))
        self._touch(session_id)
        return val

    def set_company_id(self, session_id: str, company_id: str) -> None:
        self.redis.set(self._company_key(session_id), company_id)
        self._touch(session_id)

    # ---------- Pending handoff (chat) ----------

    def get_pending_handoff_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        raw = self.redis.get(self._pending_handoff_key(session_id))
        self._touch(session_id)
        if not raw:
            return None
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def set_pending_handoff_summary(self, session_id: str, summary: Dict[str, Any]) -> None:
        self.redis.set(
            self._pending_handoff_key(session_id),
            json.dumps(summary, ensure_ascii=False),
        )
        self._touch(session_id)

    def clear_pending_handoff(self, session_id: str) -> None:
        self.redis.delete(self._pending_handoff_key(session_id))
        self._touch(session_id)

    # ---------- VPN context ----------

    def get_vpn_context(self, session_id: str) -> VpnContext:
        raw = self.redis.get(self._vpn_key(session_id))
        self._touch(session_id)
        if not raw:
            return VpnContext()
        try:
            return VpnContext.model_validate_json(raw)
        except Exception:
            return VpnContext()

    def set_vpn_context(self, session_id: str, ctx: VpnContext) -> None:
        self.redis.set(self._vpn_key(session_id), ctx.model_dump_json())
        self._touch(session_id)

    def clear_vpn_context(self, session_id: str) -> None:
        self.redis.delete(self._vpn_key(session_id))
        self._touch(session_id)

    # ---------- Email idempotency + receipts (Mode A) ----------

    def is_email_processed(self, message_id: str) -> bool:
        mid = self._norm_mid(message_id)
        if not mid:
            return False
        return self.redis.exists(self._email_processed_key(mid)) == 1

    def mark_email_processed(self, message_id: str) -> None:
        mid = self._norm_mid(message_id)
        if not mid:
            return
        self.redis.setex(self._email_processed_key(mid), self.ttl_seconds, "1")

    def get_email_receipt(self, message_id: str) -> Optional[Dict[str, Any]]:
        mid = self._norm_mid(message_id)
        if not mid:
            return None

        raw = self.redis.get(self._email_receipt_key(mid))
        if not raw:
            return None

        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def set_email_receipt(self, message_id: str, receipt: Dict[str, Any]) -> None:
        mid = self._norm_mid(message_id)
        if not mid or not isinstance(receipt, dict):
            return

        self.redis.setex(
            self._email_receipt_key(mid),
            self.ttl_seconds,
            json.dumps(receipt, ensure_ascii=False),
        )

    # ---------- Email pending storage (Mode B) ----------

    def get_pending_email(self, message_id: str) -> Optional[Dict[str, Any]]:
        mid = self._norm_mid(message_id)
        if not mid:
            return None

        raw = self.redis.get(self._email_pending_key(mid))
        if not raw:
            return None

        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def set_pending_email(self, message_id: str, payload: Dict[str, Any]) -> None:
        mid = self._norm_mid(message_id)
        if not mid or not isinstance(payload, dict):
            return

        self.redis.setex(
            self._email_pending_key(mid),
            self.ttl_seconds,
            json.dumps(payload, ensure_ascii=False),
        )

    def clear_pending_email(self, message_id: str) -> None:
        mid = self._norm_mid(message_id)
        if not mid:
            return
        self.redis.delete(self._email_pending_key(mid))

    def list_pending_emails(self, limit: int = 200) -> List[str]:
        """
        Mode B helper:
        Return a stable list of message_ids currently stored as pending.

        Uses SCAN to avoid blocking Redis. `limit` caps how many IDs we return.
        """
        pattern = "email:*:pending"
        cursor = 0
        out: List[str] = []

        while True:
            cursor, keys = self.redis.scan(cursor=cursor, match=pattern, count=200)

            for k in keys:
                # key format: email:{message_id}:pending
                # split only the outer parts so message_id can safely contain ':'
                if not k.startswith("email:") or not k.endswith(":pending"):
                    continue
                mid = k[len("email:") : -len(":pending")]
                if mid:
                    out.append(mid)
                    if len(out) >= limit:
                        return sorted(set(out))

            if cursor == 0:
                break

        return sorted(set(out))

    # ---------- Cleanup ----------

    def delete_session(self, session_id: str) -> bool:
        deleted = self.redis.delete(
            self._messages_key(session_id),
            self._intent_key(session_id),
            self._vpn_key(session_id),
            self._company_key(session_id),
            self._pending_handoff_key(session_id),
        )
        return deleted > 0
