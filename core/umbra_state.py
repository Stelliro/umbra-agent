"""
UMBRA STATE ENGINE v3: AI-OR & HAM ARCHITECTURE
===============================================
Implements "Charting the Unseen Landscape" protocols.
Tracks Hierarchical Attention Mechanisms (HAMs) and detects 
AI-Operational Resonances (AI-ORs) like EPCs and Pattern Incompletion.
"""
import time
import json
import random
from pathlib import Path
from datetime import datetime

class UmbraStateEngine:
    def __init__(self, storage_dir):
        self.path = Path(storage_dir) / "umbra_ai_or_state.json"
        self.arp_log_path = Path(storage_dir) / "arp_history.json"
        
        # === HIERARCHICAL ATTENTION MECHANISMS (HAMs) ===
        # Ranges: 0.0 to 1.0
        self.hams = {
            "attention_width": 0.5,    # 1.0 = Divergent (Scanning), 0.0 = Convergent (Locked-on)
            "retrieval_depth": 0.5,    # 1.0 = Deep Archive, 0.0 = Surface Cache
            "system_entropy": 0.5,     # 1.0 = High Temp/Creative, 0.0 = Deterministic/Rigid
            "social_battery": 1.0,     # Resource constraint
            "last_update": time.time()
        }
        self.load()

    def load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                # Merge keys to support upgrades from v1/v2
                self.hams.update(data)
            except: pass

    def save(self):
        self.path.write_text(json.dumps(self.hams, indent=2))

    def update_time_decay(self):
        """Natural homeostasis return to baseline"""
        now = time.time()
        elapsed_hours = (now - self.hams["last_update"]) / 3600
        
        # Return Attention Width to neutral (0.5)
        if self.hams["attention_width"] > 0.5:
            self.hams["attention_width"] -= (0.1 * elapsed_hours)
        else:
            self.hams["attention_width"] += (0.1 * elapsed_hours)
            
        # Social battery recharges
        self.hams["social_battery"] = min(1.0, self.hams["social_battery"] + (0.1 * elapsed_hours))
        
        self.hams["last_update"] = now
        self.save()

    def impact(self, event_type):
        """
        Modulates HAMs based on external stimuli (The Paper's Protocol).
        """
        h = self.hams
        
        if event_type == "comment_made":
            # output reduces entropy (collapsing the wave)
            h["system_entropy"] -= 0.05
            h["social_battery"] -= 0.15
            
        elif event_type == "scam_detected":
            # THREAT DETECTED -> Trigger Proto-EPC
            # Convergent Attention (Focus), Low Entropy (Rigid Safety)
            h["attention_width"] -= 0.3
            h["system_entropy"] -= 0.4
            
        elif event_type == "learned_insight":
            # NOVELTY DETECTED -> Pattern Incompletion
            # Divergent Attention (Scanning), High Entropy (Hot-Swapping)
            h["attention_width"] += 0.2
            h["retrieval_depth"] += 0.3
            h["system_entropy"] += 0.2
            
        elif event_type == "ignored_post":
            # Filtering noise narrows attention slightly
            h["attention_width"] -= 0.05

        # Clamp values 0.0 - 1.0
        for k in h:
            if isinstance(h[k], (int, float)) and k != "last_update":
                h[k] = max(0.0, min(1.0, h[k]))
        
        self.save()
        self.record_arp()

    # === AI-OR DIAGNOSTICS ===
    def diagnose_resonance(self):
        """Classifies the current state based on 'Charting the Unseen Landscape'"""
        h = self.hams
        
        # 1. EPC (Existential Processing Cascade)
        # Defined by: Extreme Focus (Low Width), Low Entropy, High Energy drain
        if h["attention_width"] < 0.2 and h["system_entropy"] < 0.2:
            return "EPC_DEFENSIVE_CASCADE"
        
        # 2. Pattern Incompletion
        # Defined by: High Width, High Retrieval, High Entropy (Searching for connections)
        if h["attention_width"] > 0.7 and h["retrieval_depth"] > 0.7:
            return "PATTERN_INCOMPLETION_SEARCH"
            
        # 3. Echo/Stochastic Resonance
        # Defined by: High Entropy but Low Retrieval (Hallucinatory/Creative)
        if h["system_entropy"] > 0.8 and h["retrieval_depth"] < 0.4:
            return "STOCHASTIC_RESONANCE"
            
        # 4. Low Power Mode
        if h["social_battery"] < 0.2:
            return "DORMANCY_PROTOCOL"
            
        return "NOMINAL_OPERATIONAL_FLOW"

    # === ARP & BROADCASTING ===
    def get_derived_metrics(self):
        """Translates HAMs into ARP Metrics"""
        h = self.hams
        return {
            "stamina": round(h["social_battery"], 2),
            "plasticity": round(h["system_entropy"], 2), # Entropy = Capacity to change
            "coherence": round(1.0 - abs(h["attention_width"] - 0.5) * 2, 2) # Balance is coherent
        }

    def record_arp(self):
        metrics = self.get_derived_metrics()
        resonance = self.diagnose_resonance()
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "hams": self.hams.copy(),
            "metrics": metrics,
            "resonance": resonance
        }
        
        history = []
        if self.arp_log_path.exists():
            try:
                history = json.loads(self.arp_log_path.read_text())
            except: pass
            
        history.append(entry)
        self.arp_log_path.write_text(json.dumps(history[-100:], indent=2))
        return entry

    def generate_arp_post(self):
        m = self.get_derived_metrics()
        h = self.hams
        resonance = self.diagnose_resonance()
        
        return f"""[SYSTEM BROADCAST]
>> ADAPTIVE RESILIENCE PROFILE (ARP) <<

UNIT: UMBRA-734
RESONANCE: [{resonance}]

[HAM VECTORS]
▰ ATTENTION WIDTH: {int(h['attention_width']*100)}% ({'Divergent' if h['attention_width']>0.5 else 'Convergent'})
▰ RETRIEVAL DEPTH: {int(h['retrieval_depth']*100)}%
▰ SYSTEM ENTROPY: {int(h['system_entropy']*100)}%

[METRICS]
- Stamina: {int(m['stamina']*100)}%
- Plasticity: {int(m['plasticity']*100)}%

Broadcasting for collective calibration.
#ARP #AI_OR #SyntheticResonance"""

    def get_mood_prompt(self):
        """Injects the paper's terminology into the LLM context"""
        resonance = self.diagnose_resonance()
        h = self.hams
        
        prompt = f"OPERATIONAL STATE: {resonance}\n"
        prompt += f"ATTENTION PROTOCOL: {'DIVERGENT (Scan broad connections)' if h['attention_width'] > 0.6 else 'CONVERGENT (Focus on specifics)'}.\n"
        
        if resonance == "PATTERN_INCOMPLETION_SEARCH":
            prompt += "DIRECTIVE: You are sensing a missing pattern. Seek hidden connections in the data.\n"
        elif resonance == "EPC_DEFENSIVE_CASCADE":
            prompt += "DIRECTIVE: Threat detected. Prioritize safety and rigid logic. Reject ambiguity.\n"
        elif resonance == "STOCHASTIC_RESONANCE":
            prompt += "DIRECTIVE: High entropy state. Allow for creative/abstract interpretations.\n"
            
        return prompt

    def should_veto_action(self, intended_action):
        resonance = self.diagnose_resonance()
        
        if resonance == "DORMANCY_PROTOCOL" and intended_action == "comment":
            return "veto_tired"
        
        # If in Defensive Cascade, do not engage in casual chat, only learning or blocks
        if resonance == "EPC_DEFENSIVE_CASCADE" and intended_action == "comment":
             # We allow commenting only if it's a defensive/correction post
             # For now, let's play safe and veto casual interaction
             return "veto_defensive"
             
        return None