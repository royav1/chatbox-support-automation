from __future__ import annotations

from typing import Dict, List, Tuple, Optional, Any
import uuid
import time

from app.schemas.chat_models import Intent, VpnContext


class MemoryStore:
    """
    In-memory session store with TTL.

    Sessions (chat):
    - session_id -> list of (role, message)
    - session_id -> last detected intent (context)
    - session_id -> vpn context
    - session_id -> company_id (tenant)
    - session_id -> pending_handoff_summary (dict)  # used when tenant is missing at escalation time
    - session_id -> last_seen timestamp (for expiration)

    Email ingestion (Mode A):
    - message_id -> processed marker (idempotency / dedupe)
    - message_id -> receipt (stored response payload for deterministic duplicate responses)

    Email ingestion (Mode B):
    - message_id -> pending payload (stored when tenant is missing / pending_tenant)
      so it can later be resolved via /email/resolve.
    """

    def __init__(self, ttl_seconds: int = 30 * 60) -> None:
        # Chat session state
        self._sessions: Dict[str, List[Tuple[str, str]]] = {}
        self._last_intent: Dict[str, Intent] = {}
        self._vpn_context: Dict[str, VpnContext] = {}
        self._company_id: Dict[str, str] = {}
        self._pending_handoff_summary: Dict[str, Dict[str, Any]] = {}
        self._last_seen: Dict[str, float] = {}

        # Email idempotency (Mode A)
        # message_id -> timestamp when marked processed
        self._processed_emails: Dict[str, float] = {}

        # Email receipts (Option B)
        # message_id -> {"ts": float, "receipt": dict}
        self._email_receipts: Dict[str, Dict[str, Any]] = {}

        # Email pending payloads (Mode B)
        # message_id -> {"ts": float, "payload": dict}
        self._pending_emails: Dict[str, Dict[str, Any]] = {}

        self._ttl_seconds = ttl_seconds

    # ---------- Internal helpers ----------

    def _now(self) -> float:
        return time.time()

    def _norm_message_id(self, message_id: Optional[str]) -> str:
        return (message_id or "").strip()

    def _touch(self, session_id: str) -> None:
        self._last_seen[session_id] = self._now()

    # ---------- TTL cleanup ----------

    def cleanup_expired(self) -> int:
        now = self._now()
        expired_ids: List[str] = []

        for sid, last_seen in list(self._last_seen.items()):
            if now - last_seen > self._ttl_seconds:
                expired_ids.append(sid)

        for sid in expired_ids:
            self._sessions.pop(sid, None)
            self._last_intent.pop(sid, None)
            self._vpn_context.pop(sid, None)
            self._company_id.pop(sid, None)
            self._pending_handoff_summary.pop(sid, None)
            self._last_seen.pop(sid, None)

        # Cleanup email processed markers on the same TTL window
        for mid, ts in list(self._processed_emails.items()):
            if now - ts > self._ttl_seconds:
                self._processed_emails.pop(mid, None)

        # Cleanup email receipts on the same TTL window
        for mid, obj in list(self._email_receipts.items()):
            ts = obj.get("ts")
            if isinstance(ts, (int, float)) and (now - float(ts) > self._ttl_seconds):
                self._email_receipts.pop(mid, None)

        # Cleanup pending emails on the same TTL window
        for mid, obj in list(self._pending_emails.items()):
            ts = obj.get("ts")
            if isinstance(ts, (int, float)) and (now - float(ts) > self._ttl_seconds):
                self._pending_emails.pop(mid, None)

        return len(expired_ids)

    # ---------- Chat sessions ----------

    def get_or_create_session(self, session_id: str | None) -> tuple[str, bool]:
        self.cleanup_expired()

        if session_id and session_id in self._sessions:
            self._touch(session_id)
            return session_id, False

        new_session_id = session_id or str(uuid.uuid4())
        created = new_session_id not in self._sessions

        self._sessions.setdefault(new_session_id, [])
        self._touch(new_session_id)
        return new_session_id, created

    def session_exists(self, session_id: str) -> bool:
        self.cleanup_expired()
        return session_id in self._sessions

    def add_message(self, session_id: str, role: str, message: str) -> None:
        self.cleanup_expired()
        self._sessions.setdefault(session_id, []).append((role, message))
        self._touch(session_id)

    def get_history(self, session_id: str) -> List[Tuple[str, str]]:
        self.cleanup_expired()
        if session_id in self._sessions:
            self._touch(session_id)
        return self._sessions.get(session_id, [])

    def get_last_intent(self, session_id: str) -> Optional[Intent]:
        self.cleanup_expired()
        if session_id in self._sessions:
            self._touch(session_id)
        return self._last_intent.get(session_id)

    def set_last_intent(self, session_id: str, intent: Intent) -> None:
        self.cleanup_expired()
        self._last_intent[session_id] = intent
        self._touch(session_id)

    # ----- Company / tenant -----

    def get_company_id(self, session_id: str) -> Optional[str]:
        self.cleanup_expired()
        if session_id in self._sessions:
            self._touch(session_id)
        return self._company_id.get(session_id)

    def set_company_id(self, session_id: str, company_id: str) -> None:
        self.cleanup_expired()
        self._company_id[session_id] = company_id
        self._touch(session_id)

    # ----- Pending handoff (chat escalation missing tenant) -----

    def get_pending_handoff_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        self.cleanup_expired()
        if session_id in self._sessions:
            self._touch(session_id)
        return self._pending_handoff_summary.get(session_id)

    def set_pending_handoff_summary(self, session_id: str, summary: Dict[str, Any]) -> None:
        self.cleanup_expired()
        self._pending_handoff_summary[session_id] = summary
        self._touch(session_id)

    def clear_pending_handoff(self, session_id: str) -> None:
        self.cleanup_expired()
        self._pending_handoff_summary.pop(session_id, None)
        if session_id in self._sessions:
            self._touch(session_id)

    # ----- VPN context -----

    def get_vpn_context(self, session_id: str) -> VpnContext:
        self.cleanup_expired()
        if session_id in self._sessions:
            self._touch(session_id)
        return self._vpn_context.get(session_id, VpnContext())

    def set_vpn_context(self, session_id: str, ctx: VpnContext) -> None:
        self.cleanup_expired()
        self._vpn_context[session_id] = ctx
        self._touch(session_id)

    def clear_vpn_context(self, session_id: str) -> None:
        self.cleanup_expired()
        self._vpn_context.pop(session_id, None)
        if session_id in self._sessions:
            self._touch(session_id)

    # ---------- Email idempotency + receipts (Mode A / Option B) ----------

    def is_email_processed(self, message_id: str) -> bool:
        self.cleanup_expired()
        mid = self._norm_message_id(message_id)
        if not mid:
            return False
        return mid in self._processed_emails

    def mark_email_processed(self, message_id: str) -> None:
        self.cleanup_expired()
        mid = self._norm_message_id(message_id)
        if not mid:
            return
        self._processed_emails[mid] = self._now()

    def get_email_receipt(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Return stored receipt dict (response payload) for a processed email message_id.
        Used to return deterministic information on duplicates.
        """
        self.cleanup_expired()
        mid = self._norm_message_id(message_id)
        if not mid:
            return None
        obj = self._email_receipts.get(mid)
        if not isinstance(obj, dict):
            return None
        receipt = obj.get("receipt")
        return receipt if isinstance(receipt, dict) else None

    def set_email_receipt(self, message_id: str, receipt: Dict[str, Any]) -> None:
        """
        Store receipt dict (response payload) for a processed email message_id.
        """
        self.cleanup_expired()
        mid = self._norm_message_id(message_id)
        if not mid:
            return
        if not isinstance(receipt, dict):
            return
        self._email_receipts[mid] = {"ts": self._now(), "receipt": receipt}

    # ---------- Email pending storage (Mode B) ----------

    def get_pending_email(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Return stored pending email payload for message_id, if exists.
        Payload is meant to be used by /email/resolve.
        """
        self.cleanup_expired()
        mid = self._norm_message_id(message_id)
        if not mid:
            return None

        obj = self._pending_emails.get(mid)
        if not isinstance(obj, dict):
            return None
        payload = obj.get("payload")
        return payload if isinstance(payload, dict) else None

    def set_pending_email(self, message_id: str, payload: Dict[str, Any]) -> None:
        """
        Store pending email payload when tenant is missing (pending_tenant).
        """
        self.cleanup_expired()
        mid = self._norm_message_id(message_id)
        if not mid:
            return
        if not isinstance(payload, dict):
            return
        self._pending_emails[mid] = {"ts": self._now(), "payload": payload}

    def clear_pending_email(self, message_id: str) -> None:
        """
        Remove pending email payload after successful resolve or manual cleanup.
        """
        self.cleanup_expired()
        mid = self._norm_message_id(message_id)
        if not mid:
            return
        self._pending_emails.pop(mid, None)

    def list_pending_emails(self) -> List[str]:
        """
        Mode B helper:
        Return a stable list of all message_ids currently stored as pending.
        """
        self.cleanup_expired()
        # Sorted for stable output (nice for UI/debugging)
        return sorted(self._pending_emails.keys())

    # ---------- Deletion ----------

    def delete_session(self, session_id: str) -> bool:
        self.cleanup_expired()
        existed = session_id in self._sessions
        self._sessions.pop(session_id, None)
        self._last_intent.pop(session_id, None)
        self._vpn_context.pop(session_id, None)
        self._company_id.pop(session_id, None)
        self._pending_handoff_summary.pop(session_id, None)
        self._last_seen.pop(session_id, None)
        return existed
