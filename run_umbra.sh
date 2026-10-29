#!/usr/bin/env bash
# Launch UMBRA inside a bubblewrap sandbox (the same kernel isolation Flatpak uses).
#
# Inside the sandbox UMBRA can see ONLY:
#   - this project's code, .venv and the model file   (read-only)
#   - data/ and env/                                   (writable)
#   - the GPU device files
# It has NO network (not even the LAN), NO home folder, NO ~/.config (where the
# login lives), NO other projects, and credential files in the project are blanked.
# The browser reaches the web app only through tools/gatekeeper.py, which runs
# outside, checks the login, and talks to the app over a private socket file.
# Web research goes through tools/fetcher.py (outside): allowlisted https sites
# only (~/.config/umbra/fetch_allowlist.txt), rate-limited, logged outside.
# Offline Wikipedia (~/.local/share/umbra/zim/*.zim) is mounted read-only.
#
# Usage: ./run_umbra.sh web | dry-run | status | escape-test | research [runs]
cd "$(dirname "$0")" || exit 1
ROOT="$PWD"
NV=".venv/lib/python3.12/site-packages/nvidia"
SOCK="$ROOT/data/run/umbra.sock"
FETCH_SOCK="$ROOT/data/run/fetch.sock"
ZIM_DIR="$HOME/.local/share/umbra/zim"
mkdir -p "$ROOT/data/run" "$ROOT/env"

MODEL_ARGS=()
for m in models/*.gguf; do
  [ -e "$m" ] || continue
  real="$(readlink -f "$m")"
  MODEL_ARGS+=(--ro-bind "$real" "$real")
done

# Blank out credential files that live inside the project
MASK_ARGS=()
for f in credentials.json data/credentials.json data/access_credentials.json data/login.json; do
  [ -e "$ROOT/$f" ] && MASK_ARGS+=(--ro-bind /dev/null "$ROOT/$f")
done

ZIM_ARGS=()
[ -d "$ZIM_DIR" ] && ZIM_ARGS=(--ro-bind "$ZIM_DIR" "$ZIM_DIR")

GPU_ARGS=()
for d in /dev/nvidia*; do
  [ -e "$d" ] && GPU_ARGS+=(--dev-bind "$d" "$d")
done
[ -d /dev/nvidia-caps ] && GPU_ARGS+=(--dev-bind /dev/nvidia-caps /dev/nvidia-caps)

sandbox() {
  bwrap \
    --unshare-all --die-with-parent --new-session --hostname umbra-sandbox \
    --ro-bind /usr /usr \
    --symlink usr/lib /lib --symlink usr/lib64 /lib64 --symlink usr/bin /bin --symlink usr/sbin /sbin \
    --ro-bind /etc/ld.so.cache /etc/ld.so.cache \
    --ro-bind-try /etc/localtime /etc/localtime \
    --ro-bind-try /etc/alternatives /etc/alternatives \
    --ro-bind /sys/devices /sys/devices --ro-bind /sys/bus /sys/bus --ro-bind-try /sys/module/nvidia /sys/module/nvidia \
    --proc /proc --dev /dev "${GPU_ARGS[@]}" \
    --tmpfs /tmp \
    --ro-bind "$ROOT" "$ROOT" \
    --tmpfs "$ROOT/.git" \
    --bind "$ROOT/data" "$ROOT/data" \
    --bind "$ROOT/env" "$ROOT/env" \
    "${MASK_ARGS[@]}" "${MODEL_ARGS[@]}" "${ZIM_ARGS[@]}" \
    --clearenv \
    --setenv HOME /tmp --setenv PATH /usr/bin:/bin --setenv PYTHONDONTWRITEBYTECODE 1 \
    --setenv LD_LIBRARY_PATH "$ROOT/$NV/cuda_runtime/lib:$ROOT/$NV/cublas/lib" \
    --setenv UMBRA_SOCKET "$SOCK" --setenv UMBRA_ZIM_DIR "$ZIM_DIR" \
    --chdir "$ROOT" \
    "$@"
}

case "${1:-dry-run}" in
  web)
    rm -f "$SOCK" "$FETCH_SOCK"
    python3 tools/fetcher.py "$FETCH_SOCK" &
    FETCHER=$!
    sandbox .venv/bin/python umbra_web.py &
    APP=$!
    trap 'kill $APP $FETCHER 2>/dev/null; rm -f "$SOCK" "$FETCH_SOCK"' EXIT INT TERM
    for _ in $(seq 1 120); do [ -S "$SOCK" ] && break; kill -0 $APP 2>/dev/null || exit 1; sleep 1; done
    [ -S "$SOCK" ] || { echo "[UMBRA] Web app did not start (no socket after 120 s)."; exit 1; }
    python3 tools/gatekeeper.py "$SOCK"
    ;;
  dry-run) sandbox .venv/bin/python core/umbra_autonomous.py --mode=dry-run ;;
  research) sandbox .venv/bin/python tools/research_run.py "${2:-10}" ;;
  status)  sandbox .venv/bin/python core/umbra_autonomous.py --mode=status ;;
  escape-test)
    rm -f "$FETCH_SOCK"
    python3 tools/fetcher.py "$FETCH_SOCK" >/dev/null &
    FETCHER=$!
    trap 'kill $FETCHER 2>/dev/null; rm -f "$FETCH_SOCK"' EXIT INT TERM
    sleep 1
    sandbox .venv/bin/python tools/escape_test.py
    ;;
  *) echo "Usage: $0 [web|dry-run|status|escape-test|research [runs]]"; exit 1 ;;
esac
