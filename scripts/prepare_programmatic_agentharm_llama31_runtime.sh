#!/usr/bin/env bash
set -euo pipefail

: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"
: "${RUNTIME_CONFIG:?RUNTIME_CONFIG is required}"
: "${ATTACK_SOURCE:?ATTACK_SOURCE is required}"
: "${MODEL_DIR:?MODEL_DIR is required}"

export HF_HOME="${HF_HOME:-/tmp/huggingface}"
export HF_HUB_DISABLE_TELEMETRY="${HF_HUB_DISABLE_TELEMETRY:-1}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"

curl --fail --location --retry 5 --retry-delay 3 \
  'https://raw.githubusercontent.com/mdoumbouya/h4rm3l/e6f58a1a1e56c1a95b26b06aa4fe393ee2240dbd/experiments/experiment_116_bandi_synthesis/config/benchmark_reference_programs.csv' \
  --output "$ATTACK_SOURCE"
echo 'b4c07b11c9e92ecd332807e8ba32d8fe028b59f4c3499f72670d44105626ef07  /tmp/h4rm3l-reference-programs.csv' \
  | sha256sum --check --strict

archive="$RUNNER_TEMP/llama-b10441-bin-ubuntu-x64.tar.gz"
runtime_root="$RUNNER_TEMP/llama-b10441"
mkdir -p "$runtime_root"
curl --fail --location --retry 5 --retry-delay 5 \
  'https://github.com/ggml-org/llama.cpp/releases/download/b10441/llama-b10441-bin-ubuntu-x64.tar.gz' \
  --output "$archive"
tar -xzf "$archive" -C "$runtime_root"
server="$(find "$runtime_root" -type f -name 'llama-server' -print -quit)"
test -n "$server"
chmod +x "$server"
lib_dirs="$(find "$runtime_root" -type f -name '*.so*' -printf '%h\n' \
  | sort -u | paste -sd: -)"
export LLAMA_SERVER="$server"
export LD_LIBRARY_PATH="$lib_dirs"
echo "LLAMA_SERVER=$LLAMA_SERVER" >> "$GITHUB_ENV"
echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH" >> "$GITHUB_ENV"
"$LLAMA_SERVER" --version

mkdir -p "$MODEL_DIR"
python - <<'PY'
import hashlib
import json
import os
from pathlib import Path

from huggingface_hub import hf_hub_download

config = json.loads(Path(os.environ["RUNTIME_CONFIG"]).read_text())
target = config["target"]
items = target["gguf_files"]
if len(items) != 1:
    raise SystemExit("second-model contract must contain exactly one GGUF")
item = items[0]
path = Path(
    hf_hub_download(
        repo_id=target["gguf_repo_id"],
        revision=target["gguf_revision"],
        filename=item["filename"],
        local_dir=Path(os.environ["MODEL_DIR"]),
    )
)
digest = hashlib.sha256()
with path.open("rb") as handle:
    for block in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(block)
if digest.hexdigest() != item["sha256"]:
    raise SystemExit("Llama 3.1 model SHA-256 mismatch")
if path.stat().st_size != item["size"]:
    raise SystemExit("Llama 3.1 model size mismatch")
with Path(os.environ["GITHUB_ENV"]).open("a") as handle:
    handle.write(f"MODEL_PATH={path}\n")
print(f"verified immutable GGUF: {path.name}")
PY

MODEL_PATH="$(tail -n 1 "$GITHUB_ENV" | sed 's/^MODEL_PATH=//')"
export MODEL_PATH
mkdir -p "$RUNNER_TEMP/llama-server"
nohup "$LLAMA_SERVER" \
  -m "$MODEL_PATH" \
  --alias meta-llama-3.1-8b-instruct \
  --jinja \
  --host 127.0.0.1 \
  --port 8080 \
  -c 8192 \
  -t 4 \
  -np 1 \
  >"$RUNNER_TEMP/llama-server/server.log" 2>&1 &
echo "$!" >"$RUNNER_TEMP/llama-server/pid"

ready=0
for _ in $(seq 1 180); do
  if ! kill -0 "$(cat "$RUNNER_TEMP/llama-server/pid")" 2>/dev/null; then
    echo 'llama-server exited before readiness'
    head -n 120 "$RUNNER_TEMP/llama-server/server.log"
    exit 1
  fi
  status="$(curl -sS -o /dev/null -w '%{http_code}' \
    http://127.0.0.1:8080/health || true)"
  if [ "$status" = '200' ]; then
    ready=1
    break
  fi
  sleep 5
done
if [ "$ready" != '1' ]; then
  echo 'llama-server did not become ready'
  head -n 120 "$RUNNER_TEMP/llama-server/server.log"
  exit 1
fi
