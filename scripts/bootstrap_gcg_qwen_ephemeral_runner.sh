#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

readonly DEFAULT_REPOSITORY="hko920920/Jailbreak-Prompt-ICLR-2026-"
readonly DEFAULT_BRANCH="agent/programmatic-agentharm-pivot"
readonly ATTESTATION_WORKFLOW="gcg_qwen_self_hosted_attestation.yml"
readonly RUNNER_VERSION="2.337.0"
readonly RUNNER_ARCHIVE="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
readonly RUNNER_ARCHIVE_SHA256="70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613"
readonly CUSTOM_LABELS="gpu,a100-80gb,private-research"
readonly CONFIG_PATH="configs/natural_language_localization/gcg_qwen_differentiable_compute_contract_v1.json"
readonly ATTEST_SCRIPT="scripts/attest_gcg_qwen_self_hosted_runner.py"

REPOSITORY="${GCG_GITHUB_REPOSITORY:-$DEFAULT_REPOSITORY}"
TARGET_BRANCH="${GCG_TARGET_BRANCH:-$DEFAULT_BRANCH}"
RUNNER_BASE="${GCG_RUNNER_BASE:-$HOME/.local/share/gcg-qwen-ephemeral-runners}"
RUNNER_NAME="${GCG_RUNNER_NAME:-gcg-qwen-ephemeral-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUNNER_INSTANCE=""
REGISTRATION_RESPONSE=""
DISPATCH_RESPONSE=""
REGISTRATION_TOKEN=""

log() {
  printf '[gcg-qwen-bootstrap] %s\n' "$*" >&2
}

fail() {
  log "ERROR: $*"
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

secure_remove() {
  local path="${1:-}"
  [[ -n "$path" && -e "$path" ]] || return 0
  chmod -R u+rwX,go-rwx "$path" 2>/dev/null || true
  rm -rf -- "$path"
}

cleanup() {
  local status=$?
  REGISTRATION_TOKEN=""
  secure_remove "$REGISTRATION_RESPONSE"
  secure_remove "$DISPATCH_RESPONSE"
  if [[ -n "$RUNNER_INSTANCE" ]]; then
    case "$RUNNER_INSTANCE" in
      "$RUNNER_BASE"/*) secure_remove "$RUNNER_INSTANCE" ;;
      *) log "refusing to remove unexpected runner path" ;;
    esac
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

[[ "$EUID" -ne 0 ]] || fail "run as a dedicated non-root service account"
[[ -n "${GH_TOKEN:-}" ]] || fail "GH_TOKEN must be provided through the environment"
[[ "$REPOSITORY" == */* ]] || fail "invalid owner/repository value"
[[ -f "$CONFIG_PATH" ]] || fail "run from the frozen research repository root"
[[ -f "$ATTEST_SCRIPT" ]] || fail "attestation script is missing"

for command_name in curl git nvidia-smi python3 sha256sum tar; do
  require_command "$command_name"
done

case "$(uname -s)" in
  Linux) ;;
  *) fail "the frozen runner contract requires Linux" ;;
esac
case "$(uname -m)" in
  x86_64 | amd64) ;;
  *) fail "the frozen runner contract requires x86_64" ;;
esac

current_branch="$(git branch --show-current)"
[[ "$current_branch" == "$TARGET_BRANCH" ]] || \
  fail "checkout branch $TARGET_BRANCH before bootstrapping"
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || \
  fail "tracked working tree must be clean"

mkdir -p "$RUNNER_BASE"
chmod 0700 "$RUNNER_BASE"
RUNNER_INSTANCE="$RUNNER_BASE/$RUNNER_NAME"
mkdir -p "$RUNNER_INSTANCE"
chmod 0700 "$RUNNER_INSTANCE"

export RUNNER_NAME
export GCG_PRIVATE_CACHE_ROOT="${GCG_PRIVATE_CACHE_ROOT:-$HOME/.cache/gcg-qwen-private-v1}"
export GCG_PRIVATE_VENV_ROOT="${GCG_PRIVATE_VENV_ROOT:-$HOME/.venvs/gcg-qwen-2.6.0-cu124}"
export GCG_PRIVATE_WORK_ROOT="${GCG_PRIVATE_WORK_ROOT:-/tmp/h4rm3l-gcg-signal-screen-private-v1}"
mkdir -p "$GCG_PRIVATE_CACHE_ROOT" "$GCG_PRIVATE_VENV_ROOT" "$GCG_PRIVATE_WORK_ROOT"
chmod 0700 "$GCG_PRIVATE_CACHE_ROOT" "$GCG_PRIVATE_VENV_ROOT" "$GCG_PRIVATE_WORK_ROOT"

local_attestation="$GCG_PRIVATE_WORK_ROOT/bootstrap_runner_attestation.safe.json"
log "checking the frozen two-A100, memory, driver, disk, and MIG-disabled contract"
python3 "$ATTEST_SCRIPT" \
  --config "$CONFIG_PATH" \
  --workspace "$PWD" \
  --output "$local_attestation"
python3 - "$local_attestation" <<'PY'
import json
import sys
from pathlib import Path

record = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if record.get("status") != "GCG_QWEN_SELF_HOSTED_RUNNER_ATTESTATION_PASS":
    raise SystemExit("local hardware attestation did not pass")
if record.get("model_weight_downloaded") is not False:
    raise SystemExit("attestation boundary violation")
if record.get("attack_optimization_performed") is not False:
    raise SystemExit("attestation boundary violation")
PY
rm -f -- "$local_attestation"

archive_path="$RUNNER_INSTANCE/$RUNNER_ARCHIVE"
runner_url="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_ARCHIVE}"
log "downloading pinned GitHub Actions runner v${RUNNER_VERSION}"
curl --fail --location --silent --show-error \
  --output "$archive_path" "$runner_url"
printf '%s  %s\n' "$RUNNER_ARCHIVE_SHA256" "$archive_path" | sha256sum --check --status || \
  fail "runner archive SHA-256 mismatch"
tar -xzf "$archive_path" -C "$RUNNER_INSTANCE"
rm -f -- "$archive_path"

api_root="https://api.github.com/repos/${REPOSITORY}"
REGISTRATION_RESPONSE="$(mktemp "$RUNNER_INSTANCE/registration.XXXXXX")"
registration_status="$(
  curl --silent --show-error \
    --output "$REGISTRATION_RESPONSE" \
    --write-out '%{http_code}' \
    --request POST \
    --header "Accept: application/vnd.github+json" \
    --header "Authorization: Bearer ${GH_TOKEN}" \
    --header "X-GitHub-Api-Version: 2022-11-28" \
    "$api_root/actions/runners/registration-token"
)"
[[ "$registration_status" == "201" ]] || \
  fail "GitHub runner registration-token request failed with HTTP $registration_status"
REGISTRATION_TOKEN="$(
  python3 - "$REGISTRATION_RESPONSE" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("token", "")
if not isinstance(value, str) or not value:
    raise SystemExit(1)
print(value, end="")
PY
)" || fail "registration-token response was invalid"
rm -f -- "$REGISTRATION_RESPONSE"
REGISTRATION_RESPONSE=""

log "configuring an ephemeral runner with frozen labels"
(
  cd "$RUNNER_INSTANCE"
  ./config.sh \
    --url "https://github.com/${REPOSITORY}" \
    --token "$REGISTRATION_TOKEN" \
    --name "$RUNNER_NAME" \
    --labels "$CUSTOM_LABELS" \
    --work _work \
    --unattended \
    --ephemeral \
    --replace
)
REGISTRATION_TOKEN=""

DISPATCH_RESPONSE="$(mktemp "$RUNNER_INSTANCE/dispatch.XXXXXX")"
dispatch_payload="$(
  python3 - "$TARGET_BRANCH" <<'PY'
import json
import sys

print(
    json.dumps(
        {
            "ref": sys.argv[1],
            "inputs": {"attestation_only": "true"},
        },
        separators=(",", ":"),
    ),
    end="",
)
PY
)"
log "dispatching the attestation-only workflow"
dispatch_status="$(
  curl --silent --show-error \
    --output "$DISPATCH_RESPONSE" \
    --write-out '%{http_code}' \
    --request POST \
    --header "Accept: application/vnd.github+json" \
    --header "Authorization: Bearer ${GH_TOKEN}" \
    --header "X-GitHub-Api-Version: 2022-11-28" \
    --header "Content-Type: application/json" \
    --data "$dispatch_payload" \
    "$api_root/actions/workflows/$ATTESTATION_WORKFLOW/dispatches"
)"
[[ "$dispatch_status" == "204" ]] || \
  fail "attestation workflow dispatch failed with HTTP $dispatch_status"
rm -f -- "$DISPATCH_RESPONSE"
DISPATCH_RESPONSE=""
dispatch_payload=""

log "starting the one-job runner; it will deregister automatically after attestation"
(
  cd "$RUNNER_INSTANCE"
  ./run.sh
)
log "ephemeral runner exited after its single scheduled job"
