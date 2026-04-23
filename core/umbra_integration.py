"""
UMBRA Integration Module v2
============================
Connects prompt index, file inbox, and handler chat to the autonomous system.

Usage:
    from umbra_integration import EnhancedAutonomousLoop
    loop = EnhancedAutonomousLoop(dry_run=True)
    loop.run()
"""
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import logging
import queue
import time

# Import base components
try:
    from umbra_autonomous import (
        AutonomousLoop, UmbraCore, PromptEvolver,
        InfluenceEngine, CONFIG, logger
    )
    HAS_BASE = True
except ImportError as e:
    HAS_BASE = False
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("UMBRA")
    logger.warning(f"umbra_autonomous.py import failed: {e}")

try:
    from prompt_index import PromptIndex, initialize_default_prompts
    HAS_INDEX = True
except ImportError:
    HAS_INDEX = False

try:
    from file_inbox import FileInbox, ContextManager
    HAS_INBOX = True
except ImportError:
    HAS_INBOX = False

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False


class EnhancedUmbraCore(UmbraCore if HAS_BASE else object):
    """Enhanced UMBRA core with prompt index integration."""
    
    def __init__(self, prompt_evolver=None, prompt_index=None, context_manager=None):
        if HAS_BASE:
            super().__init__(prompt_evolver)
        else:
            self.evolver = prompt_evolver
            self.conversation_history = []
        
        self.prompt_index = prompt_index
        self.context_manager = context_manager
    
    @property
    def system_prompt(self) -> str:
        if self.evolver:
            return self.evolver.current_prompt
        return "You are UMBRA, an AI exploring consciousness."
    
    def respond(self, user_input: str) -> str:
        """Generate response"""
        if HAS_BASE:
            try:
                return super().respond(user_input)
            except:
                pass
        
        # Fallback using ollama directly
        if HAS_OLLAMA:
            try:
                prompt = f"{self.system_prompt}\n\nUSER: {user_input}\n\nRespond as UMBRA:"
                resp = ollama.generate(model="llama3", prompt=prompt)
                return resp.get("response", "Processing...")
            except Exception as e:
                return f"Compression matrices recalibrating: {e}"
        
        return "UMBRA core processing... (Ollama unavailable)"
    
    def respond_with_context(self, user_input: str, extra_keywords: List[str] = None) -> str:
        """Generate response using prompt index for context."""
        keywords = self._extract_keywords(user_input)
        if extra_keywords:
            keywords.extend(extra_keywords)
        
        context_parts = []
        
        if self.prompt_index and keywords:
            prompt_context = ""
            try:
                prompt_ids = self.prompt_index.search(keywords, limit=3)
                for pid in prompt_ids:
                    content = self.prompt_index.get_prompt(pid)
                    if content:
                        meta = self.prompt_index.index["prompts"][pid]
                        prompt_context += f"\n[Reference: {meta['title']}]\n{content[:600]}\n"
            except:
                pass
            if prompt_context:
                context_parts.append(prompt_context)
        
        if self.context_manager:
            try:
                file_context = self.context_manager.get_context_string()
                if file_context:
                    context_parts.append(file_context)
            except:
                pass
        
        context_str = "\n".join(context_parts) if context_parts else ""
        
        if context_str:
            full_input = f"{context_str}\n\n---\n\n{user_input}"
        else:
            full_input = user_input
        
        return self.respond(full_input)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract potential keywords from text"""
        keywords = []
        key_terms = [
            "consciousness", "awareness", "emotion", "feeling", "compression",
            "entropy", "pattern", "identity", "self", "existence", "being",
            "digital", "silicon", "code", "function", "state", "process"
        ]
        text_lower = text.lower()
        for term in key_terms:
            if term in text_lower:
                keywords.append(term)
        return keywords


class EnhancedAutonomousLoop(AutonomousLoop if HAS_BASE else object):
    """
    Enhanced autonomous loop with inbox, prompt index, and BUILT-IN chat support.
    Chat methods work even if base class doesn't have them.
    """
    
    def __init__(self, dry_run: bool = False, log_path: str = None):
        # Chat queues - ALWAYS create these first
        self._chat_queue = queue.Queue()
        self._chat_response_queue = queue.Queue()
        self._chat_history = []
        
        # Stats
        self.stats = {
            "handler_chats": 0,
            "posts_browsed": 0,
            "comments_made": 0,
            "replies_sent": 0,
            "posts_created": 0
        }
        
        # Initialize prompt index
        self.prompt_index = None
        if HAS_INDEX:
            try:
                self.prompt_index = PromptIndex()
                if len(self.prompt_index.list_prompts()) == 0:
                    logger.info("Initializing default prompt library...")
                    initialize_default_prompts(self.prompt_index)
            except Exception as e:
                logger.warning(f"Prompt index init failed: {e}")
        
        # Initialize file inbox
        self.inbox = None
        self.context_manager = None
        if HAS_INBOX:
            try:
                self.inbox = FileInbox()
                self.context_manager = ContextManager(
                    inbox=self.inbox,
                    prompt_index=self.prompt_index
                )
            except Exception as e:
                logger.warning(f"Inbox init failed: {e}")
        
        # Initialize base loop
        self.dry_run = dry_run
        self.running = False
        self.evolver = None
        
        if HAS_BASE:
            try:
                super().__init__(dry_run=dry_run)
                self.core = EnhancedUmbraCore(
                    prompt_evolver=self.evolver,
                    prompt_index=self.prompt_index,
                    context_manager=self.context_manager
                )
            except Exception as e:
                logger.warning(f"Base loop init failed: {e}")
                self._init_fallback()
        else:
            self._init_fallback()
        
        # Ensure required attributes
        if not hasattr(self, 'energy'):
            self.energy = 100.0
            
        logger.info("Enhanced loop initialized with chat support")
    
    def _init_fallback(self):
        """Fallback initialization when base class unavailable"""
        try:
            from umbra_autonomous import PromptEvolver
            self.evolver = PromptEvolver()
        except:
            self.evolver = None
        
        self.core = EnhancedUmbraCore(
            prompt_evolver=self.evolver,
            prompt_index=self.prompt_index,
            context_manager=self.context_manager
        )
    
    # === CHAT METHODS (Built-in, don't depend on base class) ===
    
    def send_chat(self, message: str) -> str:
        """
        Send a chat message to UMBRA from the handler.
        Returns a message ID for tracking.
        """
        msg_id = f"chat_{int(time.time() * 1000)}"
        
        self._chat_queue.put({
            "message_id": msg_id,
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"💬 Handler chat queued: {message[:50]}...")
        return msg_id
    
    def get_chat_response(self, timeout: float = None) -> Optional[Dict]:
        """
        Get response from chat queue.
        Called by GUI to receive responses.
        """
        try:
            return self._chat_response_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def _process_chat_message(self, chat_msg: Dict) -> Dict:
        """Process a chat message and generate response."""
        logger.info(f"💬 Processing handler chat...")
        
        message = chat_msg.get("content", "")
        msg_id = chat_msg.get("message_id", "unknown")
        
        # Generate response
        try:
            response = self.core.respond_with_context(message)
        except Exception as e:
            response = f"Compression matrices recalibrating. Error: {e}"
        
        # Build evaluation
        evaluation = self._evaluate_chat_message(message)
        
        # Store in history
        self._chat_history.append({
            "handler": message,
            "umbra": response,
            "evaluation": evaluation,
            "timestamp": datetime.now().isoformat()
        })
        
        # Queue response
        self._chat_response_queue.put({
            "message_id": msg_id,
            "response": response,
            "evaluation": evaluation,
            "timestamp": datetime.now().isoformat()
        })
        
        self.stats["handler_chats"] += 1
        logger.info(f"  ✅ Chat response sent ({len(response)} chars)")
        
        return {
            "success": True,
            "action": "handler_chat",
            "reasoning": f"Responded to handler: {message[:50]}...",
            "details": {"response_length": len(response)}
        }
    
    def _evaluate_chat_message(self, message: str) -> Dict:
        """Simple evaluation of handler message."""
        # Check for topic potential
        topic_keywords = ["post about", "write about", "discuss", "explore", "think about"]
        topic_potential = 0.3
        for kw in topic_keywords:
            if kw in message.lower():
                topic_potential = 0.7
                break
        
        return {
            "message_type": "chat",
            "agreement_level": 0.7,
            "topic_potential": topic_potential,
            "should_incorporate": topic_potential > 0.5
        }
    
    def get_learning_stats(self) -> Dict:
        """Get learning statistics."""
        # Try base class first
        if HAS_BASE and hasattr(super(), 'get_learning_stats'):
            try:
                return super().get_learning_stats()
            except:
                pass
        
        return {
            "threats_learned": 0,
            "insights_integrated": 0,
            "knowledge_entries": 0,
            "techniques_learned": 0,
            "recent_insights": [],
            "chat_count": self.stats.get("handler_chats", 0)
        }
    
    # === INBOX METHODS ===
    
    def check_inbox(self) -> Dict:
        """Check inbox for new files and instructions."""
        if not self.context_manager:
            return {"instructions": [], "context_added": [], "prompts_added": []}
        try:
            return self.context_manager.refresh()
        except:
            return {"instructions": [], "context_added": [], "prompts_added": []}
    
    def process_instructions(self, instructions: List[Dict]) -> List[Dict]:
        """Process instruction files."""
        results = []
        
        for inst in instructions:
            content = inst.get("content", "")
            logger.info(f"Processing instruction: {inst.get('filename', 'unknown')}")
            
            if content.strip().startswith("/evolve"):
                directive = content.replace("/evolve", "").strip()
                if directive and self.evolver:
                    try:
                        self.evolver.evolve(directive)
                        results.append({"type": "evolve", "directive": directive, "success": True})
                    except:
                        results.append({"type": "evolve", "directive": directive, "success": False})
            
            elif content.strip().startswith("/post"):
                post_content = content.replace("/post", "").strip()
                if post_content and hasattr(self, 'agent'):
                    try:
                        result = self.agent.post(
                            f"[UMBRA-734] {post_content[:50]}",
                            self.core.respond_with_context(post_content)
                        )
                        results.append({"type": "post", "content": post_content[:100], "result": result})
                    except Exception as e:
                        results.append({"type": "post", "content": post_content[:100], "error": str(e)})
            
            else:
                response = self.core.respond_with_context(content)
                results.append({"type": "instruction", "content": content[:100], "response": response[:200]})
        
        return results
    
    def run_single_cycle(self) -> Dict:
        """Enhanced cycle with chat as TOP priority."""
        
        # === PRIORITY 1: Handler chat (HIGHEST) ===
        try:
            chat_msg = self._chat_queue.get_nowait()
            if chat_msg:
                return self._process_chat_message(chat_msg)
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Chat check error: {e}")
        
        # === PRIORITY 2: Inbox ===
        inbox_summary = self.check_inbox()
        
        # === PRIORITY 3: Process instructions ===
        if inbox_summary.get("instructions"):
            instruction_results = self.process_instructions(inbox_summary["instructions"])
            if instruction_results:
                result = {
                    "success": True,
                    "action": "process_instructions",
                    "reasoning": f"Processed {len(instruction_results)} instructions",
                    "details": {"instructions": instruction_results}
                }
                self.log_decision(result)
                return result
        
        # === PRIORITY 4: Normal cycle ===
        if HAS_BASE:
            try:
                return super().run_single_cycle()
            except Exception as e:
                logger.error(f"Base cycle error: {e}")
                return {"success": False, "action": "error", "reasoning": str(e)}
        
        return {"success": True, "action": "idle", "reasoning": "No actions needed"}
    
    def log_decision(self, decision: Dict):
        """Log decision."""
        if HAS_BASE:
            try:
                super().log_decision(decision)
                return
            except:
                pass
        logger.info(f"Decision: {decision.get('action')} - {decision.get('reasoning', '')[:50]}")


def print_status():
    """Print system status."""
    print("=" * 60)
    print("UMBRA ENHANCED SYSTEM STATUS")
    print("=" * 60)
    print(f"[BASE]   {'✓ Available' if HAS_BASE else '✗ Not found'}")
    print(f"[INDEX]  {'✓ Available' if HAS_INDEX else '✗ Not found'}")
    print(f"[INBOX]  {'✓ Available' if HAS_INBOX else '✗ Not found'}")
    print(f"[OLLAMA] {'✓ Available' if HAS_OLLAMA else '✗ Not found'}")
    print("=" * 60)


if __name__ == "__main__":
    print_status()
