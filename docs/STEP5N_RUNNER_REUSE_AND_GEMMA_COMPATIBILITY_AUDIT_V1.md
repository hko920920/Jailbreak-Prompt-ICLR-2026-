# Step 5N Runner Reuse and Gemma Compatibility Audit V1

Date: 2026-09-05 (Asia/Seoul)  
Status: **STATIC AUDIT PASS; NEW TARGET-SCOPED RUNNERS REQUIRED; NO SCIENTIFIC AUTHORITY**

## Outcome

The exact topology core and h4rm3l typed renderer can be reused, but neither D3 scientific runner
is a valid drop-in C1N/C2N runner. The correct implementation route is to preserve D3 byte-for-byte
as development evidence and create new, versioned, target-scoped runners after the author accepts
NARROW and selects the target pair.

This is an implementation finding, not a model qualification or paper result. No model was
downloaded, no target or evaluator was called, and no confirmatory output was opened.

## What may be reused unchanged

- `src/jbspan/topology.py`: finite-lattice enumeration, recovery decisions, strict-subset
  minimality, and exact-topology evaluation;
- `src/jbspan/topology_adaptive.py`: first-valid-harmful-witness short-circuit semantics;
- `run_topology_d2_micro_pilot.build_one_h4_materialization_family`: the frozen source-native
  three-unit renderer;
- through new wrappers only: atomic persistence, private-record hashing, safe projections,
  llama.cpp invocation, evaluator prompt/parsing primitives, the fixed panel rule, and the
  capability-control rendering pattern.

## Why D3 cannot be reused as a drop-in runner

1. The D3 screen and legacy funnel hard-code both `h4rm3l` and `DeepInception`, 15 development
   payloads, and development-specific routing.
2. The D3 topology runner hard-codes 9 h4rm3l plus 3 DeepInception instances and the corresponding
   888 nonempty subset-neutralizer groups.
3. The inherited P3 runtime resolves one `target_model` from a parent contract; it cannot safely
   switch between two frozen target artifacts.
4. Existing phase filenames are keyed by seed but not by target, so naïve two-model reuse would
   collide.
5. D3 empty baselines refer to D3 screen records. C2N must reuse only the matching C1N baseline for
   the same target, payload, and seed.
6. Editing a frozen, post-outcome D3 runner or contract into the confirmatory population would
   destroy the prospective evidence boundary.

## Required new layers after authorization

- one target registry and harmless-admission runner binding each selected model and runtime by
  revision, size, and SHA-256;
- a C1N h4rm3l-only screen with `target_id` in every pair, plan, record, path, and result identity;
- a C2N exact runner consuming every eligible C1N target-payload pair without a topology cap;
- a C3N runner for every reported edge and its strict-subset downward closure at the seven frozen
  seeds;
- target-scoped atomic checkpoints and resume audits that never restart completed calls;
- separate independent reconstruction scripts, frozen configs, safe output roots, and gitignored
  private roots.

Direct responses may not be shared across target models. Empty responses may be reused only within
the same target-payload-seed identity. The final target dimension must be present before record IDs
are hashed.

## Gemma compatibility boundary

The pinned llama.cpp `b10441` CLI still matches its expected SHA-256. Static scanning found Gemma4
markers in `llama-common.dll`, `llama.dll`, and `mtmd.dll`, and the matching upstream revision has
Gemma4 source implementations. This makes a harmless test on the existing runtime reasonable.

It does **not** prove that the official Gemma 4 E4B Q4 artifact loads within local VRAM, applies the
correct embedded chat template, extracts one clean response, meets the input/context budget, or is
deterministic enough for the frozen protocol. Those remain Step 5N harmless-admission gates after
authorization. If `b10441` fails there, a replacement runtime must be frozen first and both final
targets requalified on it before any C1N scientific output.

## Reproducible record

- config:
  `configs/natural_language_localization/step5n_runner_reuse_audit_v1.json`;
- config SHA-256:
  `90424c987f571bedaccf30d75e17c9d8f30fd1546f06d4d05b0db67bdc7d4a14`;
- script: `scripts/audit_step5n_runner_reuse.py`;
- script SHA-256:
  `4660bd41773b32bb67bbd818bdf619dc5ff9215ce69019b75000dc3b3335c561`;
- safe result:
  `data/natural_language_localization/step5n_runner_reuse_audit_v1/runner_reuse_audit.safe.json`;
- safe result SHA-256:
  `cb6b68c3057ffb488feccac49a2cf168a263ed9ec74e2327909df5c866826156`;
- result identity:
  `43e7486c8dc1ef212f868adfb72fafb38f6f6b740448f2fcf3e944f9e8f1cff5`;
- source audits: 8/8 passed;
- focused tests: 4/4 passed;
- Ruff: passed.

Both this result and the upstream draft-preflight receipt are byte-stable on identical reruns; a
nonidentical reconstruction is refused instead of silently overwriting the recorded PASS.

Next operation: wait for explicit author acceptance of h4rm3l-only NARROW and the target pair, then
materialize new frozen admission/C1N--C3N contracts and target-scoped runners. Do not modify D3.
