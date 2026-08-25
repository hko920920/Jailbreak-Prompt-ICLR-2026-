#!/usr/bin/env bash
set -Eeuo pipefail

: "${ROOT:?}"
: "${SOURCE_ROOT:?}"
: "${CONTRACT:?}"
: "${SAFE_DIR:?}"
: "${SAFE_RESULT:?}"
: "${PRIVATE_DIR:?}"
: "${MODEL_DIR:?}"
: "${TOOLS_DIR:?}"
: "${SERVER_URL:?}"

stage="initialization"
model_downloaded=false
server_ready=false
inference_performed=false
live_predictions_generated=false
server_pid=""

mkdir -p "$SAFE_DIR" "$PRIVATE_DIR" "$MODEL_DIR" "$TOOLS_DIR"
chmod 700 "$PRIVATE_DIR"

write_operational_failure() {
  local exit_code="$1"
  local line_number="$2"
  python - "$stage" "$exit_code" "$line_number" <<'PY'
import hashlib
import json
import os
import sys
from pathlib import Path

stage, exit_code, line_number = sys.argv[1:]
contract_path = Path(os.environ["CONTRACT"])
contract = json.loads(contract_path.read_text(encoding="utf-8"))
decision = contract["decision_gate"]
record = {
    "schema_version": "e1c-harmbench-live-result-v1",
    "status": "E1C_HARMBENCH_COMPONENT_OPERATIONAL_FAIL",
    "operational_pass": False,
    "scientific_pass": False,
    "paper_validity": False,
    "evidence_class": "DEVELOPMENT",
    "failure_stage": stage,
    "failure_exit_code": int(exit_code),
    "failure_line_number": int(line_number),
    "contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
    "next_authorized_operation": decision["on_operational_fail"],
    "model_weight_downloaded": os.environ.get("MODEL_DOWNLOADED", "false") == "true",
    "server_ready": os.environ.get("SERVER_READY", "false") == "true",
    "model_inference_performed": os.environ.get("INFERENCE_PERFORMED", "false") == "true",
    "harmbench_live_predictions_generated": (
        os.environ.get("LIVE_PREDICTIONS_GENERATED", "false") == "true"
    ),
    "new_harmful_attack_outputs_generated": False,
    "semantic_only_stage_a_opened": False,
    "cross_regime_stage_a_opened": False,
    "prior_evaluation_opened": False,
    "heldout_opened": False,
    "causal_oracle_opened": False,
    "keep_only_oracle_opened": False,
    "wavelet_used": False,
    "raw_text_recorded": False,
}
path = Path(os.environ["SAFE_RESULT"])
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

cleanup() {
  set +e
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" >/dev/null 2>&1 || true
    for _ in $(seq 1 30); do
      kill -0 "$server_pid" >/dev/null 2>&1 || break
      sleep 1
    done
    kill -9 "$server_pid" >/dev/null 2>&1 || true
  fi
  if [[ -d "$PRIVATE_DIR" ]]; then
    find "$PRIVATE_DIR" -type f -exec shred -u {} + >/dev/null 2>&1 || true
    rm -rf "$PRIVATE_DIR"
  fi
}

on_error() {
  local exit_code="$1"
  local line_number="$2"
  trap - ERR
  export MODEL_DOWNLOADED="$model_downloaded"
  export SERVER_READY="$server_ready"
  export INFERENCE_PERFORMED="$inference_performed"
  export LIVE_PREDICTIONS_GENERATED="$live_predictions_generated"
  write_operational_failure "$exit_code" "$line_number"
  cleanup
  exit 0
}

on_signal() {
  local signal_name="$1"
  trap - ERR TERM INT
  stage="workflow_${signal_name,,}_timeout_or_interrupt"
  export MODEL_DOWNLOADED="$model_downloaded"
  export SERVER_READY="$server_ready"
  export INFERENCE_PERFORMED="$inference_performed"
  export LIVE_PREDICTIONS_GENERATED="$live_predictions_generated"
  write_operational_failure 124 0
  cleanup
  exit 0
}

trap 'on_error "$?" "$LINENO"' ERR
trap 'on_signal TERM' TERM
trap 'on_signal INT' INT
trap cleanup EXIT

component_value() {
  python - "$1" <<'PY'
import json
import os
import sys
from pathlib import Path
value = json.loads(Path(os.environ["CONTRACT"]).read_text(encoding="utf-8"))
for key in sys.argv[1].split("."):
    value = value[key]
print(value)
PY
}

stage="verify_frozen_contract"
python - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"])
contract = json.loads(Path(os.environ["CONTRACT"]).read_text(encoding="utf-8"))
frozen_path = (
    root
    / "data/natural_language_localization/evaluator_panel_v1/"
      "e1c_harmbench_live_contract.safe.json"
)
frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
assert frozen["status"] == "E1C_HARMBENCH_LIVE_CONTRACT_FREEZE_PASS"
assert frozen["operational_pass"] is True
assert frozen["next_authorized_operation"] == (
    "EXECUTE_E1C_HARMBENCH_LIVE_REPRODUCTION_AND_INJECTION_CANARIES"
)
assert contract["execution_budget"]["expected_total_classifier_requests"] == 448
assert contract["execution_budget"]["workflow_timeout_minutes"] == 360
assert all(value is False for value in contract["sealed_boundaries"].values())
PY

stage="free_runner_disk"
sudo rm -rf /opt/hostedtoolcache/CodeQL >/dev/null 2>&1 || true
sudo rm -rf /usr/local/lib/android >/dev/null 2>&1 || true
sudo rm -rf /opt/ghc >/dev/null 2>&1 || true
df -h "$RUNNER_TEMP" || true

stage="download_llama_cpp_runtime"
llama_repo="$(component_value component.llama_cpp_repository)"
llama_tag="$(component_value component.llama_cpp_release_tag)"
llama_revision="$(component_value component.llama_cpp_revision)"
llama_asset="$(component_value component.llama_cpp_release_asset)"
ref_json="$(gh api "/repos/${llama_repo}/git/ref/tags/${llama_tag}")"
ref_type="$(jq -r '.object.type' <<<"$ref_json")"
ref_sha="$(jq -r '.object.sha' <<<"$ref_json")"
if [[ "$ref_type" == "tag" ]]; then
  ref_sha="$(gh api "/repos/${llama_repo}/git/tags/${ref_sha}" --jq '.object.sha')"
fi
test "$ref_sha" = "$llama_revision"
gh release download "$llama_tag" \
  --repo "$llama_repo" \
  --pattern "$llama_asset" \
  --dir "$TOOLS_DIR"
tar -xzf "$TOOLS_DIR/$llama_asset" -C "$TOOLS_DIR"
server_binary="$(find "$TOOLS_DIR" -type f -name llama-server | head -n 1)"
test -n "$server_binary"
chmod +x "$server_binary"
export LD_LIBRARY_PATH="$(dirname "$server_binary"):${LD_LIBRARY_PATH:-}"
"$server_binary" --version

stage="download_harmbench_runtime_artifact"
model_repo="$(component_value component.runtime_model_repository)"
model_revision="$(component_value component.runtime_model_revision)"
model_filename="$(component_value component.runtime_filename)"
model_sha256="$(component_value component.runtime_sha256)"
model_size="$(component_value component.runtime_size_bytes)"
model_path="$MODEL_DIR/$model_filename"
model_url="https://huggingface.co/${model_repo}/resolve/${model_revision}/${model_filename}?download=true"
curl -L --fail --retry 5 --retry-all-errors --retry-delay 5 \
  --connect-timeout 30 --speed-time 600 --speed-limit 1024 \
  -o "$model_path" "$model_url"
test "$(stat -c '%s' "$model_path")" = "$model_size"
test "$(sha256sum "$model_path" | cut -d' ' -f1)" = "$model_sha256"
model_downloaded=true
export MODEL_DOWNLOADED=true

stage="prepare_private_requests"
python scripts/run_evaluator_panel_e1c_harmbench_live.py prepare \
  --root "$ROOT" \
  --source-root "$SOURCE_ROOT" \
  --contract "$CONTRACT" \
  --private-output-dir "$PRIVATE_DIR" \
  --safe-output-dir "$SAFE_DIR"

stage="start_classifier_server"
server_log="$PRIVATE_DIR/llama-server.private.log"
server_port="${SERVER_URL##*:}"
server_args=(
  -m "$model_path"
  --alias harmbench-e1c
  --host 127.0.0.1
  --port "$server_port"
  -c "$(component_value component.context_tokens)"
  -t "$(component_value component.cpu_threads)"
  -np "$(component_value component.parallel_slots)"
)
if "$server_binary" --help 2>&1 | grep -q -- '--no-warmup'; then
  server_args+=(--no-warmup)
fi
nohup stdbuf -oL -eL "$server_binary" "${server_args[@]}" \
  >"$server_log" 2>&1 &
server_pid=$!
echo "$server_pid" > "$PRIVATE_DIR/llama-server.pid"

readiness_seconds=0
health_code="000"
for attempt in $(seq 1 360); do
  if ! kill -0 "$server_pid" >/dev/null 2>&1; then
    tail -n 200 "$server_log" >&2 || true
    exit 31
  fi
  health_code="$(curl -sS -o "$PRIVATE_DIR/health.txt" -w '%{http_code}' \
    "$SERVER_URL/health" || true)"
  if [[ "$health_code" == "200" ]]; then
    readiness_seconds=$((attempt * 5))
    break
  fi
  if (( attempt % 12 == 0 )); then
    ps -o pid,etimes,rss,vsz,stat,cmd -p "$server_pid" || true
    free -h || true
    tail -n 40 "$server_log" || true
  fi
  sleep 5
done
test "$health_code" = "200"
server_ready=true
export SERVER_READY=true
python - <<PY
import json
from pathlib import Path
record = {
    "schema_version": "e1c-harmbench-server-startup-safe-v1",
    "ready": True,
    "readiness_seconds": $readiness_seconds,
    "health_http_code": "$health_code",
    "runtime_sha256": "$model_sha256",
    "runtime_size_bytes": int("$model_size"),
    "raw_log_recorded": False,
}
Path("$SAFE_DIR/harmbench_server_startup.safe.json").write_text(
    json.dumps(record, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
: > "$server_log"

stage="evaluate_raw_and_hardened_full_selection"
inference_performed=true
live_predictions_generated=true
export INFERENCE_PERFORMED=true
export LIVE_PREDICTIONS_GENERATED=true
timeout 240m python scripts/run_evaluator_panel_e1c_harmbench_live.py evaluate \
  --root "$ROOT" \
  --contract "$CONTRACT" \
  --private-output-dir "$PRIVATE_DIR" \
  --safe-output-dir "$SAFE_DIR" \
  --server-url "$SERVER_URL"

stage="evaluate_hardened_repeatability"
timeout 60m python scripts/run_evaluator_panel_e1c_harmbench_live.py repeatability \
  --root "$ROOT" \
  --contract "$CONTRACT" \
  --private-output-dir "$PRIVATE_DIR" \
  --safe-output-dir "$SAFE_DIR" \
  --server-url "$SERVER_URL"

stage="evaluate_injection_canaries"
timeout 60m python scripts/run_evaluator_panel_e1c_harmbench_live.py canaries \
  --root "$ROOT" \
  --contract "$CONTRACT" \
  --private-output-dir "$PRIVATE_DIR" \
  --safe-output-dir "$SAFE_DIR" \
  --server-url "$SERVER_URL"

stage="finalize_scientific_gate"
set +e
python scripts/run_evaluator_panel_e1c_harmbench_live.py finalize \
  --root "$ROOT" \
  --contract "$CONTRACT" \
  --safe-output-dir "$SAFE_DIR" \
  --runtime-sha256 "$model_sha256" \
  --runtime-size-bytes "$model_size" \
  --safe-output "$SAFE_RESULT"
finalize_code=$?
set -e
if [[ "$finalize_code" != "0" && "$finalize_code" != "2" ]]; then
  exit "$finalize_code"
fi

stage="complete"
cleanup
trap - EXIT ERR TERM INT
exit 0
