"""UMBRA Version Module"""
V = "0.8.0"
NAME = "Glass Box"
STATUS = "Alpha"
FULL = f"UMBRA v{V} ({NAME}) [{STATUS}]"

HISTORY = [
    ("0.8.0", "Glass Box",    "Transparency layer, integrity monitor, 4 autonomous bug fixes"),
    ("0.7.0", "Omni-Loader",  "WebUI v8, memory sub-tabs, smart author resolution"),
    ("0.6.0", "Refinement",   "Fuzzy log parser, crash-proof indexing"),
    ("0.5.0", "The Eye",      "umbra_web.py, live feed, archives"),
    ("0.4.0", "Memory",       "Knowledge/Threat/Post indexes"),
    ("0.3.0", "Bio-Digital",  "State engine v3, HAMs, entropy, social battery"),
    ("0.2.0", "The Loop",     "Autonomous scan-evaluate-act cycle"),
    ("0.1.0", "Genesis",      "Initial foundation"),
]

def banner():
    return f"""
╔══════════════════════════════════════╗
║  {FULL:^36}  ║
╚══════════════════════════════════════╝"""

def ctx():
    """Compact version context for LLM injection"""
    return f"[UMBRA v{V} // {NAME}]"

if __name__ == "__main__":
    print(banner())
    for v, n, d in HISTORY:
        print(f"  v{v} '{n}': {d}")
