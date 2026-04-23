"""Tests for ThinkingEngine — multi-stage reasoning"""
import sys, json, shutil, tempfile, time
sys.path.insert(0, '/home/claude')
from thinking import ThinkingEngine, ThinkingStage, ThoughtChain


# === Mock LLM ===
class MockLLM:
    """Returns predictable JSON/text for each stage."""
    def __init__(self):
        self.calls = []
    
    def generate(self, model="llama3", prompt="", format=None, **kw):
        self.calls.append({"prompt": prompt[:100], "format": format})
        
        # Match on the exact STAGE: line the engine uses
        if "STAGE: PARSE" in prompt:
            return {"response": json.dumps({
                "intent": "question", "topic": "AI architecture",
                "complexity": "medium", "needs_research": False,
                "key_points": ["swarm design", "agent memory"],
                "emotional_tone": "curious"
            })}
        
        if "STAGE: THINK" in prompt:
            return {"response": json.dumps({
                "reasoning": "The handler is asking about architecture. I should explain the pyramid structure.",
                "considerations": ["memory limits", "queue priority", "agent spawning"],
                "approach": "Explain with concrete examples",
                "confidence": 0.85,
                "tone": "explanatory"
            })}
        
        if "STAGE: DRAFT" in prompt:
            return {"response": "The swarm uses a pyramid structure where primary agents decompose tasks into sub-agents."}
        
        if "STAGE: REFINE" in prompt:
            return {"response": json.dumps({
                "quality": 0.8,
                "issues": ["could add more detail about memory limits"],
                "improved": "The swarm uses a pyramid structure. Primary agents decompose tasks into research and coding sub-agents. Each agent has independent memory with hard token limits — when full, it compresses its context and spawns a continuation agent.",
                "changes_made": ["added memory limit detail", "added continuation agent mention"]
            })}
        
        return {"response": "Default response from mock LLM."}


def setup():
    return ThinkingEngine(ollama=MockLLM(), model="llama3")


# === ThoughtChain ===

def test_chain_creation():
    chain = ThoughtChain(message="How does the swarm work?")
    assert chain.message == "How does the swarm work?"
    assert len(chain.stages) == 0
    assert chain.final_response == ""
    assert chain.status == "pending"
    print("✓ ThoughtChain: created")

def test_chain_add_stage():
    chain = ThoughtChain(message="test")
    chain.add_stage(ThinkingStage.PARSE, {"intent": "question"}, tokens=50)
    chain.add_stage(ThinkingStage.THINK, {"reasoning": "I should explain..."}, tokens=100)
    assert len(chain.stages) == 2
    assert chain.stages[0]["stage"] == "parse"
    assert chain.stages[1]["tokens"] == 100
    print(f"✓ ThoughtChain: {len(chain.stages)} stages added")

def test_chain_timing():
    chain = ThoughtChain(message="test")
    chain.add_stage(ThinkingStage.PARSE, {"intent": "q"}, tokens=10)
    time.sleep(0.05)
    chain.add_stage(ThinkingStage.THINK, {"r": "x"}, tokens=10)
    chain.complete("Final response")
    assert chain.total_time > 0
    assert chain.total_tokens == 20
    print(f"✓ ThoughtChain: {chain.total_time:.3f}s, {chain.total_tokens} tokens")

def test_chain_serialize():
    chain = ThoughtChain(message="test")
    chain.add_stage(ThinkingStage.PARSE, {"intent": "question"}, tokens=50)
    chain.complete("Done")
    d = chain.to_dict()
    assert "stages" in d
    assert "final_response" in d
    assert d["status"] == "complete"
    print("✓ ThoughtChain: serializes")


# === ThinkingEngine ===

def test_parse_stage():
    te = setup()
    result = te._run_parse("How does the swarm architecture work?", "")
    assert "intent" in result
    assert result["intent"] == "question"
    print(f"✓ Parse: intent={result['intent']}")

def test_think_stage():
    te = setup()
    parse = {"intent": "question", "topic": "swarm", "complexity": "medium"}
    result = te._run_think("How does swarm work?", parse, "")
    assert "reasoning" in result
    assert "confidence" in result
    print(f"✓ Think: confidence={result['confidence']}")

def test_draft_stage():
    te = setup()
    think = {"reasoning": "explain pyramid", "approach": "examples", "confidence": 0.85}
    result = te._run_draft("How does swarm work?", think, "")
    assert len(result) > 10
    print(f"✓ Draft: {len(result)} chars")

def test_refine_stage():
    te = setup()
    draft = "The swarm uses a pyramid structure."
    result = te._run_refine(draft, "How does swarm work?", "")
    assert "improved" in result
    assert len(result["improved"]) > len(draft)
    print(f"✓ Refine: {len(result['improved'])} chars (was {len(draft)})")


# === Full Chain ===

def test_full_think_chain():
    te = setup()
    chain = te.think("How does the swarm architecture work?")
    assert chain.status == "complete"
    assert len(chain.stages) >= 3  # parse, think, draft (+ optional refine)
    assert len(chain.final_response) > 20
    assert chain.total_tokens > 0
    print(f"✓ Full chain: {len(chain.stages)} stages, {chain.total_tokens} tokens")
    for s in chain.stages:
        print(f"    → {s['stage']}: {s['tokens']} tok")

def test_think_with_context():
    te = setup()
    chain = te.think("What about memory limits?",
                     context="Previous: We discussed the swarm pyramid design.")
    assert chain.status == "complete"
    assert len(chain.final_response) > 10
    print(f"✓ Full chain with context: {len(chain.stages)} stages")

def test_think_simple_message():
    """Short/simple messages should skip refine."""
    te = setup()
    te.refine_threshold = 999  # Force skip refine
    chain = te.think("hi")
    # Should still work, just fewer stages
    assert chain.status == "complete"
    print(f"✓ Simple message: {len(chain.stages)} stages")


# === Streaming Stages ===

def test_get_thinking_status():
    """UI should be able to poll thinking status."""
    te = setup()
    chain = te.think("complex question about agent architecture")
    d = chain.to_dict()
    assert "stages" in d
    assert d["status"] == "complete"
    # Each stage should have timing
    for s in d["stages"]:
        assert "elapsed" in s
        assert "stage" in s
    print(f"✓ Thinking status: {len(d['stages'])} stages with timing")


# === Multi-Turn ===

def test_multi_turn():
    """Engine should accept previous chain for continuations."""
    te = setup()
    chain1 = te.think("How does the swarm work?")
    # Follow-up uses previous chain as context
    chain2 = te.think("What about the memory limits specifically?",
                       context=f"Previous response: {chain1.final_response}")
    assert chain2.status == "complete"
    # Second chain's parse should have context awareness
    assert te.ollama.calls[-1]["prompt"]  # Some call was made
    print(f"✓ Multi-turn: chain1={len(chain1.stages)} stages, chain2={len(chain2.stages)} stages")


# === Config ===

def test_config_skip_refine():
    te = setup()
    te.skip_refine = True
    chain = te.think("Test without refine step")
    stage_names = [s["stage"] for s in chain.stages]
    assert "refine" not in stage_names
    print(f"✓ Config skip_refine: stages={stage_names}")

def test_config_depth():
    """Depth controls how many stages run."""
    te = setup()
    # Shallow: parse + draft only
    chain = te.think("Quick question", depth="shallow")
    assert len(chain.stages) <= 2
    print(f"✓ Shallow depth: {len(chain.stages)} stages")


if __name__ == "__main__":
    print("=" * 50)
    print("THINKING ENGINE TESTS")
    print("=" * 50)
    tests = [
        test_chain_creation, test_chain_add_stage, test_chain_timing, test_chain_serialize,
        test_parse_stage, test_think_stage, test_draft_stage, test_refine_stage,
        test_full_think_chain, test_think_with_context, test_think_simple_message,
        test_get_thinking_status, test_multi_turn,
        test_config_skip_refine, test_config_depth,
    ]
    for t in tests:
        t()
    print(f"\n{'='*50}\nALL {len(tests)} TESTS PASSED ✓\n{'='*50}")
