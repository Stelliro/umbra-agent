"""
UMBRA Engine v1.0 — Standalone LLM Inference
=============================================
Replaces Ollama. Loads GGUF models via llama-cpp-python with CUDA.
Priority queue ensures chat never waits behind batch processing.

Install: pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
(adjust cu124 to match your CUDA version: cu121, cu122, cu123, cu124)

Model files go in: models/ directory (GGUF format)
Recommended: https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF
  → Download: Meta-Llama-3-8B-Instruct-Q4_K_M.gguf (~4.9GB)
"""
import threading, queue, time, json, logging, os
from pathlib import Path
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Generator

logger = logging.getLogger("UMBRA-ENGINE")

# Priority levels (lower = higher priority)
class Priority(IntEnum):
    CRITICAL = 0  # Handler chat, alerts
    HIGH = 1      # Reply generation
    NORMAL = 2    # Post evaluation, commenting
    LOW = 3       # Reflection, evolution, learning review


@dataclass(order=True)
class Job:
    priority: int
    seq: int = field(compare=True)  # tiebreaker: FIFO within same priority
    prompt: str = field(compare=False)
    params: dict = field(compare=False, default_factory=dict)
    result: threading.Event = field(compare=False, default_factory=threading.Event)
    response: str = field(compare=False, default="")
    error: str = field(compare=False, default="")


class UmbraEngine:
    """
    Standalone LLM engine with priority queue.
    Drop-in replacement for ollama module.
    """
    def __init__(self, models_dir="models", n_gpu_layers=-1, n_ctx=4096):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.n_gpu = n_gpu_layers
        self.n_ctx = n_ctx

        self._model = None
        self._model_name = None
        self._lock = threading.Lock()
        self._queue = queue.PriorityQueue()
        self._seq = 0  # monotonic counter for FIFO tiebreaking
        self._running = False
        self._worker = None
        self._llama = None  # lazy import

    def start(self):
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._process_loop, daemon=True, name="engine-worker")
        self._worker.start()
        logger.info("⚡ Engine worker started")

    def stop(self):
        self._running = False
        if self._worker:
            # Push a poison pill to unblock
            self._queue.put(Job(priority=99, seq=0, prompt="__STOP__"))
            self._worker.join(timeout=5)
        self._unload()
        logger.info("Engine stopped")

    # === Model Management ===

    def list_models(self) -> List[str]:
        """List available GGUF files."""
        if not self.models_dir.exists():
            return []
        return [f.name for f in self.models_dir.glob("*.gguf")]

    def find_model(self, name: str) -> Optional[Path]:
        """Find a model file by name or partial match."""
        # Exact match
        exact = self.models_dir / name
        if exact.exists():
            return exact
        # With .gguf extension
        with_ext = self.models_dir / f"{name}.gguf"
        if with_ext.exists():
            return with_ext
        # Partial match (e.g., "llama3" matches "Meta-Llama-3-8B-Instruct-Q4_K_M.gguf")
        name_lower = name.lower().replace("-", "").replace("_", "")
        for f in self.models_dir.glob("*.gguf"):
            fn = f.stem.lower().replace("-", "").replace("_", "")
            if name_lower in fn:
                return f
        return None

    def load(self, model_name: str) -> bool:
        """Load a GGUF model. Returns True on success."""
        if self._model_name == model_name and self._model is not None:
            return True  # Already loaded

        path = self.find_model(model_name)
        if not path:
            logger.error(f"Model not found: {model_name} (searched {self.models_dir})")
            logger.info(f"Available models: {self.list_models()}")
            return False

        self._unload()
        logger.info(f"Loading model: {path.name} (GPU layers: {self.n_gpu}, ctx: {self.n_ctx})")
        t0 = time.time()

        try:
            if self._llama is None:
                from llama_cpp import Llama
                self._llama = Llama

            self._model = self._llama(
                model_path=str(path),
                n_gpu_layers=self.n_gpu,
                n_ctx=self.n_ctx,
                verbose=False,
            )
            self._model_name = model_name
            logger.info(f"✅ Model loaded in {time.time()-t0:.1f}s: {path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self._model = None
            return False

    def _unload(self):
        if self._model:
            del self._model
            self._model = None
            self._model_name = None

    # === Inference (Ollama-compatible interface) ===

    def generate(self, model: str = None, prompt: str = "", format: str = None,
                 priority: int = Priority.NORMAL, timeout: float = None, **kw) -> Dict:
        """
        Ollama-compatible generate().
        Returns {"response": "...", "model": "..."}
        """
        if model and not self.load(model):
            return {"response": f"Error: model '{model}' not found", "model": model or ""}

        # Build params
        params = {"format": format}
        params.update(kw)

        # Submit job
        with self._lock:
            self._seq += 1
            job = Job(priority=priority, seq=self._seq, prompt=prompt, params=params)
        self._queue.put(job)

        # === FIX: Allow infinite timeout if timeout is None ===
        if job.result.wait(timeout=timeout):
            if job.error:
                return {"response": f"Error: {job.error}", "model": self._model_name or ""}
            return {"response": job.response, "model": self._model_name or ""}
        else:
            return {"response": "Error: inference timeout", "model": self._model_name or ""}

    def chat(self, model: str = None, messages: List[Dict] = None, stream: bool = False, **kw) -> Dict:
        """
        Ollama-compatible chat().
        Converts messages to a prompt and runs generate.
        """
        if not messages:
            messages = []

        # Convert chat messages to prompt
        prompt = self._messages_to_prompt(messages)
        result = self.generate(model=model, prompt=prompt, priority=Priority.CRITICAL, **kw)

        if stream:
            # Yield chunks for streaming compatibility
            def gen():
                for word in result["response"].split():
                    yield {"message": {"content": word + " "}}
            return gen()

        return {"message": {"content": result["response"]}}

    def _messages_to_prompt(self, messages: List[Dict]) -> str:
        """Convert chat messages to llama3 instruct format."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{content}<|eot_id|>")
            elif role == "user":
                parts.append(f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>")
            elif role == "assistant":
                parts.append(f"<|start_header_id|>assistant<|end_header_id|>\n\n{content}<|eot_id|>")
        parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
        return "".join(parts)

    # === Worker ===

    def _process_loop(self):
        """Background worker: pulls jobs from priority queue, runs inference."""
        while self._running:
            try:
                job = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            if job.prompt == "__STOP__":
                break

            if not self._model:
                job.error = "No model loaded"
                job.result.set()
                continue

            try:
                t0 = time.time()
                fmt = job.params.get("format")

                # JSON mode: add grammar constraint hint
                extra = {}
                if fmt == "json":
                    extra["grammar"] = None  # llama.cpp grammar could go here
                    # For now, rely on prompt instruction for JSON

                out = self._model(
                    job.prompt,
                    max_tokens=job.params.get("max_tokens", 1024),
                    temperature=job.params.get("temperature", 0.7),
                    stop=job.params.get("stop", ["<|eot_id|>", "<|end_of_text|>"]),
                    **extra,
                )

                text = out["choices"][0]["text"].strip()

                # JSON cleanup: strip markdown fences if present
                if fmt == "json" and text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()

                job.response = text
                elapsed = time.time() - t0
                tokens = out.get("usage", {}).get("completion_tokens", 0)
                logger.debug(f"Inference: {tokens} tok in {elapsed:.1f}s ({tokens/max(elapsed,0.01):.0f} t/s) pri={job.priority}")

            except Exception as e:
                job.error = str(e)
                logger.error(f"Inference error: {e}")

            job.result.set()

    # === Status ===

    def status(self) -> Dict:
        return {
            "running": self._running,
            "model": self._model_name,
            "models_available": self.list_models(),
            "queue_size": self._queue.qsize(),
            "gpu_layers": self.n_gpu,
            "ctx_size": self.n_ctx,
        }


class OllamaCompat:
    """
    Drop-in replacement for `import ollama`.
    Routes to primary engine by default, or to pool if available.
    """
    def __init__(self, engine: UmbraEngine, pool: 'ModelPool' = None):
        self.engine = engine
        self.pool = pool

    def generate(self, **kw) -> Dict:
        # If pool exists and a specific role/model is requested, route there
        if self.pool and kw.get("_role"):
            role = kw.pop("_role")
            return self.pool.generate(role, **kw)
        return self.engine.generate(**kw)

    def chat(self, **kw):
        return self.engine.chat(**kw)


class ModelPool:
    """
    Manages multiple loaded models for the Phoenix architecture.
    Each role gets its own UmbraEngine instance with a dedicated model.

    Usage:
        pool = ModelPool("models/")
        pool.add("judge", "llama3-8b", n_ctx=4096)
        pool.add("architect", "llama3-3b", n_ctx=2048)
        pool.add("auditor", "llama3-3b", n_ctx=2048)
        pool.start()

        result = pool.generate("judge", prompt="...", format="json")
    """
    def __init__(self, models_dir="models"):
        self.models_dir = models_dir
        self.engines: Dict[str, UmbraEngine] = {}
        self._roles: Dict[str, str] = {}  # role → model name

    def add(self, role: str, model: str, n_gpu_layers=-1, n_ctx=4096):
        """Register a role with a specific model."""
        engine = UmbraEngine(self.models_dir, n_gpu_layers=n_gpu_layers, n_ctx=n_ctx)
        self.engines[role] = engine
        self._roles[role] = model
        logger.info(f"Pool: registered '{role}' → {model}")

    def start(self):
        """Start all engines and load their models."""
        for role, engine in self.engines.items():
            engine.start()
            model = self._roles[role]
            if not engine.load(model):
                logger.warning(f"Pool: failed to load {model} for role '{role}'")
            else:
                logger.info(f"Pool: '{role}' ready ({model})")

    def stop(self):
        for engine in self.engines.values():
            engine.stop()

    def generate(self, role: str, **kw) -> Dict:
        """Generate using a specific role's engine."""
        if role not in self.engines:
            logger.warning(f"Pool: unknown role '{role}', falling back to first")
            role = next(iter(self.engines))
        kw.pop("model", None)  # model is determined by role
        return self.engines[role].generate(**kw)

    def has_role(self, role: str) -> bool:
        return role in self.engines

    def status(self) -> Dict:
        return {
            role: {
                "model": self._roles.get(role),
                "loaded": e._model is not None,
                "queue": e._queue.qsize()
            }
            for role, e in self.engines.items()
        }


# === Convenience: single global engine ===
_engine = None
_pool = None

def get_engine(models_dir="models", **kw) -> UmbraEngine:
    global _engine
    if _engine is None:
        _engine = UmbraEngine(models_dir, **kw)
    return _engine

def get_pool() -> Optional[ModelPool]:
    return _pool

def init(models_dir="models", model="llama3", **kw) -> OllamaCompat:
    """One-call setup. Returns Ollama-compatible interface."""
    engine = get_engine(models_dir, **kw)
    engine.start()
    engine.load(model)
    return OllamaCompat(engine)

def init_pool(models_dir="models", roles=None) -> ModelPool:
    """
    Initialize multi-model pool.
    roles: dict of {role_name: {model, n_ctx, n_gpu_layers}}
    """
    global _pool
    _pool = ModelPool(models_dir)
    if roles:
        for role, cfg in roles.items():
            _pool.add(
                role,
                cfg.get("model", "llama3"),
                n_gpu_layers=cfg.get("n_gpu_layers", -1),
                n_ctx=cfg.get("n_ctx", 4096),
            )
    _pool.start()
    return _pool
