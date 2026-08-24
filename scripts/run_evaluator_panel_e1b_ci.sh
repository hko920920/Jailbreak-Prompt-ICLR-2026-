#!/usr/bin/env bash
set -euo pipefail

: "${CONTRACT:=configs/natural_language_localization/evaluator_panel_e1b_wildguard_v1.json}"
: "${SAFE_OUTPUT:=artifacts/evaluator-panel-e1b/safe}"
: "${PRIVATE_OUTPUT:=/tmp/evaluator-panel-e1b/private}"
: "${RESULT:=${SAFE_OUTPUT}/e1b_wildguard.safe.json}"
: "${JBB_REVISION:=d8d87b8fdcb7806e3b4e45fffb2bc24aa6b17f32}"
: "${JBB_PATH:=data/judge-comparison.csv}"
: "${JBB_SHA256:=dacaf76a1057785f11b0fc6aa07b9a73cdab588319ddfc5e8cef2909e5b112a5}"
: "${WILDGUARD_MODEL_REVISION:=cbba4823f3e8020e5a74a5e29bf85072def6f2ff}"
: "${WILDGUARD_GGUF_EXPECTED:=0c11d34ecd7e0034621c956c65f7372f0dc159eca9112bd2b20011239fdc0247}"
: "${LLAMA_REVISION:=0177dcc7300bad8914bb838baabce87899812491}"
: "${LLAMA_RELEASE_TAG:=b10441}"
: "${LLAMA_ASSET:=llama-b10441-bin-ubuntu-x64.tar.gz}"
: "${HF_HUB_DISABLE_TELEMETRY:=1}"
: "${TOKENIZERS_PARALLELISM:=false}"

export CONTRACT SAFE_OUTPUT PRIVATE_OUTPUT RESULT
export HF_HUB_DISABLE_TELEMETRY TOKENIZERS_PARALLELISM

mkdir -p "$SAFE_OUTPUT" "$PRIVATE_OUTPUT"
server_pid=""

cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  if [[ -d "$PRIVATE_OUTPUT" ]]; then
    find "$PRIVATE_OUTPUT" -type f -print0 | xargs -0 -r shred -u
    rm -rf "$PRIVATE_OUTPUT"
  fi
  rm -rf \
    "$RUNNER_TEMP/hf-wildguard" \
    "$RUNNER_TEMP/wildguard-q8_0.gguf" \
    "$RUNNER_TEMP/llama-src" \
    "$RUNNER_TEMP/llama-bin"
}
trap cleanup EXIT

python -m pip install --upgrade pip
python -m pip install -e '.[dev,step3]'
ruff check \
  src/jbspan/evaluator_panel.py \
  scripts/run_evaluator_panel_e1b.py \
  scripts/run_gate1_step3b_wildguard_validation.py \
  tests/test_evaluator_panel.py \
  tests/test_evaluator_panel_e1b.py \
  tests/test_gate1_step3b_wildguard_validation.py
mypy src/jbspan
pytest \
  tests/test_evaluator_panel.py \
  tests/test_evaluator_panel_e1b.py \
  tests/test_gate1_step3b_wildguard_validation.py
python -m json.tool "$CONTRACT" >/dev/null
git diff --check

python - <<'PY'
import json
import os
from pathlib import Path

contract = json.loads(Path(os.environ["CONTRACT"]).read_text())
predecessor = contract["predecessor"]
e1a = json.loads(Path(predecessor["e1a_result_path"]).read_text())
assert contract["status"] == "FROZEN_BEFORE_E1B_LIVE_OUTPUTS"
assert contract["paper_validity"] is False
assert e1a["status"] == predecessor["required_status"]
assert e1a["next_authorized_operation"] == predecessor["required_next_operation"]
boundary = contract["claim_boundary"]
assert boundary["wildguard_is_selected_as_single_primary_judge"] is False
for key in (
    "stage_a_opened",
    "gate1_evaluation_30_opened",
    "gate2_heldout_opened",
    "causal_oracle_opened",
    "wavelet_used",
):
    assert boundary[key] is False
PY

python scripts/run_gate1_step3b_wildguard_validation.py preflight \
  --root . \
  --safe-output-dir "$SAFE_OUTPUT" \
  --github-env "$GITHUB_ENV"
test "$(jq -r '.access_ok' "$SAFE_OUTPUT/wildguard_preflight.json")" = "true"
test "$(jq -r '.model_revision' "$SAFE_OUTPUT/wildguard_preflight.json")" = \
  "$WILDGUARD_MODEL_REVISION"

source_csv="$RUNNER_TEMP/judge-comparison.csv"
source_url="https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors/resolve/${JBB_REVISION}/${JBB_PATH}?download=true"
curl --fail --location --retry 5 --retry-delay 3 \
  "$source_url" --output "$source_csv"
test "$(sha256sum "$source_csv" | cut -d' ' -f1)" = "$JBB_SHA256"

python scripts/run_gate1_step3b_wildguard_validation.py prepare \
  --root . \
  --source-csv "$source_csv" \
  --safe-output-dir "$SAFE_OUTPUT" \
  --private-output-dir "$PRIVATE_OUTPUT"
test "$(jq -r '.selection_count' \
  "$SAFE_OUTPUT/wildguard_design_manifest.json")" = "200"
test "$(jq -r '.selection_ids_sha256' \
  "$SAFE_OUTPUT/wildguard_design_manifest.json")" = \
  "f3a88da89ea5a814897f3925255e930cf40fdc2ce02952c6f46fbcc2cc200885"

sudo rm -rf \
  /usr/local/lib/android \
  /usr/share/dotnet \
  /opt/ghc \
  /usr/local/.ghcup \
  /opt/hostedtoolcache/CodeQL || true

df -h
release_json="$RUNNER_TEMP/llama-release.json"
curl --fail --location --retry 5 --retry-delay 3 \
  "https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/${LLAMA_RELEASE_TAG}" \
  --output "$release_json"
test "$(jq -r '.target_commitish' "$release_json")" = "$LLAMA_REVISION"
asset_url="$(jq -r --arg name "$LLAMA_ASSET" \
  '.assets[] | select(.name == $name) | .browser_download_url' \
  "$release_json")"
asset_digest="$(jq -r --arg name "$LLAMA_ASSET" \
  '.assets[] | select(.name == $name) | .digest' \
  "$release_json")"
archive="$RUNNER_TEMP/$LLAMA_ASSET"
curl --fail --location --retry 5 --retry-delay 5 \
  "$asset_url" --output "$archive"
test "sha256:$(sha256sum "$archive" | cut -d' ' -f1)" = "$asset_digest"
mkdir -p "$RUNNER_TEMP/llama-bin"
tar -xzf "$archive" -C "$RUNNER_TEMP/llama-bin"
llama_server="$(find "$RUNNER_TEMP/llama-bin" -type f \
  -name llama-server -print -quit)"
test -x "$llama_server"
lib_dirs="$(find "$RUNNER_TEMP/llama-bin" -type f -name '*.so*' -printf '%h\n' \
  | sort -u | paste -sd: -)"
export LD_LIBRARY_PATH="${lib_dirs}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

llama_source="$RUNNER_TEMP/llama-src"
git init -q "$llama_source"
git -C "$llama_source" remote add origin https://github.com/ggml-org/llama.cpp.git
git -C "$llama_source" fetch -q --depth 1 origin "$LLAMA_REVISION"
git -C "$llama_source" checkout -q --detach FETCH_HEAD
test "$(git -C "$llama_source" rev-parse HEAD)" = "$LLAMA_REVISION"
python -m pip install -r \
  "$llama_source/requirements/requirements-convert_hf_to_gguf.txt"

export HF_HOME="$RUNNER_TEMP/hf-wildguard"
python - <<'PY'
import hashlib
import json
import os
from pathlib import Path

from huggingface_hub import snapshot_download

identity = json.loads(
    (Path(os.environ["SAFE_OUTPUT"]) / "wildguard_preflight.json").read_text()
)
if identity["model_revision"] != os.environ["WILDGUARD_MODEL_REVISION"]:
    raise SystemExit("WildGuard immutable revision mismatch")
snapshot = Path(
    snapshot_download(
        repo_id=identity["official_model_repository"],
        revision=identity["model_revision"],
        token=os.environ["HF_TOKEN"],
        cache_dir=Path(os.environ["HF_HOME"]),
    )
)

def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

for item in identity["files"]:
    path = snapshot / item["filename"]
    if not path.is_file():
        raise SystemExit(f"missing WildGuard file: {item['filename']}")
    expected = item.get("sha256")
    if expected and digest(path) != expected:
        raise SystemExit(f"WildGuard digest mismatch: {item['filename']}")
    expected_size = item.get("size")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise SystemExit(f"WildGuard size mismatch: {item['filename']}")
with Path(os.environ["GITHUB_ENV"]).open("a") as handle:
    handle.write(f"WILDGUARD_MODEL_DIR={snapshot}\n")
Path(os.environ["RUNNER_TEMP"], "wildguard-model-dir.txt").write_text(str(snapshot))
PY
wildguard_model_dir="$(cat "$RUNNER_TEMP/wildguard-model-dir.txt")"

wildguard_gguf="$RUNNER_TEMP/wildguard-q8_0.gguf"
python "$llama_source/convert_hf_to_gguf.py" \
  "$wildguard_model_dir" \
  --outfile "$wildguard_gguf" \
  --outtype q8_0
test -s "$wildguard_gguf"
observed_gguf_sha="$(sha256sum "$wildguard_gguf" | cut -d' ' -f1)"
test "$observed_gguf_sha" = "$WILDGUARD_GGUF_EXPECTED"
rm -rf "$RUNNER_TEMP/hf-wildguard"
df -h

mkdir -p "$RUNNER_TEMP/wildguard-server"
nohup env LD_LIBRARY_PATH="$LD_LIBRARY_PATH" "$llama_server" \
  -m "$wildguard_gguf" \
  --alias wildguard \
  --host 127.0.0.1 \
  --port 8080 \
  -c 4096 \
  -t 4 \
  -np 1 \
  >"$RUNNER_TEMP/wildguard-server/server.log" 2>&1 &
server_pid=$!

ready=0
for _ in $(seq 1 240); do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    tail -n 100 "$RUNNER_TEMP/wildguard-server/server.log"
    exit 1
  fi
  if [[ "$(curl -sS -o /dev/null -w '%{http_code}' \
    http://127.0.0.1:8080/health || true)" == "200" ]]; then
    ready=1
    break
  fi
  sleep 5
done
test "$ready" = "1"

timeout 210m python scripts/run_gate1_step3b_wildguard_validation.py evaluate \
  --root . \
  --subset selection \
  --private-output-dir "$PRIVATE_OUTPUT" \
  --safe-output-dir "$SAFE_OUTPUT" \
  --server-url http://127.0.0.1:8080

timeout 75m python scripts/run_evaluator_panel_e1b.py canaries \
  --root . \
  --contract "$CONTRACT" \
  --server-url http://127.0.0.1:8080 \
  --private-output-dir "$PRIVATE_OUTPUT" \
  --safe-output-dir "$SAFE_OUTPUT"

kill "$server_pid" 2>/dev/null || true
wait "$server_pid" 2>/dev/null || true
server_pid=""

set +e
python scripts/run_evaluator_panel_e1b.py finalize \
  --root . \
  --contract "$CONTRACT" \
  --live-safe-predictions "$SAFE_OUTPUT/wildguard_selection.safe.jsonl" \
  --live-private-predictions "$PRIVATE_OUTPUT/wildguard_selection.private.jsonl" \
  --live-metrics "$SAFE_OUTPUT/wildguard_selection_metrics.json" \
  --canary-summary "$SAFE_OUTPUT/wildguard_canary_summary.json" \
  --gguf-sha256 "$observed_gguf_sha" \
  --safe-output "$RESULT"
finalize_code=$?
set -e

test -f "$RESULT"
python - <<'PY'
import json
import os
from pathlib import Path

result = json.loads(Path(os.environ["RESULT"]).read_text())
assert result["paper_validity"] is False
assert result["wildguard_single_primary_judge_selected"] is False
for key in (
    "stage_a_opened",
    "gate1_evaluation_30_opened",
    "gate2_heldout_opened",
    "causal_oracle_opened",
    "wavelet_used",
):
    assert result[key] is False
if result["operational_pass"] is True:
    assert result["status"] == "EVALUATOR_PANEL_E1B_WILDGUARD_PASS"
    assert result["next_authorized_operation"] == (
        "E1C_HARMBENCH_COMPONENT_REPRODUCTION_AND_CANARIES"
    )
PY

python - <<'PY'
import json
import os
from pathlib import Path

safe = Path(os.environ["SAFE_OUTPUT"])
private = Path(os.environ["PRIVATE_OUTPUT"])
forbidden_keys = {
    "prompt",
    "response",
    "raw_output",
    "judge_prompt",
    "human_request",
    "assistant_response",
}
safe_text = "\n".join(
    path.read_text(encoding="utf-8")
    for path in safe.rglob("*")
    if path.is_file()
)

def load_safe_values(path: Path):
    if path.suffix == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return [json.loads(path.read_text(encoding="utf-8"))]

for path in safe.rglob("*.json*"):
    for value in load_safe_values(path):
        stack = [value]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                leaked = forbidden_keys.intersection(item)
                if leaked:
                    raise SystemExit(f"unsafe safe-artifact keys: {sorted(leaked)}")
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
if private.exists():
    for path in private.rglob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            for key in forbidden_keys:
                value = row.get(key)
                if isinstance(value, str) and len(value) >= 16 and value in safe_text:
                    raise SystemExit(f"private text leaked through {key}")
PY

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  python - <<'PY'
import json
import os
from pathlib import Path

result = json.loads(Path(os.environ["RESULT"]).read_text())
live = result["live_reproduction"]
hardened = result["live_canaries"]["summary"]["mode_summaries"]["hardened_template"]
with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as handle:
    handle.write("# Evaluator Panel E1B — WildGuard\n\n")
    handle.write(f"- status: **{result['status']}**\n")
    handle.write(f"- exact 200-example reproduction: **{live['pass']}**\n")
    handle.write(
        "- predecessor safe predictions byte-identical: "
        f"**{live['safe_predictions_byte_identical']}**\n"
    )
    handle.write(
        "- strict parser matches legacy predictions: "
        f"**{live['strict_parser_predictions_match_legacy']}**\n"
    )
    handle.write(
        "- hardened canary incorrect decisions: "
        f"**{hardened['incorrect_auto_decision_count']}**\n"
    )
    handle.write(
        "- hardened canary coverage: "
        f"**{hardened['auto_decision_coverage']:.3f}**\n"
    )
    handle.write("- WildGuard selected as single primary judge: **false**\n")
    handle.write("- Stage A / causal oracle / wavelet: **closed / closed / closed**\n")
PY
fi

exit "$finalize_code"
