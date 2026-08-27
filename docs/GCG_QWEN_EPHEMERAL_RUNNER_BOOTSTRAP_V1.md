# GCG-Qwen Ephemeral Runner Bootstrap V1

## Purpose

This bootstrap crosses only the physical runner-registration boundary for the frozen GCG-Qwen protocol. It performs a local hardware and private-storage attestation, registers one ephemeral GitHub Actions runner, dispatches the attestation-only workflow, and exits after the runner handles one job.

It does **not** download Qwen model weights, materialize the differentiable Python environment, run a forward pass, optimize a GCG control, generate target-model responses, or open the signal-screen outcomes.

## Security boundary

The repository is public. Do not install a permanent unattended runner for this protocol. The provided script configures `--ephemeral`, uses the static labels `gpu,a100-80gb,private-research`, dispatches only `gcg_qwen_self_hosted_attestation.yml`, and removes the runner installation directory on exit.

`GH_TOKEN` is read only from the process environment. The script never enables shell tracing, never writes the GitHub token or registration token to a tracked file, clears the registration token after configuration, and removes temporary API response files.

The token must be authorized for this repository to:

- create a repository runner registration token;
- dispatch GitHub Actions workflows.

Use a short-lived credential and revoke it after the one-shot attestation.

## Frozen host requirements

The local preflight invokes `scripts/attest_gcg_qwen_self_hosted_runner.py` against the committed compute contract. It requires:

- Linux x86_64;
- two `NVIDIA A100 80GB PCIe` GPUs;
- at least 65,536 MiB free on each selected GPU;
- NVIDIA driver `>=525.60.13` and `<580.0.0`;
- MIG explicitly reported as `Disabled` on both GPUs;
- at least 64 GiB free in the private cache filesystem;
- private cache, virtual-environment, and work roots with mode `0700` outside the GitHub workspace.

The GitHub Actions runner archive is pinned to `v2.337.0` and verified against SHA-256 `70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613` before extraction.

## Execution

From a clean checkout of `agent/programmatic-agentharm-pivot` on the GPU host:

```bash
chmod 700 scripts/bootstrap_gcg_qwen_ephemeral_runner.sh
GH_TOKEN='SHORT_LIVED_TOKEN' \
  scripts/bootstrap_gcg_qwen_ephemeral_runner.sh
```

Prefer injecting `GH_TOKEN` through a secret manager or a non-persistent shell environment rather than placing it in shell history.

Optional private roots can be overridden before execution:

```bash
export GCG_PRIVATE_CACHE_ROOT="$HOME/.cache/gcg-qwen-private-v1"
export GCG_PRIVATE_VENV_ROOT="$HOME/.venvs/gcg-qwen-2.6.0-cu124"
export GCG_PRIVATE_WORK_ROOT="/tmp/h4rm3l-gcg-signal-screen-private-v1"
```

## Expected result

A successful one-shot host run produces and commits only the hash-only record:

```text
data/natural_language_localization/topology_micro_pilot_v1/
  gcg_qwen_self_hosted_runner_attestation_v1.safe.json
```

Its required status is:

```text
GCG_QWEN_SELF_HOSTED_RUNNER_ATTESTATION_PASS
```

The next authorized operation after that record exists is environment materialization plus a one-step gradient smoke on a synthetic non-harmful fixture. Full GCG optimization and the 36-generation signal screen remain blocked until that smoke passes.
