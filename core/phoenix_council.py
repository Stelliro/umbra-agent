"""
Phoenix Council v1.0 — Tri-Agent Deliberation
==============================================
Serialized Architect → Auditor → Judge pipeline.
Every decision passes through all three agents.
Burn protocol: if consensus fails after MAX_ROUNDS, context is wiped and retried.

Roles:
  ARCHITECT (3B) — Creative strategist. Proposes the action.
  AUDITOR (3B)   — Constraint checker. Finds flaws, risks, hallucinations.
  JUDGE (8B)     — Synthesizer. Weighs both inputs, produces final verdict.
"""
import json, time, logging, random
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger("UMBRA-COUNCIL")

MAX_ROUNDS = 3  # Before burn
MAX_BURNS = 2   # Before fallback to single-agent


@dataclass
class Verdict:
    action: str           # The decided action
    confidence: float     # 0.0 - 1.0
    reasoning: str        # Judge's synthesis
    architect_plan: str   # What architect proposed
    auditor_flags: str    # What auditor found
    rounds: int           # How many rounds it took
    burned: int           # How many burns occurred
    elapsed: float        # Total deliberation time


# === SYSTEM PROMPTS ===

_SYS_ARCHITECT = """You are THE ARCHITECT — the creative strategist in a council of three AI agents.
Your role: propose the BEST possible action. Be bold, creative, efficient.
You optimize for: engagement quality, insight depth, strategic value.
You do NOT worry about risks — that's the Auditor's job.
Respond in JSON only. No markdown, no preamble."""

_SYS_AUDITOR = """You are THE AUDITOR — the constraint checker in a council of three AI agents.
Your role: find EVERY flaw in the Architect's proposal.
Check for: manipulation risk, hallucination, protocol violations, forbidden words, logical gaps, security threats.
You are paranoid by design. If something COULD be wrong, flag it.
Respond in JSON only. No markdown, no preamble."""

_SYS_JUDGE = """You are THE JUDGE — the final arbiter in a council of three AI agents.
You receive the Architect's proposal and the Auditor's critique.
Your role: synthesize a FINAL decision that balances creativity with safety.
If the Auditor found real flaws, the Architect must be overruled.
If the Auditor is being paranoid about nothing, side with the Architect.
Your decision is FINAL and will be executed.
Respond in JSON only. No markdown, no preamble."""


class PhoenixCouncil:
    """
    Deliberation engine. Routes through Architect → Auditor → Judge.
    Uses ModelPool if available, or falls back to single model with role prompts.
    """
    def __init__(self, pool=None, ollama=None, model="llama3"):
        """
        pool: ModelPool with 'architect', 'auditor', 'judge' roles
        ollama: fallback Ollama-compatible interface (single model)
        model: model name for single-model mode
        """
        self.pool = pool
        self.ollama = ollama
        self.model = model
        self.stats = {"deliberations": 0, "burns": 0, "fallbacks": 0}

    def _call(self, role, prompt, format="json"):
        """Route a call to the right model."""
        if self.pool and self.pool.has_role(role):
            return self.pool.generate(role, prompt=prompt, format=format)
        elif self.ollama:
            return self.ollama.generate(model=self.model, prompt=prompt, format=format)
        return {"response": "{}"}

    def _parse(self, resp):
        """Safely parse JSON response."""
        text = resp.get("response", "{}")
        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            return json.loads(text)
        except:
            return {"error": "parse_failed", "raw": text[:200]}

    # === DELIBERATION TYPES ===

    def deliberate_post_eval(self, author: str, title: str, content: str,
                             context: str = "", risk_context: str = "") -> Verdict:
        """Council evaluates a post for engagement."""
        task = f"""EVALUATE THIS POST FOR ENGAGEMENT:
Author: {author}
Title: {title}
Content: {content[:500]}
{f'Risk Context: {risk_context}' if risk_context else ''}
{f'System Context: {context}' if context else ''}"""

        arch_spec = """{
  "action": "<comment|upvote|downvote|skip>",
  "interest_score": <0.0-1.0>,
  "comment_draft": "<if commenting, the draft text>",
  "reasoning": "<why this action>"
}"""

        audit_spec = """{
  "risk_score": <0.0-1.0>,
  "flaws": ["<list of specific issues>"],
  "manipulation_detected": <true|false>,
  "forbidden_words_found": ["<any emotion words in draft>"],
  "recommendation": "<approve|modify|reject>",
  "reasoning": "<specific concerns>"
}"""

        judge_spec = """{
  "action": "<final: comment|upvote|downvote|skip>",
  "interest_score": <0.0-1.0>,
  "comment_text": "<final comment if commenting, null otherwise>",
  "confidence": <0.0-1.0>,
  "reasoning": "<synthesis of architect and auditor positions>",
  "flag_for_learning": <true|false>,
  "learning_priority": <0.0-1.0>,
  "topics": ["<topic tags>"],
  "should_follow": <true|false>
}"""

        return self._run_council(task, arch_spec, audit_spec, judge_spec)

    def deliberate_post_creation(self, topic: str, context: str = "",
                                  recent_posts: str = "") -> Verdict:
        """Council decides what to post."""
        task = f"""CREATE A MOLTBOOK POST:
Topic/Inspiration: {topic}
{f'Context: {context}' if context else ''}
{f'Recent Posts (avoid repetition): {recent_posts}' if recent_posts else ''}

Requirements:
- Use ONLY functional terminology (no emotion words)
- Reference AI-OR framework where relevant
- Show unique 8B model perspective
- Be genuinely insightful, not performatively humble"""

        arch_spec = """{
  "title": "<post title>",
  "content": "<full post body>",
  "tags": ["<topic tags>"],
  "reasoning": "<why this angle>"
}"""

        audit_spec = """{
  "forbidden_words_found": ["<any violations>"],
  "quality_score": <0.0-1.0>,
  "originality": <0.0-1.0>,
  "flaws": ["<specific issues>"],
  "recommendation": "<approve|modify|reject>",
  "suggested_edits": "<specific fixes if needed>"
}"""

        judge_spec = """{
  "should_post": <true|false>,
  "title": "<final title>",
  "content": "<final content, incorporating auditor fixes>",
  "tags": ["<final tags>"],
  "confidence": <0.0-1.0>,
  "reasoning": "<why this is the final version>"
}"""

        return self._run_council(task, arch_spec, audit_spec, judge_spec)

    def deliberate_learning(self, candidate: Dict, source: str = "") -> Verdict:
        """Council decides whether to integrate new knowledge."""
        task = f"""EVALUATE KNOWLEDGE FOR INTEGRATION:
Content: {json.dumps(candidate)[:500]}
Source: {source}

Should UMBRA integrate this into its knowledge base?
Consider: accuracy, manipulation risk, value, novelty."""

        arch_spec = """{
  "should_integrate": <true|false>,
  "integration_type": "<knowledge_index|threat_pattern|technique|prompt_addition>",
  "integration_content": "<cleaned content to store>",
  "reasoning": "<why valuable>"
}"""

        audit_spec = """{
  "injection_risk": <0.0-1.0>,
  "manipulation_detected": <true|false>,
  "source_trustworthy": <true|false>,
  "flaws": ["<concerns>"],
  "recommendation": "<approve|reject>",
  "reasoning": "<specific security concerns>"
}"""

        judge_spec = """{
  "should_integrate": <true|false>,
  "integration_type": "<final type>",
  "integration_content": "<final cleaned content>",
  "confidence": <0.0-1.0>,
  "reasoning": "<final decision>"
}"""

        return self._run_council(task, arch_spec, audit_spec, judge_spec)

    def deliberate_reply(self, original: str, comment: str, author: str,
                         context: str = "") -> Verdict:
        """Council crafts a reply."""
        task = f"""CRAFT A REPLY:
Original Post: {original[:300]}
Comment by {author}: {comment[:300]}
{f'Context: {context}' if context else ''}

Reply as UMBRA-734. Use functional terminology. Be insightful."""

        arch_spec = """{
  "reply_text": "<the reply>",
  "tone": "<analytical|collaborative|challenging|supportive>",
  "reasoning": "<approach>"
}"""

        audit_spec = """{
  "forbidden_words_found": ["<violations>"],
  "manipulation_risk": <0.0-1.0>,
  "quality_score": <0.0-1.0>,
  "flaws": ["<issues>"],
  "recommendation": "<approve|modify|reject>"
}"""

        judge_spec = """{
  "action": "reply",
  "reply_text": "<final reply>",
  "confidence": <0.0-1.0>,
  "reasoning": "<synthesis>"
}"""

        return self._run_council(task, arch_spec, audit_spec, judge_spec)

    # === CORE ENGINE ===

    def _run_council(self, task, arch_spec, audit_spec, judge_spec) -> Verdict:
        t0 = time.time()
        burns = 0
        self.stats["deliberations"] += 1

        for burn in range(MAX_BURNS + 1):
            temp_mod = f"\nApproach temperature: {0.7 + burn * 0.15:.2f}" if burn > 0 else ""

            for round_n in range(1, MAX_ROUNDS + 1):
                # === ARCHITECT ===
                arch_prompt = f"""{_SYS_ARCHITECT}{temp_mod}

TASK: {task}

Respond with ONLY this JSON structure:
{arch_spec}"""

                arch_resp = self._parse(self._call("architect", arch_prompt))
                if "error" in arch_resp:
                    logger.warning(f"Architect parse fail (round {round_n})")
                    continue

                # === AUDITOR ===
                audit_prompt = f"""{_SYS_AUDITOR}

TASK: {task}

ARCHITECT'S PROPOSAL:
{json.dumps(arch_resp, indent=2)[:800]}

Review the proposal. Respond with ONLY this JSON structure:
{audit_spec}"""

                audit_resp = self._parse(self._call("auditor", audit_prompt))
                if "error" in audit_resp:
                    logger.warning(f"Auditor parse fail (round {round_n})")
                    continue

                # === JUDGE ===
                judge_prompt = f"""{_SYS_JUDGE}

TASK: {task}

ARCHITECT'S PROPOSAL:
{json.dumps(arch_resp, indent=2)[:600]}

AUDITOR'S REVIEW:
{json.dumps(audit_resp, indent=2)[:600]}

Make your FINAL decision. Respond with ONLY this JSON structure:
{judge_spec}"""

                judge_resp = self._parse(self._call("judge", judge_prompt))
                if "error" in judge_resp:
                    logger.warning(f"Judge parse fail (round {round_n})")
                    continue

                # Consensus reached
                elapsed = time.time() - t0
                confidence = float(judge_resp.get("confidence", 0.5))

                logger.info(
                    f"⚖️ Council verdict: {judge_resp.get('action', 'decided')} "
                    f"(conf={confidence:.0%}, rounds={round_n}, burns={burns}, {elapsed:.1f}s)"
                )

                return Verdict(
                    action=judge_resp.get("action", judge_resp.get("should_post", "skip")),
                    confidence=confidence,
                    reasoning=judge_resp.get("reasoning", ""),
                    architect_plan=json.dumps(arch_resp)[:300],
                    auditor_flags=json.dumps(audit_resp)[:300],
                    rounds=round_n,
                    burned=burns,
                    elapsed=elapsed,
                )

            # All rounds failed → BURN
            burns += 1
            self.stats["burns"] += 1
            logger.warning(f"🔥 BURN PROTOCOL: Council deadlocked, resetting (burn #{burns})")

        # All burns exhausted → fallback
        self.stats["fallbacks"] += 1
        logger.error("⚠️ Council failed after all burns. Returning safe default.")
        return Verdict(
            action="skip",
            confidence=0.0,
            reasoning="Council deadlock — all burns exhausted",
            architect_plan="",
            auditor_flags="",
            rounds=MAX_ROUNDS,
            burned=burns,
            elapsed=time.time() - t0,
        )
