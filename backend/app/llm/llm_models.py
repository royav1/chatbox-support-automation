from __future__ import annotations

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.schemas.chat_models import Intent


class LlmClassificationResult(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0)
    reason: Optional[str] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    internal_tags: List[str] = Field(default_factory=list)