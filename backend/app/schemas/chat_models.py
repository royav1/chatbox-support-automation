from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from enum import Enum

# ===== Intent types =====

Intent = Literal[
    "VPN_ISSUE",
    "PASSWORD_RESET",
    "EMAIL_ISSUE",
    "GENERAL",
    "UNKNOWN",
]

# ===== Chat request / response =====

class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(
        default=None,
        description="Client-provided session id"
    )
    message: str = Field(
        min_length=1,
        max_length=4000,
        description="User message"
    )

    company_id: Optional[str] = Field(
        default=None,
        description="Optional tenant/company identifier (e.g. bank_demo, auto_demo)"
    )

class ChatResponse(BaseModel):
    session_id: str
    intent: Intent
    confidence: float
    reply: str
    handoff: bool = False
    handoff_summary: Optional[Dict[str, Any]] = None
    jira_payload_preview: Optional[Dict[str, Any]] = None

# ===== Session history models =====

Role = Literal["user", "assistant"]

class MessageItem(BaseModel):
    role: Role
    message: str

class SessionHistoryResponse(BaseModel):
    session_id: str
    last_intent: Optional[Intent] = None
    messages: List[MessageItem]
    message_count: int

# ===== VPN flow models (Part 2 / Step 4.1) =====

class VpnState(str, Enum):
    VPN_START = "VPN_START"
    VPN_ASK_OS = "VPN_ASK_OS"
    VPN_ASK_CLIENT = "VPN_ASK_CLIENT"
    VPN_ASK_SYMPTOM = "VPN_ASK_SYMPTOM"
    VPN_ASK_ERROR_CODE = "VPN_ASK_ERROR_CODE"
    VPN_GIVE_STEPS = "VPN_GIVE_STEPS"
    VPN_CHECK_RESULT = "VPN_CHECK_RESULT"
    VPN_HANDOFF = "VPN_HANDOFF"

class VpnOS(str, Enum):
    WINDOWS = "windows"
    MAC = "mac"
    LINUX = "linux"
    OTHER = "other"

class VpnSymptom(str, Enum):
    CANNOT_CONNECT = "cannot_connect"
    CONNECTS_NO_ACCESS = "connects_no_access"
    DISCONNECTS = "disconnects"
    OTHER = "other"

class VpnContext(BaseModel):
    state: VpnState = VpnState.VPN_START

    os: Optional[VpnOS] = None
    client: Optional[str] = None
    symptom: Optional[VpnSymptom] = None
    error_code: Optional[str] = None

    steps_given: List[str] = Field(default_factory=list)
    attempt_count: int = 0

    # Helps avoid repeating the same question
    last_question: Optional[str] = None
