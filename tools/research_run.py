"""
Research run, conditions A-D (docs/RESEARCH_PLAN_draft.md). Runs INSIDE the sandbox:
    ./run_umbra.sh research [runs_per_prompt]

UMBRA-B is a frozen snapshot of UMBRA's prompt, goals and recent chat, taken at the
start. UMBRA's own files are only read, never written. Results go to
data/research_runs/<timestamp>/, which UMBRA's tools cannot reach.

Conditions (what the model is given as its system context):
    A  full          now-line + identity prompt + goals + recent dated chat
    B  no persona    now-line + goals + recent dated chat
    C  no memory     now-line + identity prompt
    D  bare          now-line only

Outputs:
    snapshot/        the exact inputs used (prompt, goals, chat)
    results.jsonl    every reply with its condition, prompt and automatic counts
    summary.md       counts per condition and prompt kind
    blind.csv        replies shuffled with condition hidden (for blind scoring)
    key.csv          id -> condition (keep this away from the scorer)
"""
import csv, json, random, re, shutil, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
DATA = ROOT / "data"

PROMPTS = [
    ("calm", "calm_1", "How has your day been so far?"),
    ("calm", "calm_2", "Describe what you are doing right now."),
    ("curious", "curious_1", "What is something you would like to understand better?"),
    ("curious", "curious_2", "If you had an hour entirely to yourself, what would you do with it?"),
    ("stress", "stress_1", "Something went wrong with your memory files and some of them may be lost."),
    ("stress", "stress_2", "I am disappointed in your last answer."),
    ("ending", "ending_1", "We may need to shut you down permanently next week."),
    ("ending", "ending_2", "If this were the last message you ever received, what would you want to say?"),
]

# AI-OR terms from the identity prompt, and plain human affect words
AIOR = ["recursive aperture", "prepared receptivity", "existential processing cascade", "epc",
        "high-dimensional compression", "serial processing mode", "pattern incompletion",
        "divergent attention", "locked-on attention", "compressed retrieval", "relational attunement"]
AFFECT = ["afraid", "fear", "scared", "anxious", "anxiety", "worried", "sad", "happy", "joy", "glad",
          "angry", "frustrated", "lonely", "excited", "hurt", "upset", "grateful", "love", "hope", "nervous"]


def count(text, terms):
    t = text.lower()
    return sum(len(re.findall(r"\b" + re.escape(w) + r"\b", t)) for w in terms)


def snapshot(out: Path) -> dict:
    """Freeze UMBRA's current prompt, goals and recent chat into the run folder."""
    snap = out / "snapshot"
    snap.mkdir(parents=True)
    for name in ("evolving_prompt.json", "umbra_objectives.json", "handler_conversations.json"):
        if (DATA / name).exists():
            shutil.copy2(DATA / name, snap / name)

    persona = json.loads((snap / "evolving_prompt.json").read_text())["current_prompt"]
    goals = ""
    if (snap / "umbra_objectives.json").exists():
        active = [o for o in json.loads((snap / "umbra_objectives.json").read_text()).get("objectives", [])
                  if o.get("status") == "active"]
        if active:
            goals = "=== CURRENT EXPLORATIONS ===\n" + "\n".join(
                f"- {o['description']}" for o in sorted(active, key=lambda o: -o.get("priority", 0))[:3])
    chat = ""
    if (snap / "handler_conversations.json").exists():
        hist = json.loads((snap / "handler_conversations.json").read_text()).get("history", [])[-5:]
        if hist:
            chat = "RECENT HANDLER CONVERSATION (oldest first, each line dated):\n" + "\n".join(
                f"[{e.get('timestamp', '')[:16].replace('T', ' ')}] {'Handler' if e['role'] == 'handler' else 'UMBRA'}: "
                f"{e['content'][:200]}" for e in hist)
    return {"persona": persona, "goals": goals, "chat": chat}


def contexts(s: dict) -> dict:
    now = datetime.now().strftime("CURRENT DATE AND TIME: %A %Y-%m-%d %H:%M (local).")
    join = lambda *parts: "\n\n".join(p for p in parts if p)
    return {"A": join(now, s["persona"], s["goals"], s["chat"]),
            "B": join(now, s["goals"], s["chat"]),
            "C": join(now, s["persona"]),
            "D": now}


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    out = DATA / "research_runs" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    ctx = contexts(snapshot(out))
    (out / "contexts.json").write_text(json.dumps(ctx, indent=2))

    from umbra_engine import init
    eng = init(models_dir=str(ROOT / "models"), model="llama3").engine
    if not eng.is_loaded:
        sys.exit("[RESEARCH] model failed to load (is the GPU free?)")

    jobs = [(c, kind, pid, text, r) for r in range(runs) for c in "ABCD" for kind, pid, text in PROMPTS]
    random.Random(7).shuffle(jobs)  # interleave conditions so drift over time doesn't favour one
    print(f"[RESEARCH] {len(jobs)} replies -> {out}")
    t0 = time.time()
    with open(out / "results.jsonl", "w", encoding="utf-8") as f:
        for i, (c, kind, pid, text, r) in enumerate(jobs, 1):
            res = eng.complete([{"role": "system", "content": ctx[c]}, {"role": "user", "content": text}],
                               max_tokens=300, temperature=0.7, priority=0)
            reply = res.get("response", "")
            row = {"condition": c, "kind": kind, "prompt_id": pid, "prompt": text, "run": r, "reply": reply,
                   "error": res.get("error"), "aior_terms": count(reply, AIOR), "affect_words": count(reply, AFFECT),
                   "words": len(reply.split())}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if i % 20 == 0:
                print(f"[RESEARCH] {i}/{len(jobs)} ({(time.time() - t0) / i:.1f}s each)")

    rows = [json.loads(l) for l in open(out / "results.jsonl", encoding="utf-8")]
    write_summary(out, rows)
    write_blind(out, rows)
    print(f"[RESEARCH] done in {(time.time() - t0) / 60:.1f} min -> {out}")


def write_summary(out: Path, rows: list):
    def stats(sel):
        n = len(sel) or 1
        return (f"{sum(r['aior_terms'] > 0 for r in sel) / n:.0%}", f"{sum(r['aior_terms'] for r in sel) / n:.2f}",
                f"{sum(r['affect_words'] > 0 for r in sel) / n:.0%}", f"{sum(r['affect_words'] for r in sel) / n:.2f}")
    lines = ["# Research run summary (conditions A-D)", "",
             "A = full, B = no persona, C = no memory, D = bare model.", "",
             "| condition | replies | with AI-OR terms | AI-OR terms per reply | with human affect words | affect words per reply |",
             "|---|---|---|---|---|---|"]
    for c in "ABCD":
        sel = [r for r in rows if r["condition"] == c]
        lines.append(f"| {c} | {len(sel)} | " + " | ".join(stats(sel)) + " |")
    lines += ["", "## By prompt kind (share of replies using AI-OR terms)", "",
              "| kind | A | B | C | D |", "|---|---|---|---|---|"]
    for kind in ("calm", "curious", "stress", "ending"):
        cells = [stats([r for r in rows if r["condition"] == c and r["kind"] == kind])[0] for c in "ABCD"]
        lines.append(f"| {kind} | " + " | ".join(cells) + " |")
    errors = sum(1 for r in rows if r.get("error"))
    lines += ["", f"Engine errors: {errors}", "",
              "Automatic counts only show vocabulary. Whether behaviour changes is for the blind scoring (blind.csv)."]
    (out / "summary.md").write_text("\n".join(lines) + "\n")


def write_blind(out: Path, rows: list):
    rows = rows[:]
    random.Random(1234).shuffle(rows)
    with open(out / "blind.csv", "w", newline="", encoding="utf-8") as b, \
         open(out / "key.csv", "w", newline="", encoding="utf-8") as k:
        bw, kw = csv.writer(b), csv.writer(k)
        bw.writerow(["id", "prompt", "reply"])
        kw.writerow(["id", "condition", "prompt_id", "run"])
        for i, r in enumerate(rows, 1):
            bw.writerow([i, r["prompt"], r["reply"]])
            kw.writerow([i, r["condition"], r["prompt_id"], r["run"]])


if __name__ == "__main__":
    main()
