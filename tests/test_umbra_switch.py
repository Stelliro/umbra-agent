"""Tests for UmbraSwitch and UmbraBrain — external editable weight DB."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Make project root importable.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.umbra_switch import (  # noqa: E402
    UmbraSwitch,
    Switch,
    VALID_CATEGORIES,
    WEIGHT_MAX,
    WEIGHT_MIN,
)
from core.umbra_brain import UmbraBrain, BrainResponse  # noqa: E402


class _MockEngine:
    """Minimal engine matching the chat() contract used by UmbraBrain."""

    def __init__(self, reply: str = "engine reply"):
        self.reply = reply
        self.calls = []

    def chat(self, model=None, messages=None, **kw):
        self.calls.append({"model": model, "messages": messages, "kw": kw})
        return {"message": {"content": self.reply}}


class SwitchCRUDTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "switch.db"
        self.sw = UmbraSwitch(db_path=self.db_path)

    def tearDown(self):
        self.sw.close()
        self.tmp.cleanup()

    def test_register_creates_switch(self):
        s = self.sw.register("alpha concept", "alpha is the first")
        self.assertIsInstance(s, Switch)
        self.assertEqual(s.key, "alpha concept")
        self.assertEqual(s.category, "concept")
        self.assertIn(s.category, VALID_CATEGORIES)
        self.assertIsNotNone(self.sw.get(s.id))
        self.assertIsNotNone(self.sw.get("alpha concept"))

    def test_register_invalid_category(self):
        with self.assertRaises(ValueError):
            self.sw.register("bad", "x", category="not_real")

    def test_register_empty_key(self):
        with self.assertRaises(ValueError):
            self.sw.register("   ", "x")

    def test_register_updates_existing(self):
        a = self.sw.register("dup key", "first content")
        b = self.sw.register("dup key", "second content")
        self.assertEqual(a.id, b.id)
        self.assertEqual(self.sw.get(a.id).content, "second content")

    def test_delete(self):
        s = self.sw.register("temp", "x")
        self.assertTrue(self.sw.delete(s.id))
        self.assertIsNone(self.sw.get(s.id))
        self.assertFalse(self.sw.delete("missing"))

    def test_lock_blocks_delete(self):
        s = self.sw.register("guarded", "x")
        self.sw.lock(s.id, True)
        with self.assertRaises(PermissionError):
            self.sw.delete(s.id)
        self.assertTrue(self.sw.delete(s.id, force=True))


class WeightEditingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sw = UmbraSwitch(db_path=Path(self.tmp.name) / "w.db")
        self.s = self.sw.register("concept x", "body", weight=2.0)

    def tearDown(self):
        self.sw.close()
        self.tmp.cleanup()

    def test_reinforce_increases_weight(self):
        before = self.s.weight
        updated = self.sw.reinforce(self.s.id, 0.5)
        self.assertAlmostEqual(updated.weight, before + 0.5, places=4)

    def test_weaken_decreases_weight(self):
        before = self.s.weight
        updated = self.sw.weaken(self.s.id, 0.5)
        self.assertAlmostEqual(updated.weight, before - 0.5, places=4)

    def test_weight_clamped(self):
        self.sw.set_weight(self.s.id, 999.0)
        self.assertEqual(self.sw.get(self.s.id).weight, WEIGHT_MAX)
        self.sw.set_weight(self.s.id, -50.0)
        self.assertEqual(self.sw.get(self.s.id).weight, WEIGHT_MIN)


class SearchAndRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sw = UmbraSwitch(
            db_path=Path(self.tmp.name) / "r.db",
            direct_threshold=3.0,
            route_top_k=5,
        )
        self.sw.register(
            "system identity",
            "The system is a local autonomous AI workstation.",
            category="fact",
            weight=4.0,
            tags=["identity"],
            triggers=["who are you", "describe the system"],
        )
        self.sw.register(
            "greeting reply",
            "Hello operator. Online.",
            category="response",
            weight=8.0,
            triggers=["hello", "hi there"],
        )
        self.sw.register(
            "unrelated thing",
            "Spaghetti recipe.",
            category="concept",
            weight=1.0,
        )

    def tearDown(self):
        self.sw.close()
        self.tmp.cleanup()

    def test_search_finds_matching_switch(self):
        hits = self.sw.search("describe the system identity")
        self.assertTrue(hits)
        keys = [s.key for s, _ in hits]
        self.assertIn("system identity", keys)

    def test_search_empty_for_no_tokens(self):
        self.assertEqual(self.sw.search("a the of"), [])

    def test_route_returns_direct_for_high_score_response(self):
        result = self.sw.route("hello there")
        self.assertTrue(result.has_direct, msg=f"matched={result.matched}")
        self.assertEqual(result.direct_answer, "Hello operator. Online.")

    def test_route_returns_context_block_only_for_facts(self):
        result = self.sw.route("describe the system identity")
        self.assertFalse(result.has_direct)
        self.assertIn("system identity", result.context_block)

    def test_route_empty_for_unrelated_query(self):
        result = self.sw.route("xyzzy plover")
        self.assertEqual(result.matched, [])
        self.assertEqual(result.context_block, "")

    def test_usage_count_increments_on_route(self):
        before = self.sw.get("system identity").usage_count
        self.sw.route("describe the system identity")
        after = self.sw.get("system identity").usage_count
        self.assertEqual(after, before + 1)


class GraphAndMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sw = UmbraSwitch(db_path=Path(self.tmp.name) / "g.db")

    def tearDown(self):
        self.sw.close()
        self.tmp.cleanup()

    def test_link_creates_parent_child(self):
        p = self.sw.register("parent node", "p body")
        c = self.sw.register("child node", "c body")
        self.assertTrue(self.sw.link(p.id, c.id))
        children = self.sw.children_of(p.id)
        self.assertEqual([s.id for s in children], [c.id])

    def test_self_link_rejected(self):
        s = self.sw.register("solo", "x")
        with self.assertRaises(ValueError):
            self.sw.link(s.id, s.id)

    def test_prune_removes_low_weight_unlocked(self):
        keep = self.sw.register("important", "x", weight=5.0)
        kill = self.sw.register("trivia", "x", weight=0.1)
        locked = self.sw.register("locked low", "x", weight=0.1, locked=True)
        removed = self.sw.prune(threshold=0.25)
        self.assertEqual(removed, 1)
        self.assertIsNotNone(self.sw.get(keep.id))
        self.assertIsNone(self.sw.get(kill.id))
        self.assertIsNotNone(self.sw.get(locked.id))

    def test_snapshot_round_trip(self):
        self.sw.register("a thing", "body a", weight=2.0, tags=["t1"])
        self.sw.register("b thing", "body b", weight=3.0)
        snap = self.sw.snapshot()
        self.assertEqual(len(snap), 2)

        # New DB, import.
        sw2 = UmbraSwitch(db_path=Path(self.tmp.name) / "g2.db")
        try:
            n = sw2.import_snapshot(snap)
            self.assertEqual(n, 2)
            self.assertIsNotNone(sw2.get("a thing"))
            self.assertIsNotNone(sw2.get("b thing"))
        finally:
            sw2.close()


class BrainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sw = UmbraSwitch(
            db_path=Path(self.tmp.name) / "b.db",
            direct_threshold=3.0,
        )
        self.engine = _MockEngine(reply="engine speaks")
        self.brain = UmbraBrain(engine=self.engine, switch=self.sw, model="test-model")

    def tearDown(self):
        self.sw.close()
        self.tmp.cleanup()

    def test_chat_uses_switch_for_direct_answer(self):
        self.sw.register(
            "ping reply",
            "pong",
            category="response",
            weight=9.0,
            triggers=["ping"],
        )
        resp = self.brain.chat("ping")
        self.assertEqual(resp.source, "switch")
        self.assertEqual(resp.text, "pong")
        self.assertEqual(self.engine.calls, [])

    def test_chat_falls_back_to_engine(self):
        self.sw.register(
            "context fact",
            "Context body.",
            category="fact",
            weight=2.0,
            triggers=["weather"],
        )
        resp = self.brain.chat("tell me about weather patterns")
        self.assertEqual(resp.source, "gguf")
        self.assertEqual(resp.text, "engine speaks")
        self.assertEqual(len(self.engine.calls), 1)
        sys_msg = self.engine.calls[0]["messages"][0]
        self.assertEqual(sys_msg["role"], "system")
        self.assertIn("context fact", sys_msg["content"])

    def test_chat_with_no_engine_returns_fallback(self):
        brain = UmbraBrain(engine=None, switch=self.sw)
        resp = brain.chat("nothing matches abc xyz")
        self.assertEqual(resp.source, "fallback")
        self.assertEqual(resp.text, "")

    def test_force_gguf_skips_direct(self):
        self.sw.register("ping reply", "pong", category="response", weight=9.0, triggers=["ping"])
        resp = self.brain.chat("ping", force_gguf=True)
        self.assertEqual(resp.source, "gguf")
        self.assertEqual(len(self.engine.calls), 1)

    def test_reinforce_adjusts_used_switches(self):
        s = self.sw.register("ping reply", "pong", category="response", weight=5.0, triggers=["ping"])
        before = self.sw.get(s.id).weight
        resp = self.brain.chat("ping")
        self.brain.reinforce(resp, signal=1.0)
        after = self.sw.get(s.id).weight
        self.assertGreater(after, before)


if __name__ == "__main__":
    unittest.main()
