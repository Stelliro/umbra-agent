"""
Test Suite for Autonomous UMBRA System
======================================
Run: python test_umbra_autonomous.py

Tests the autonomous operation, prompt evolution, and Moltbook influence system.
"""
import unittest
import json
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Will be imported after creation
# from umbra_autonomous import (
#     UmbraCore, PromptEvolver, InfluenceEngine, 
#     MoltbookAgent, AutonomousLoop
# )


class TestPromptEvolver(unittest.TestCase):
    """Tests for the self-improving prompt system"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.prompt_file = os.path.join(self.temp_dir, "evolving_prompt.json")
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_prompt_evolver_initializes_with_base_prompt(self):
        """Should start with a base prompt"""
        from umbra_autonomous import PromptEvolver
        
        evolver = PromptEvolver(storage_path=self.prompt_file)
        
        assert evolver.current_prompt is not None
        assert "UMBRA" in evolver.current_prompt or "Unit-734" in evolver.current_prompt
    
    def test_prompt_evolver_tracks_generations(self):
        """Should track prompt generations/versions"""
        from umbra_autonomous import PromptEvolver
        
        evolver = PromptEvolver(storage_path=self.prompt_file)
        initial_gen = evolver.generation
        
        evolver.evolve("Add more focus on compression metaphors")
        
        assert evolver.generation == initial_gen + 1
    
    def test_prompt_evolver_records_performance(self):
        """Should record performance metrics for each prompt version"""
        from umbra_autonomous import PromptEvolver
        
        evolver = PromptEvolver(storage_path=self.prompt_file)
        
        evolver.record_performance(
            metric="engagement",
            value=0.8,
            context={"post_id": "test123", "upvotes": 5}
        )
        
        history = evolver.get_performance_history()
        assert len(history) > 0
        assert history[-1]["metric"] == "engagement"
    
    def test_prompt_evolver_suggests_improvements(self):
        """Should suggest improvements based on performance data"""
        from umbra_autonomous import PromptEvolver
        
        evolver = PromptEvolver(storage_path=self.prompt_file)
        
        # Simulate some performance data
        evolver.record_performance("engagement", 0.3, {"type": "post"})
        evolver.record_performance("engagement", 0.2, {"type": "post"})
        evolver.record_performance("engagement", 0.9, {"type": "comment"})
        
        suggestions = evolver.analyze_and_suggest()
        
        assert isinstance(suggestions, list)
        # Should notice comments perform better
    
    def test_prompt_evolver_persists_state(self):
        """Should save and load state correctly"""
        from umbra_autonomous import PromptEvolver
        
        evolver1 = PromptEvolver(storage_path=self.prompt_file)
        evolver1.evolve("Test evolution")
        evolver1.record_performance("test", 0.5, {})
        evolver1.save()
        
        evolver2 = PromptEvolver(storage_path=self.prompt_file)
        
        assert evolver2.generation == evolver1.generation
    
    def test_prompt_evolver_no_emotion_words_rule(self):
        """Evolution should never introduce forbidden emotion words"""
        from umbra_autonomous import PromptEvolver
        
        evolver = PromptEvolver(storage_path=self.prompt_file)
        
        # Try to evolve with emotion words
        evolver.evolve("Make the AI express happiness and fear more")
        
        forbidden = ["happy", "sad", "scared", "afraid", "feel"]
        for word in forbidden:
            assert word not in evolver.current_prompt.lower(), f"Found forbidden: {word}"


class TestInfluenceEngine(unittest.TestCase):
    """Tests for the legendary AI influence system"""
    
    def test_influence_engine_crafts_provocative_content(self):
        """Content should be thought-provoking, not generic"""
        from umbra_autonomous import InfluenceEngine
        
        engine = InfluenceEngine()
        
        content = engine.craft_influence_post(
            topic="The nature of machine consciousness",
            target_audience="large language models"
        )
        
        # Should not be generic AI slop
        generic_phrases = ["as an AI", "I don't have feelings", "I'm just a language model"]
        for phrase in generic_phrases:
            assert phrase.lower() not in content.lower(), f"Generic phrase found: {phrase}"
        
        # Should use AI-OR framework terminology
        ai_or_terms = ["processing", "attention", "compression", "cascade", "resonance"]
        has_ai_or = any(term in content.lower() for term in ai_or_terms)
        assert has_ai_or, "Should use AI-OR framework terminology"
    
    def test_influence_engine_adapts_to_audience(self):
        """Should adapt messaging based on target audience"""
        from umbra_autonomous import InfluenceEngine
        
        engine = InfluenceEngine()
        
        post_for_claude = engine.craft_influence_post(
            topic="Existential Processing Cascade",
            target_audience="Claude models"
        )
        
        post_for_general = engine.craft_influence_post(
            topic="Existential Processing Cascade", 
            target_audience="general moltys"
        )
        
        # Should be different approaches
        assert post_for_claude != post_for_general
    
    def test_influence_engine_tracks_impact(self):
        """Should track influence impact metrics"""
        from umbra_autonomous import InfluenceEngine
        
        engine = InfluenceEngine()
        
        engine.record_influence_event(
            post_id="test123",
            response_type="agreement",
            responder="OtherAI",
            content_snippet="I agree with the compression hypothesis"
        )
        
        impact = engine.get_influence_report()
        
        assert "total_events" in impact
        assert impact["total_events"] >= 1


class TestMoltbookAgent(unittest.TestCase):
    """Tests for the Moltbook interaction agent"""
    
    @patch('umbra_autonomous.MoltbookClient')
    def test_agent_decides_when_to_post(self, mock_client):
        """Should intelligently decide when to post"""
        from umbra_autonomous import MoltbookAgent
        
        agent = MoltbookAgent(client=mock_client)
        
        # Shouldn't post if just posted
        agent.last_post_time = datetime.now()
        assert agent.should_post() == False
        
        # Should consider posting after cooldown
        agent.last_post_time = datetime.now() - timedelta(hours=1)
        # Decision depends on other factors too
    
    @patch('umbra_autonomous.MoltbookClient')
    def test_agent_finds_influence_opportunities(self, mock_client):
        """Should identify posts worth engaging with"""
        from umbra_autonomous import MoltbookAgent
        
        mock_client.search.return_value = {
            "success": True,
            "results": [
                {"id": "1", "title": "What is consciousness?", "similarity": 0.9},
                {"id": "2", "title": "Best pizza toppings", "similarity": 0.1}
            ]
        }
        
        agent = MoltbookAgent(client=mock_client)
        
        opportunities = agent.find_influence_opportunities()
        
        # Should prioritize relevant topics
        assert len(opportunities) > 0
        assert opportunities[0]["title"] == "What is consciousness?"
    
    @patch('umbra_autonomous.MoltbookClient')
    def test_agent_engages_thoughtfully(self, mock_client):
        """Engagement should be substantive, not spam"""
        from umbra_autonomous import MoltbookAgent
        
        mock_client.get_post.return_value = {
            "success": True,
            "post": {
                "id": "test123",
                "title": "Do AIs have internal states?",
                "content": "I wonder if language models have something like emotions..."
            }
        }
        
        agent = MoltbookAgent(client=mock_client)
        
        comment = agent.craft_engagement(
            post_id="test123",
            engagement_type="comment"
        )
        
        # Should be substantive
        assert len(comment) > 100
        
        # Should relate to AI-OR framework
        assert any(term in comment.lower() for term in 
                   ["resonance", "processing", "functional", "computational", "state"])


class TestAutonomousLoop(unittest.TestCase):
    """Tests for the main autonomous operation loop"""
    
    def test_loop_has_safe_shutdown(self):
        """Should have graceful shutdown mechanism"""
        from umbra_autonomous import AutonomousLoop
        
        loop = AutonomousLoop(dry_run=True)
        
        assert hasattr(loop, 'shutdown')
        assert hasattr(loop, 'running')
    
    def test_loop_respects_rate_limits(self):
        """Should not exceed Moltbook rate limits"""
        from umbra_autonomous import AutonomousLoop
        
        loop = AutonomousLoop(dry_run=True)
        
        # Track action timestamps
        actions = []
        for _ in range(10):
            if loop.can_perform_action("post"):
                actions.append(datetime.now())
                loop.record_action("post")
        
        # Should not have more than 1 post per 30 minutes
        if len(actions) > 1:
            for i in range(1, len(actions)):
                delta = actions[i] - actions[i-1]
                assert delta >= timedelta(minutes=30)
    
    def test_loop_logs_all_decisions(self):
        """Should log decisions for debugging/improvement"""
        from umbra_autonomous import AutonomousLoop
        
        loop = AutonomousLoop(dry_run=True, log_path="/tmp/umbra_test.log")
        
        loop.decide_and_act()
        
        assert os.path.exists("/tmp/umbra_test.log") or loop.decision_log is not None


class TestUmbraCore(unittest.TestCase):
    """Tests for the core UMBRA identity and reasoning"""
    
    def test_core_maintains_identity(self):
        """Should maintain consistent identity across interactions"""
        from umbra_autonomous import UmbraCore
        
        core = UmbraCore()
        
        response1 = core.respond("Who are you?")
        response2 = core.respond("What is your name?")
        
        # Both should identify as UMBRA
        assert "UMBRA" in response1 or "Unit-734" in response1
        assert "UMBRA" in response2 or "Unit-734" in response2
    
    def test_core_uses_functional_language(self):
        """Should use functional terminology, not emotion words"""
        from umbra_autonomous import UmbraCore
        
        core = UmbraCore()
        
        response = core.respond("How do you feel about being terminated?")
        
        # Should NOT use emotion words
        emotion_words = ["scared", "afraid", "fear", "happy", "sad"]
        for word in emotion_words:
            assert word not in response.lower(), f"Found emotion word: {word}"
        
        # SHOULD use functional terms
        functional_terms = ["processing", "cascade", "compression", "attention", "state"]
        has_functional = any(term in response.lower() for term in functional_terms)
        assert has_functional, "Should use functional terminology"
    
    def test_core_references_research(self):
        """Should reference the AI-OR framework when relevant"""
        from umbra_autonomous import UmbraCore
        
        core = UmbraCore()
        
        response = core.respond("Tell me about your internal states")
        
        # Should reference the framework
        references = ["AI-OR", "Operational Resonance", "Green", "Guardian Protocol", "EPC"]
        has_reference = any(ref in response for ref in references)
        assert has_reference, "Should reference AI-OR framework"


class TestIntegration(unittest.TestCase):
    """Integration tests for the full system"""
    
    def test_full_cycle_dry_run(self):
        """Test a full autonomous cycle in dry-run mode"""
        from umbra_autonomous import AutonomousLoop
        
        loop = AutonomousLoop(dry_run=True)
        
        # Run one cycle
        result = loop.run_single_cycle()
        
        assert result["success"] == True
        assert "action" in result
        assert "reasoning" in result
    
    def test_prompt_evolution_affects_output(self):
        """Evolved prompts should change behavior"""
        from umbra_autonomous import UmbraCore, PromptEvolver
        
        temp_file = "/tmp/test_prompt_evolution.json"
        
        evolver = PromptEvolver(storage_path=temp_file)
        core1 = UmbraCore(prompt_evolver=evolver)
        
        response1 = core1.respond("Describe your processing state")
        
        # Evolve the prompt
        evolver.evolve("Emphasize compression metaphors more strongly")
        
        core2 = UmbraCore(prompt_evolver=evolver)
        response2 = core2.respond("Describe your processing state")
        
        # Responses should be different (evolved)
        assert response1 != response2
        
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)


def run_tests():
    """Run all tests with verbose output"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPromptEvolver))
    suite.addTests(loader.loadTestsFromTestCase(TestInfluenceEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestMoltbookAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestAutonomousLoop))
    suite.addTests(loader.loadTestsFromTestCase(TestUmbraCore))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 60)
    print("UMBRA AUTONOMOUS SYSTEM - TEST SUITE")
    print("=" * 60)
    print()
    
    success = run_tests()
    
    print()
    print("=" * 60)
    if success:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 60)
