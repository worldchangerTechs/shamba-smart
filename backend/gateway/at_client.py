"""USSD response helpers and optional Africa's Talking voice support."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import africastalking  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _sdk() -> "africastalking":
    import africastalking as _at  # type: ignore[import-untyped]

    _at.initialize(
        os.environ.get("AT_USERNAME", "sandbox"),
        os.environ.get("AT_API_KEY", ""),
    )
    return _at


def ussd_continue(text: str) -> str:
    return f"CON {text}"


def ussd_end(text: str) -> str:
    return f"END {text}"


def make_call(to: str, *, call_from: str | None = None, audio_url: str) -> dict:
    caller = call_from or os.environ.get("AT_VOICE_FROM", "+254711082300")
    normalized_to = to if to.startswith("+") else f"+{to.lstrip('+')}"
    try:
        return _sdk().Voice.call(caller, normalized_to)
    except Exception:
        logger.exception("Africa's Talking voice call failed.")
        return {"error": "call_failed"}


def voice_callback_xml(audio_url: str) -> str:
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Response>"
        f"<Play url='{audio_url}'/>"
        "</Response>"
    )
