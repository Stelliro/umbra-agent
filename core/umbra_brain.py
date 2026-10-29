"""
UMBRA Brain v1.0 — Switch + GGUF Orchestrator
==============================================
The Brain wires the external Switch CPU (`core/umbra_switch.py`) into
the GGUF inference engine (`core/umbra_engine.py`).

Flow per `chat(message)`:
    1. Route the message through the Switch DB.
    2. If a high-confidence 'response' switch matches, return it directly
       (CPU-only mode — no GGUF call). This is the seed of "the app IS
       the model": as the switch DB grows, more answers come from pure
       Python without invoking the GGUF.
    3. Otherwise, prepend the switch context block to the system prompt
       and call the GGUF engine. The static GGUF gets shaped by the
       editable external "weights".
    4. Optionally record reinforcement based on caller feedback.

The Brain itself is intentionally thin. Engine and Switch each remain
independently usable. The Brain accepts any object exposing a
`chat(model, messages, **kw) -> {"message": {"content": str}}` method
(matches `UmbraEngine` / `OllamaCompat`), or `None` for pure-CPU mode.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .umbra_switch import RouteResult, UmbraSwitch, get_default_switch

logger = logging.getLogger("UMBRA-BRAIN")


class _ChatBackend(Protocol):
    def chat(self, model: str, messages: List[Dict[str, str]], **kw: Any) -> Dict[str, Any]: ...


@dataclass
class BrainResponse:
    text: str
    source: str  # "switch" | "gguf" | "fallback"
    matched_switches: List[str] = field(default_factory=list)
    direct_switch_id: Optional[str] = None
    model: Optional[str] = None


class UmbraBrain:
    """Switch-augmented inference orchestrator."""

    DEFAULT_SYSTEM = (
        "You are UMBRA. Use the Switch Context below as authoritative "
        "supplemental knowledge when relevant. Do not contradict locked "
        "switches without an explicit instruction to do so."
    )

    def __init__(
        self,
        engine: Optional[_ChatBackend] = None,
        switch: Optional[UmbraSwitch] = None,
        *,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        teach_on_gguf: bool = False,
    ) -> None:
        self.engine = engine
        self.switch = switch or get_default_switch()
        self.model = model
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM
        self.teach_on_gguf = bool(teach_on_gguf)

    # -- core ---------------------------------------------------------------

    def route(self, message: str) -> RouteResult:
        return self.switch.route(message)

    def chat(
        self,
        message: str,
        *,
        history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        force_gguf: bool = False,
        **engine_kw: Any,
    ) -> BrainResponse:
        if not message or not message.strip():
            return BrainResponse(text="", source="fallback")

        decision = self.switch.route(message)
        matched_ids = decision.ids()

        # 1) Direct CPU answer from switch DB
        if decision.has_direct and not force_gguf:
            logger.debug("Brain: direct switch answer (%s)", decision.direct_switch_id)
            return BrainResponse(
                text=decision.direct_answer or "",
                source="switch",
                matched_switches=matched_ids,
                direct_switch_id=decision.direct_switch_id,
            )

        # 2) GGUF path with switch-augmented system prompt
        if self.engine is None:
            # No backend wired — degrade gracefully. Return the highest
            # ranked switch content if anything matched, else empty.
            if decision.matched:
                top_sw, _ = decision.matched[0]
                return BrainResponse(
                    text=top_sw.content,
                    source="switch",
                    matched_switches=matched_ids,
                    direct_switch_id=top_sw.id,
                )
            return BrainResponse(text="", source="fallback")

        sys_text = self.system_prompt
        if decision.context_block:
            sys_text = f"{self.system_prompt}\n\n{decision.context_block}"

        messages: List[Dict[str, str]] = [{"role": "system", "content": sys_text}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        result = self.engine.chat(model=model or self.model, messages=messages, **engine_kw)
        text = ""
        try:
            text = result["message"]["content"]
        except (KeyError, TypeError):
            text = str(result) if result is not None else ""

        # 3) Optional auto-teach: store this as a low-weight response switch
        if self.teach_on_gguf and text:
            try:
                self.switch.teach_response(message, text, weight=1.0)
            except Exception as exc:  # pragma: no cover - learning never breaks chat
                logger.warning("Brain: teach_response failed: %s", exc)

        return BrainResponse(
            text=text,
            source="gguf",
            matched_switches=matched_ids,
            model=(model or self.model),
        )

    # -- feedback -----------------------------------------------------------

    def reinforce(self, response: BrainResponse, signal: float = 1.0) -> None:
        """Apply positive/negative reinforcement to switches used in `response`."""
        ids = list(response.matched_switches)
        if response.direct_switch_id and response.direct_switch_id not in ids:
            ids.append(response.direct_switch_id)
        if ids:
            self.switch.apply_feedback(ids, signal)

    # -- introspection ------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        return {
            "switch": self.switch.stats(),
            "model": self.model,
            "engine": type(self.engine).__name__ if self.engine else None,
        }


__all__ = ["UmbraBrain", "BrainResponse"]
