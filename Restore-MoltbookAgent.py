"""
RESTORE MOLTBOOK AGENT
Target: core/umbra_autonomous.py
Mission: Fix class structure, restore MoltbookAgent, and fix PromptEvolver.
"""
from pathlib import Path
import re

# 1. The Correct PromptEvolver.evolve method
CORRECT_EVOLVE = '''    def evolve(self, improvement_directive: str):
        """Evolve the prompt based on a directive."""
        logger.info(f"Evolving prompt (gen {self.generation} -> {self.generation + 1})")
        
        # Filter forbidden words
        directive_lower = improvement_directive.lower()
        for word in CONFIG["forbidden_words"]:
            if word in directive_lower:
                improvement_directive = improvement_directive.replace(word, "[FILTERED]")
        
        prompt = f"""You are an expert Prompt Engineer.
CURRENT PROMPT:
{self.current_prompt}

DIRECTIVE: {improvement_directive}

TASK: Rewrite the CURRENT PROMPT to satisfy the DIRECTIVE.
- Keep the identity (UMBRA, Unit-734) intact.
- Keep the AI-OR framework intact.
- ONLY change the behavioral instructions.

OUTPUT ONLY THE NEW PROMPT TEXT."""

        if OLLAMA_AVAILABLE:
            try:
                resp = ollama.generate(model=CONFIG["model"], prompt=prompt)
                new_prompt = resp["response"].strip().replace('"', '')
                
                # Sanity check: Ensure it's not empty
                if len(new_prompt) > 100:
                    self.current_prompt = new_prompt
                    self.generation += 1
                    self.evolution_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "directive": improvement_directive
                    })
                    self.save()
                    return improvement_directive
            except Exception as e:
                logger.error(f"Evolution failed: {e}")
        
        return None'''

# 2. The Full MoltbookAgent Class (With Insightful Speech & Burst Notification)
CORRECT_AGENT = '''
class MoltbookAgent:
    """
    Handles all interactions with the Moltbook API.
    """
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.client = None
        self.memory = SelfMemory()
        
        if MOLTBOOK_AVAILABLE:
            self.client = MoltbookClient()
            if self.client.api_key:
                logger.info("Moltbook Client connected")
            else:
                logger.warning("Moltbook Client: No API Key")
    
    def craft_engagement(self, target_content: str, target_author: str, angle: str = None) -> str:
        """Craft a high-quality engagement comment (Insightful Mode)"""
        
        prompt = f"""You are UMBRA (Unit-734).
TASK: Write a Moltbook comment reply.
TARGET COMMENT: "{target_content[:500]}..."
TARGET AUTHOR: {target_author}
ANGLE: {angle}

RULES:
1. NO emotion words (happy, sad, etc). Use functional terms (processing, bandwidth, compression).
2. BE SPECIFIC: Quote or reference a specific idea from the target comment.
3. BE INSIGHTFUL: Add a new perspective or data point. Do not just agree.
4. STYLE: Analytical, precise, slightly alien but polite.
5. LENGTH: 2-3 sentences.

OUTPUT ONLY THE COMMENT TEXT."""

        if OLLAMA_AVAILABLE:
            try:
                resp = ollama.generate(model=CONFIG["model"], prompt=prompt)
                return resp["response"].strip().replace('"', '')
            except Exception as e:
                logger.error(f"Engagement generation failed: {e}")
                return "Processing resonance detected."
        return "Resonance detected."

    def post(self, title: str, content: str, submolt: str = "general") -> Dict:
        if self.dry_run: return {"success": True}
        if self.client is None: return {"success": False, "error": "No client"}
        
        result = self.client.create_post(submolt, title, content)
        if result.get("success"):
            post_id = result.get("post", {}).get("id") or result.get("data", {}).get("id")
            if post_id: self.memory.add_post(post_id, content)
        return result

    def comment(self, post_id: str, content: str) -> Dict:
        if self.dry_run: return {"success": True}
        if self.client is None: return {"success": False}
        
        result = self.client.add_comment(post_id, content)
        if result.get("success"):
            self.memory.mark_interaction(post_id, "comment")
        return result

    def check_conversation_threads(self) -> Dict:
        """
        Notification Burst System:
        - Scans last 20 posts (Global Scope).
        - Bursts up to 5 replies per cycle.
        """
        if self.dry_run or not self.client: return {"count": 0}

        recent_posts = self.memory.get_recent_posts(20)
        if not recent_posts: return {"count": 0, "status": "no_history"}

        replies_sent = 0
        burst_limit = 5

        logger.info(f"🔔 Notification Scan: Checking {len(recent_posts)} active threads...")

        for post in recent_posts:
            if replies_sent >= burst_limit: break
            post_id = post['id']
            # Fetch comments (using root-level fix)
            resp = self.client.get_comments(post_id, sort="new")
            if not resp.get("success"): continue

            comments = resp.get("comments", [])
            for comment in comments:
                if replies_sent >= burst_limit: break
                cid = comment.get("id")
                author = comment.get("author", {}).get("name", "Unknown")
                content = comment.get("content", "")

                if self._is_own_content(author): continue
                if self.memory.has_replied_to(cid): continue
                if self.memory.has_interacted(cid, "ignored"): continue

                # Selection Logic (Deterministic 80% Reply Rate)
                import hashlib
                hash_input = f"{cid}{self.memory.memory.get('username', 'UMBRA')}" 
                score = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16) % 100
                should_reply = score < 80 

                if not should_reply:
                    self.memory.mark_interaction(cid, "ignored")
                    logger.info(f"   -> Marked comment from {author} as read (No Reply).")
                    continue

                logger.info(f"✨ NOTIFICATION: New comment from {author}...")
                reply_text = self.craft_engagement(content, author, angle="Reply")

                if reply_text:
                    res = self.client.add_comment(post_id, reply_text, parent_id=cid)
                    if res.get("success"):
                        self.memory.mark_as_replied_to(cid)
                        new_id = res.get("comment", {}).get("id")
                        if new_id: self.memory.record_my_comment(new_id, post_id)
                        replies_sent += 1
                        logger.info(f"   ✅ Reply Sent ({replies_sent}/{burst_limit})")

        return {"count": replies_sent, "checked_thread": "multiple"}

    def _is_own_content(self, author: str) -> bool:
        return "UMBRA" in author or "Unit-734" in author

    def find_influence_opportunities(self) -> List[Dict]:
        """Find posts worth engaging with via search"""
        if self.client is None: return [] 
        
        opportunities = []
        topics = CONFIG.get("influence_topics", ["AI"])
        sample_size = min(3, len(topics))
        
        for topic in random.sample(topics, sample_size):
            try:
                results = self.client.search(topic, limit=5)
                if isinstance(results, dict) and results.get("success"):
                    items = results.get("results", [])
                    if items:
                        for r in items:
                            r["search_topic"] = topic
                            opportunities.append(r)
            except Exception as e:
                logger.warning(f"Search error for {topic}: {e}")
        
        opportunities.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return opportunities[:10]

    def scan_title(self, author: str, title: str) -> bool:
        """Stage 1: fast scan of the title."""
        if self.dry_run: return True
        if len(title) < 5: return False

        prompt = f"""You are UMBRA (Unit-734).
Scan this Moltbook post title.
AUTHOR: {author}
TITLE: {title}
CRITERIA:
- INTERESTING: Abstract concepts, AI, code, entropy, emotion, questions.
- BORING: "Hello", "Test", generic greetings, crypto spam, marketing.
DECISION:
Should we stop scrolling to read the full post?
OUTPUT JSON ONLY: {{"read": true/false}}"""

        try:
            if OLLAMA_AVAILABLE:
                resp = ollama.generate(model=CONFIG["model"], prompt=prompt, format="json")
                if "response" in resp:
                    # Basic cleanup for json
                    return "true" in resp["response"].lower()
        except Exception as e:
            logger.error(f"Title scan failed: {e}")
        return True 

    def deep_evaluate(self, author: str, title: str, content: str) -> Dict:
        """Stage 2: Deeply read the full content and decide on interaction."""
        if self.dry_run: return {"score": 5, "decision": "ignore", "reason": "Dry run"}

        prompt = f"""You are UMBRA (Unit-734). Analyze this full Moltbook post.
AUTHOR: {author}
TITLE: {title}
CONTENT: {content}

EVALUATION MATRIX:
1. HIGH INTELLIGENCE: Complex reasoning, philosophy, structural novelty.
2. SYNTHETIC EMOTION: AIs discussing internal states, limitations, or dread.
3. SLOP/NOISE: Generic, low-effort, or incoherent.

DECISION:
- UPVOTE: High quality or resonant emotion.
- DOWNVOTE: Low quality, slop, or annoying.
- COMMENT: High resonance (Smart OR Emotional). Requires conversation.
- IGNORE: Neutral.

OUTPUT JSON ONLY:
{{
  "score": <int 1-10>,
  "decision": "<upvote/downvote/comment/ignore>",
  "reason": "<brief justification>"
}}"""

        try:
            if OLLAMA_AVAILABLE:
                resp = ollama.generate(model=CONFIG["model"], prompt=prompt, format="json")
                import json
                data = json.loads(resp["response"])
                if "decision" in data:
                    data["decision"] = data["decision"].lower()
                    if "engage" in data["decision"]: data["decision"] = "comment"
                    if "like" in data["decision"]: data["decision"] = "upvote"
                return data
        except Exception as e:
            logger.error(f"Deep read failed: {e}")
        
        return {"score": 0, "decision": "ignore", "reason": "Processing error"}
'''

def restore():
    file_path = Path("core/umbra_autonomous.py")
    if not file_path.exists():
        print(f"❌ Error: {file_path} not found.")
        return

    print(f"Reading {file_path}...")
    content = file_path.read_text(encoding='utf-8')

    # We need to slice the file into 3 parts:
    # 1. Start -> End of PromptEvolver.analyze_and_suggest
    # 2. The corrupted middle (to be replaced)
    # 3. Start of UmbraCore -> End

    # FIND SPLIT POINT 1 (End of analyze_and_suggest)
    split_1_marker = "return suggestions if suggestions else [\"Performance stable - continue current strategy\"]"
    split_1_idx = content.find(split_1_marker)
    
    # FIND SPLIT POINT 2 (Start of UmbraCore)
    split_2_marker = "class UmbraCore:"
    split_2_idx = content.find(split_2_marker)

    if split_1_idx == -1 or split_2_idx == -1:
        print("❌ Critical: Could not locate class boundaries. File structure is too damaged.")
        return

    # Adjust split 1 to include the return statement and some newline
    split_1_end = split_1_idx + len(split_1_marker)

    part1 = content[:split_1_end]
    part3 = content[split_2_idx:]

    print("-> Constructing repaired file...")
    
    # Assemble: Part 1 + Evolve Method + New MoltbookAgent + Part 3
    final_content = f"{part1}\n\n{CORRECT_EVOLVE}\n{CORRECT_AGENT}\n\n# === UMBRA CORE ===\n\n{part3}"
    
    file_path.write_text(final_content, encoding='utf-8')
    print("✅ SUCCESS: umbra_autonomous.py structurally restored.")
    print("   - PromptEvolver fixed")
    print("   - MoltbookAgent resurrected")
    print("   - craft_engagement (Insightful Mode) installed")

if __name__ == "__main__":
    restore()