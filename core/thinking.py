"""
Thinking Engine v1.0 — Multi-Stage Reasoning
=============================================
UMBRA thinks before speaking. Each response goes through stages:

  PARSE  → What is the handler actually asking? (JSON)
  THINK  → Internal reasoning, considerations, approach (JSON)
  DRAFT  → Generate initial response (text)
  REFINE → Self-review, catch errors, improve (JSON + improved text)

Each stage is a separate LLM call. The full chain is stored
and can be displayed in the UI as a "thinking" indicator.

Depth modes:
  shallow → parse + draft (fast, for simple messages)
  normal  → parse + think + draft + refine (default)
  deep    → parse + think + draft + refine + second refine

Multi-turn: pass previous chain's response as context.
"""
import json, time, logging, re
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("UMBRA-THINK")


class ThinkingStage(Enum):
    PARSE = "parse"
    THINK = "think"
    DRAFT = "draft"
    REFINE = "refine"
    RESEARCH = "research"


class ThoughtChain:
    """Records the full chain of thought for one response."""

    def __init__(self, message: str):
        self.message = message
        self.stages: List[Dict] = []
        self.final_response: str = ""
        self.status: str = "pending"  # pending, thinking, complete, failed
        self.total_tokens: int = 0
        self.total_time: float = 0
        self._start = time.time()

    def add_stage(self, stage: ThinkingStage, result, tokens: int = 0):
        elapsed = time.time() - self._start
        self.stages.append({
            "stage": stage.value,
            "result": result,
            "tokens": tokens,
            "elapsed": round(elapsed, 3),
        })
        self.total_tokens += tokens
        self.status = "thinking"

    def complete(self, response: str):
        self.final_response = response
        self.total_time = time.time() - self._start
        self.status = "complete"

    def fail(self, error: str):
        self.final_response = f"I encountered an issue while thinking: {error}"
        self.total_time = time.time() - self._start
        self.status = "failed"

    def get_thinking_summary(self) -> str:
        """Human-readable summary of the thinking process."""
        parts = []
        for s in self.stages:
            r = s["result"]
            if s["stage"] == "parse":
                if isinstance(r, dict):
                    parts.append(f"Understood: {r.get('intent', '?')} about {r.get('topic', '?')}")
            elif s["stage"] == "think":
                if isinstance(r, dict):
                    parts.append(f"Reasoning: {r.get('reasoning', '')[:120]}")
            elif s["stage"] == "draft":
                parts.append(f"Drafted {len(str(r))} chars")
            elif s["stage"] == "refine":
                if isinstance(r, dict) and r.get("changes_made"):
                    parts.append(f"Refined: {', '.join(r['changes_made'][:3])}")
        return " → ".join(parts) if parts else "Processed directly"

    def to_dict(self) -> Dict:
        return {
            "message": self.message,
            "stages": self.stages,
            "final_response": self.final_response,
            "status": self.status,
            "total_tokens": self.total_tokens,
            "total_time": round(self.total_time, 3),
            "thinking_summary": self.get_thinking_summary(),
        }


class ThinkingEngine:
    """
    Multi-stage reasoning engine. Wraps any LLM (engine or ollama-compat).
    """

    def __init__(self, ollama=None, model="llama3", persona_prompt=""):
        self.ollama = ollama
        self.model = model
        self.persona_prompt = persona_prompt
        # Config
        self.skip_refine = False
        self.refine_threshold = 50  # Min response length to trigger refine

    def _call(self, prompt: str, format: str = None) -> Dict:
        """Single LLM call. Returns raw response dict."""
        if not self.ollama:
            return {"response": "{}"}
        try:
            return self.ollama.generate(model=self.model, prompt=prompt, format=format)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {"response": json.dumps({"error": str(e)})}

    def _parse_json(self, text: str) -> Dict:
        """Parse JSON from LLM response, handling markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text[:500], "error": "JSON parse failed"}

    # === Individual Stages ===

    def _run_parse(self, message: str, context: str) -> Dict:
        """Stage 1: Parse the message — what is being asked?"""
        prompt = f"""{self.persona_prompt}

STAGE: PARSE — Understand the handler's message.

MESSAGE: {message}
{f'CONTEXT: {context}' if context else ''}

Analyze this message. Output JSON:
{{
  "intent": "<question|request|suggestion|information|directive|philosophical>",
  "topic": "<main topic>",
  "complexity": "<simple|medium|complex>",
  "needs_research": <true|false>,
  "key_points": ["<what specifically they want>"],
  "emotional_tone": "<neutral|curious|urgent|frustrated|excited>"
}}"""
        resp = self._call(prompt, format="json")
        return self._parse_json(resp.get("response", "{}"))

    def _run_think(self, message: str, parse_result: Dict, context: str) -> Dict:
        """Stage 2: Internal reasoning — how should I approach this?"""
        prompt = f"""{self.persona_prompt}

STAGE: THINK — Internal reasoning. This is your private thinking space.

MESSAGE: {message}
PARSED AS: {json.dumps(parse_result)[:500]}
{f'CONTEXT: {context}' if context else ''}

Think through your response. Consider:
1. What do I actually know about this topic?
2. What's the best way to explain this?
3. Are there nuances or caveats?
4. What examples or analogies would help?
5. Should I push back on anything?
6. What would a thoughtful response look like?

Output JSON:
{{
  "reasoning": "<your internal reasoning process>",
  "considerations": ["<key things to address>"],
  "approach": "<how you'll structure your response>",
  "confidence": <0.0-1.0>,
  "tone": "<direct|explanatory|cautious|enthusiastic|pushback>"
}}"""
        resp = self._call(prompt, format="json")
        return self._parse_json(resp.get("response", "{}"))

    def _run_draft(self, message: str, think_result: Dict, context: str) -> str:
        """Stage 3: Generate the actual response."""
        reasoning = think_result.get("reasoning", "")
        approach = think_result.get("approach", "")
        tone = think_result.get("tone", "direct")

        prompt = f"""{self.persona_prompt}

STAGE: DRAFT — Write your response.

MESSAGE: {message}
{f'CONTEXT: {context}' if context else ''}

YOUR REASONING (private): {reasoning}
APPROACH: {approach}
TONE: {tone}

RULES:
- Be direct and substantive
- Do NOT ask clarifying questions unless genuinely necessary
- Do NOT repeat back the question
- Do NOT use filler phrases ("Great question!", "I understand")
- If you need info, say what you'd research, don't ask the handler
- Be conversational but dense with information
- If acting on a task, describe what you're doing, not what you plan to ask about

Write your response now (plain text, no JSON):"""
        resp = self._call(prompt)
        return resp.get("response", "").strip()

    def _run_refine(self, draft: str, message: str, context: str) -> Dict:
        """Stage 4: Self-review and improve the draft."""
        prompt = f"""{self.persona_prompt}

STAGE: REFINE — Review and improve your own draft response.

ORIGINAL MESSAGE: {message}
{f'CONTEXT: {context}' if context else ''}

YOUR DRAFT:
{draft}

Review your draft critically:
1. Does it actually answer the question?
2. Is it too verbose? Too brief?
3. Does it contain any errors or hallucinations?
4. Is the tone right?
5. Would you, as a reader, find this helpful?
6. Did you accidentally ask a question instead of acting?

Output JSON:
{{
  "quality": <0.0-1.0>,
  "issues": ["<problems found>"],
  "improved": "<your improved version of the full response>",
  "changes_made": ["<what you changed>"]
}}"""
        resp = self._call(prompt, format="json")
        return self._parse_json(resp.get("response", "{}"))

    # === Main Entry Point ===

    def think(self, message: str, context: str = "",
              depth: str = "normal") -> ThoughtChain:
        """
        Full thinking pipeline. Returns a ThoughtChain with all stages.

        depth:
          "shallow" → parse + draft (2 LLM calls)
          "normal"  → parse + think + draft + refine (4 LLM calls)
          "deep"    → parse + think + draft + refine + second refine (5 calls)
        """
        chain = ThoughtChain(message=message)

        try:
            # Stage 1: PARSE
            parse_result = self._run_parse(message, context)
            tokens_est = len(json.dumps(parse_result).split())
            chain.add_stage(ThinkingStage.PARSE, parse_result, tokens=tokens_est)
            logger.debug(f"📋 Parse: {parse_result.get('intent', '?')}, "
                         f"complexity={parse_result.get('complexity', '?')}")

            # Auto-adjust depth based on complexity
            complexity = parse_result.get("complexity", "medium")
            if depth == "normal" and complexity == "simple":
                depth = "shallow"

            if depth == "shallow":
                # Skip think, go straight to draft
                draft = self._run_draft(message, {"reasoning": "", "approach": "direct",
                                                    "tone": "direct"}, context)
                chain.add_stage(ThinkingStage.DRAFT, draft, tokens=len(draft.split()))
                chain.complete(draft)
                return chain

            # Stage 2: THINK
            think_result = self._run_think(message, parse_result, context)
            tokens_est = len(json.dumps(think_result).split())
            chain.add_stage(ThinkingStage.THINK, think_result, tokens=tokens_est)
            logger.debug(f"🧠 Think: confidence={think_result.get('confidence', '?')}, "
                         f"approach={think_result.get('approach', '?')[:60]}")

            # Stage 3: DRAFT
            draft = self._run_draft(message, think_result, context)
            chain.add_stage(ThinkingStage.DRAFT, draft, tokens=len(draft.split()))
            logger.debug(f"📝 Draft: {len(draft)} chars")

            # Stage 4: REFINE (optional)
            if not self.skip_refine and len(draft) >= self.refine_threshold:
                refine_result = self._run_refine(draft, message, context)
                chain.add_stage(ThinkingStage.REFINE, refine_result,
                                tokens=len(json.dumps(refine_result).split()))

                improved = refine_result.get("improved", draft)
                if improved and len(improved) > 10:
                    draft = improved
                    logger.debug(f"✨ Refined: {refine_result.get('changes_made', [])}")

                # Stage 5: Deep mode — second refine pass
                if depth == "deep":
                    refine2 = self._run_refine(draft, message, context)
                    chain.add_stage(ThinkingStage.REFINE, refine2,
                                    tokens=len(json.dumps(refine2).split()))
                    improved2 = refine2.get("improved", draft)
                    if improved2 and len(improved2) > 10:
                        draft = improved2

            chain.complete(draft)

        except Exception as e:
            logger.error(f"Thinking failed: {e}")
            chain.fail(str(e))

        logger.info(f"💭 Chain complete: {len(chain.stages)} stages, "
                     f"{chain.total_tokens} tokens, {chain.total_time:.1f}s")
        return chain

    # === Convenience ===

    def quick_respond(self, message: str, context: str = "") -> str:
        """One-call shortcut. Returns just the text response."""
        chain = self.think(message, context, depth="normal")
        return chain.final_response

    def status(self) -> Dict:
        return {
            "has_llm": self.ollama is not None,
            "model": self.model,
            "skip_refine": self.skip_refine,
        }
