"""
UMBRA Engine Setup
==================
Run this once to set up the standalone LLM engine.

1. Installs llama-cpp-python with CUDA support
2. Downloads a model if none exist
3. Validates the setup
"""
import subprocess, sys, os, shutil
from pathlib import Path

MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

def detect_cuda():
    """Detect CUDA version for correct wheel."""
    try:
        r = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if r.returncode == 0:
            # Parse CUDA version from nvidia-smi output
            for line in r.stdout.split("\n"):
                if "CUDA Version" in line:
                    ver = line.split("CUDA Version:")[1].strip().split()[0]
                    major, minor = ver.split(".")[:2]
                    return f"cu{major}{minor}"
    except FileNotFoundError:
        pass
    return None

def install_llama_cpp():
    cuda = detect_cuda()
    if cuda:
        print(f"[✓] Detected CUDA: {cuda}")
        # Install with CUDA support
        url = f"https://abetlen.github.io/llama-cpp-python/whl/{cuda}"
        cmd = [sys.executable, "-m", "pip", "install", "llama-cpp-python", "--extra-index-url", url]
    else:
        print("[!] No CUDA detected. Installing CPU-only version.")
        cmd = [sys.executable, "-m", "pip", "install", "llama-cpp-python"]

    print(f"[*] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print("[✓] llama-cpp-python installed")

def check_models():
    ggufs = list(MODELS_DIR.glob("*.gguf"))
    if ggufs:
        print(f"[✓] Found {len(ggufs)} model(s):")
        for f in ggufs:
            size_gb = f.stat().st_size / (1024**3)
            print(f"    {f.name} ({size_gb:.1f} GB)")
        return True
    else:
        print(f"[!] No models found in {MODELS_DIR}")
        print()
        print("    Download a model and place it in the models/ directory.")
        print("    Recommended for your 4070 Ti Super (16GB VRAM):")
        print()
        print("    Llama 3 8B (balanced):")
        print("      https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF")
        print("      → Meta-Llama-3-8B-Instruct-Q4_K_M.gguf (4.9 GB)")
        print()
        print("    Llama 3 8B (higher quality, more VRAM):")
        print("      → Meta-Llama-3-8B-Instruct-Q6_K.gguf (6.6 GB)")
        print()
        print("    Llama 3.1 8B (newer, if available):")
        print("      https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF")
        print("      → Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf (~4.9 GB)")
        print()
        return False

def validate():
    """Quick validation that everything works."""
    try:
        from llama_cpp import Llama
        print("[✓] llama-cpp-python importable")
    except ImportError:
        print("[✗] llama-cpp-python not installed")
        return False

    ggufs = list(MODELS_DIR.glob("*.gguf"))
    if not ggufs:
        print("[!] No model files yet — download one to proceed")
        return False

    # Quick load test (first 100MB only to verify format)
    print(f"[*] Testing model load: {ggufs[0].name}...")
    try:
        from umbra_engine import UmbraEngine
        e = UmbraEngine(str(MODELS_DIR))
        if e.load(ggufs[0].stem):
            print("[✓] Model loads successfully")
            # Quick inference test
            r = e.generate(prompt="Say 'hello' in one word.", timeout=30)
            print(f"[✓] Inference works: {r['response'][:50]}")
            return True
        else:
            print("[✗] Model failed to load")
            return False
    except Exception as ex:
        print(f"[✗] Error: {ex}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("UMBRA ENGINE SETUP")
    print("=" * 50)
    print()

    # Step 1: Install
    try:
        from llama_cpp import Llama
        print("[✓] llama-cpp-python already installed")
    except ImportError:
        print("[*] Installing llama-cpp-python...")
        try:
            install_llama_cpp()
        except subprocess.CalledProcessError as e:
            print(f"[✗] Install failed: {e}")
            print("    Try manually: pip install llama-cpp-python")
            sys.exit(1)

    print()

    # Step 2: Check models
    has_model = check_models()
    print()

    # Step 3: Validate
    if has_model:
        print("[*] Validating setup...")
        if validate():
            print()
            print("=" * 50)
            print("SETUP COMPLETE ✓")
            print("=" * 50)
            print()
            print("To use: edit umbra_autonomous.py CONFIG:")
            print('  "engine": "umbra"  (instead of using ollama)')
            print()
            print("Or set environment variable:")
            print("  UMBRA_ENGINE=1 python umbra_web.py")
        else:
            print("[!] Validation failed — check errors above")
    else:
        print("[!] Download a model file, then run this script again")
