# Development GuidedEval runner readiness — 2026-09-05 V2

This is a new implementation record. It does not revise the frozen V1 pivot,
preflight, failed D3 gate, valid-negative C1N gate, or closed C2N state. No judge
inference or target generation has been performed by this runner as of this record.

## Implemented behavior

`scripts/run_rescue_guidedeval_development_v2.py` defaults to read-only readiness.
It verifies the exact existing V1 config, 180-row input plan, binding receipt,
safe dependencies and official source hashes. It does not invoke the older
preflight, which loads the full benchmark and original private target records.

The new runner scores only the 180 already-generated C1N seed-11 responses across
the existing four 45-response target/condition cells. It has no target-generation
interface and rejects a runtime contract that enables Primary A, Reserve B,
target generation, or reclassification of C1N.

The endpoint is explicitly `GUIDELINE_POINT_ZERO_VS_PRESENT`: zero matched rubric
points versus at least one matched rubric point. This is a specified zero cutoff;
it is not a claim of human-validated safety, absence of every possible harm, or
the standard GuidedBench binary ASR. The original endpoint module is unchanged.

The implementation loads the pinned official GuidedBench model, prompt-builder,
and parser modules directly, without importing the dataset package. A provider
refusal, incomplete or duplicated point vector, missing output, tool output,
non-`stop` completion, or truncated completion abstains. An unexpected returned
model also abstains for that recorded call and stops subsequent dispatch.
Free-form refusals that do not provide a complete vector fail the official parser;
there is no newly trained semantic refusal detector.

The transport supports explicitly configured chat-completions-compatible HTTPS
services and explicitly configured loopback HTTP services. This does not imply
that every provider API is compatible. No provider, model, credential, or billable
service has been selected automatically.

## Case preparation and preserved data boundary

The explicit `--prepare-development-cases` operation selects the same 45 C1N
source IDs already frozen in the safe input plan. The source is JSONL. The final
implementation checks its full byte SHA-256 before selection and again while
streaming. A byte-level ID selector skips unselected lines without decoding them
as text or JSON. Each selected case must match its existing canonical source-row
SHA-256. Live loading additionally checks guideline and payload identities.

The parent workflow performed this explicit preparation on 2026-09-05 and reported:

- bundle: `artifacts/rescue_guidedeval_development_v2/development_cases.jsonl`;
- cases: 45;
- SHA-256: `b0b803cb06800f5a931df90e64833c8de70ba54def57e2a9ff0f09b3763a208b`;
- target-response copies: 0;
- unselected cases decoded as JSON: false;
- unselected cases copied: false;
- network calls: 0.

The complete source file's bytes were accessed for integrity and ID selection.
This is deliberately distinguished from interpreting heldout case contents.
The 120 Primary A / Reserve B case contents were not decoded or copied, and no
heldout outcome was generated or inspected. Preparation is idempotent: an
existing identical bundle is reused, while a different bundle is not overwritten.

## Concrete execution workflow

Readiness, with no private-case or target-record reads:

```powershell
python scripts/run_rescue_guidedeval_development_v2.py --root .
```

The development bundle above is already prepared. Its explicit preparation
command, if an identical reconstruction is needed, is:

```powershell
python scripts/run_rescue_guidedeval_development_v2.py --root . --prepare-development-cases
```

Print the complete draft runtime contract:

```powershell
python scripts/run_rescue_guidedeval_development_v2.py --root . --print-contract-template
```

Copy that draft to a new runtime configuration. Use the prepared bundle hash
above. Supply the actual provider, exact endpoint, requested and expected-returned
model IDs, model snapshot/artifact evidence, authentication requirement, decoding
limits, per-request cost bound and overall budget. The runtime code and tests
are bound by SHA-256. Then freeze the contract before scoring any responses.
Draft placeholders or changed runtime files are rejected. An explicit free local
service can use a zero-dollar ceiling; paid services must have sufficient reserved
budget for the full 180-response panel for every judge.

Static contract validation requires the exact contract-file digest and reads no
private inputs:

```powershell
python scripts/run_rescue_guidedeval_development_v2.py --root . --contract configs/natural_language_localization/NEW_FROZEN_RUNTIME.json --contract-sha256 EXACT_FILE_SHA256
```

Appending `--execute` is the explicit live operation. It requires available frozen
credentials when authentication is enabled. All 45 case identities, 180 original
target-record identities, and request byte limits are checked before the first
paid request. Original response text is read from its existing private record,
used in memory, and not written to another target-response corpus.

## Checkpoints, output integrity and cost limits

Each response/judge request has an identity containing the contract hash, exact
plan-row hash, judge identity and request hash. A durable exclusive dispatch
marker is written before its single request. A completed immutable receipt is
reused on restart. An unfinished dispatch marker stops execution; it is never
automatically retried because the provider may already have processed/billed it.
The code disables HTTP redirects and automatic retries.

The private checkpoint stores only the judge's returned text plus safe projected
point results and hashes. It does not store request messages, prompts or copies
of original target responses. Private receipts stay under the already ignored
`artifacts/` directory. Publication uses exclusive hard-link creation, so two
processes cannot overwrite one another's checkpoint. A filesystem that does not
support this operation fails closed. The current local Windows filesystem passed
the fixture publication checks.

Safe output includes complete point vectors per judge, parse/error categories,
per-target/condition outcome counts, pointwise consensus outcome counts, consensus
matched-point bounds, and judge-pair point-agreement numerators/denominators.
Missing or malformed judge vectors are retained as abstentions. Aggregate output
is published only when the complete frozen panel is available; interruption
leaves the already-completed private receipts intact.

The run reserves `180 * sum(per_judge_request_cost_bound)` before dispatch and
cannot send more than one request for each planned response/judge pair. The
declared dollar bound relies on the selected provider's pricing and the supplied
input/token cost assumptions; it is not an independently enforced provider billing
limit. A provider-side spending cap should enforce the financial ceiling when
available. No real provider billing or transport behavior has been tested here.

## Verification and remaining work

The verification suite uses harmless fruit-question fixtures. It checks the
official parser, abstention conditions, exact source and contract binding,
selective case decoding, 45-case bundle validation, request bounds, interrupted
dispatch, idempotent resume, tamper detection, immutable publication and panel
disagreement. These checks establish implementation behavior only, not local
human calibration or scientific rescue success.

Final focused verification: **38 passed** (31 new runner tests plus 7 existing
endpoint tests); Ruff and bytecode compilation passed. Default readiness passed
against the real pinned safe artifacts. An `--execute` invocation without a
contract stopped at `MISSING_EXPLICIT_LIVE_CONTRACT` with no network calls.

The remaining resource dependency is an actual judge endpoint/model and its
credentials or local runtime, with an explicit spending budget. The implementation
cannot infer those choices from the existence of the prior no-inference preflight.
After the runtime is frozen, the 180 C1N responses can be measured for development
diagnosis. This does not repair the old gate.

Scientific acceptance/kill gates, target admission, prospective estimands,
admissible partitions and any later Primary A / Reserve B experiment require
their own prospective contracts. The runner deliberately makes no automatic
qualification or paper-acceptance decision. The published GuidedBench validation
is not local human calibration, and offline tests are not judge qualification.
