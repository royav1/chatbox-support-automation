from __future__ import annotations

import logging
import os
from typing import Optional

from app.llm.llm_models import LlmClassificationResult
from app.llm.mock_llm_client import mock_classify_email

logger = logging.getLogger("chatbox")


def is_llm_enabled() -> bool:
    return os.getenv("USE_LLM", "0") == "1"


def get_llm_min_confidence() -> float:
    raw = os.getenv("LLM_MIN_CONFIDENCE", "0.75")
    try:
        value = float(raw)
    except Exception:
        logger.info(f"email_llm_config_invalid key=LLM_MIN_CONFIDENCE value={raw} fallback=0.75")
        return 0.75

    if value < 0.0:
        logger.info(f"email_llm_config_clamped key=LLM_MIN_CONFIDENCE value={value} clamped=0.0")
        return 0.0

    if value > 1.0:
        logger.info(f"email_llm_config_clamped key=LLM_MIN_CONFIDENCE value={value} clamped=1.0")
        return 1.0

    return value


def classify_email_with_llm(text: str) -> Optional[LlmClassificationResult]:
    """
    Returns None when LLM is disabled, unavailable, unsupported,
    returns an empty result, errors, or returns below confidence threshold.

    Supported providers:
    - mock
    - openai
    """
    if not is_llm_enabled():
        logger.info("email_llm_disabled")
        return None

    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
    threshold = get_llm_min_confidence()

    try:
        result: Optional[LlmClassificationResult] = None

        if provider == "mock":
            result = mock_classify_email(text)

        elif provider == "openai":
            from app.llm.openai_llm_client import openai_classify_email

            result = openai_classify_email(text)

        else:
            logger.info(f"email_llm_provider_unsupported provider={provider}")
            return None

        if result is None:
            logger.info(f"email_llm_empty_result provider={provider}")
            return None

        if float(result.confidence) < threshold:
            logger.info(
                f"email_llm_rejected reason=low_confidence "
                f"provider={provider} intent={result.intent} "
                f"conf={float(result.confidence):.2f} threshold={threshold:.2f}"
            )
            return None

        logger.info(
            f"email_llm_accepted provider={provider} "
            f"intent={result.intent} conf={float(result.confidence):.2f} "
            f"threshold={threshold:.2f}"
        )

        return result

    except Exception as e:
        logger.info(f"email_llm_error provider={provider} err={type(e).__name__}")
        return None