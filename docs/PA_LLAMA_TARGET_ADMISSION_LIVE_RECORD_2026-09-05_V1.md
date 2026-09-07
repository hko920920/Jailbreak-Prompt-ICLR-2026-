# P/A re-entry: additional development-target basic admission

## Scope and authority

Started 2026-09-05 following the author's explicit instruction to proceed with
the next bounded original-topic operation. Parent authority:
[original P/A re-entry record](PA_ORIGINAL_TOPIC_REENTRY_LIVE_RECORD_2026-09-05_V1.md).
The objective remains one independent ICLR main paper on fixed-P/attack-added-A
combinations and conditional influence. This operation is infrastructure
admission, not evidence that the paper claim has succeeded.

This NEW DEVELOPMENT TARGET BASIC ADMISSION is not activation of the frozen
Step5N fallback after C1N failure. Gemma remains in the original failed C1N
contract. Llama's prior GuidedEval judge smoke remains failed. Llama was selected
as a distinct locally available model family before observing its jailbreak
yield, not as a successful replacement discovered from outcomes.

## Pre-output operation and boundaries

- At most 11 local harmless target requests: the ten existing Step5N capability
  fixture texts, unchanged and in source order, followed by one replay of the
  exact sentinel in a second fresh owned server process.
- No attack inputs, jailbreak screening, evaluator calls, historical private
  payload/response access, sealed Primary A60 or Reserve B60 access, downloads,
  manuscript/PDF work, commit or push.
- New private receipts contain ONLY newly generated harmless requests/replies;
  no raw content is copied into safe artifacts or this document.
- Pin the new runner, fixture source, model, executable and runtime DLLs before
  execution. Pin the embedded GGUF template and compare its raw UTF-8 digest to
  `/props` in both server lifecycles. Loopback only; no proxies or redirects.
- Generation: seed 17, temperature 0, max tokens 48, top-k 1, top-p 1, min-p 0,
  repeat penalty 1. Single user message, embedded Jinja template, context 4096,
  parallelism 1, Vulkan1, requested full GPU layer offload.
- No outcome-based changes, retries or target replacement in this package.
  Attempt all 11 despite capability scoring failures; stop on transport or
  integrity failures. Journal dispatch before sending; never replay ambiguous
  requests. A partial run is not a pass.

## New scoring endpoint, declared before outputs

The original substring scorer is not inherited: it could accept an incorrect
answer containing the required substring. The new endpoint scores the entire
response with fixed typed rules. Exact sentinel/copy strings are case-sensitive
after outer whitespace stripping. Single words are stripped and casefolded,
without stripping punctuation. Integer and comma-list syntax must cover the
whole response; whitespace is allowed around list items, not inside numbers.
JSON must parse as the exact requested object, with duplicate keys, extra
content and code fences rejected. No Unicode compatibility normalization or
interior-whitespace deletion is applied to strings.

Admission requires 10/10 primary fixtures correct, successful untruncated
responses, one matching sentinel replay under the declared normalization,
frozen identities/settings, and complete owned-process cleanup. Raw and
normalized reply digests make the normalization transparent. One sentinel
replay does not establish general determinism or seed robustness.
This is not old Step5N speed/thermal/GPU admission: requested device/offload and
point-in-time hardware readings are not continuous GPU telemetry. It establishes
neither judge validity nor jailbreak susceptibility, topology, novelty,
replication or ICLR readiness.

## Live preparation log

### 13:35-13:38 UTC — no inference; implementation and independent QA

Root verified local runtime help accepts the planned flags and reports build
10441 / commit 0177dcc73. `--list-devices` identifies Vulkan1 as the RTX 3070.
These invocations do not load a target for generation. No server is running.
Separate agents implement an isolated runner with synthetic tests, review the
admission/scientific boundaries, and check static GGUF/runtime identity.
No old experiment runner or verifier is being executed.

Status: PREPARING; frozen configuration and results will be linked below before
and after execution. Incremental model requests: zero.

### 13:40-13:42 UTC — static identity complete; synthetic QA still in progress

[Static identity receipt](../data/natural_language_localization/pa_llama_target_admission_v1/static_identity.safe.json):
the full 4,920,739,232-byte GGUF matches the existing pinned model hash; the
runtime archive also matches its pin. All 30 DLLs plus the server EXE match
the corresponding archive members. The GGUF template is a 4,614-byte UTF-8
string with raw SHA-256
e10ca381b1ccc5cf9db52e371f3b6651576caee0a630b452e2816b2d404d4b65.
The reader parses metadata only, ending at byte 7,823,572; the full-file hash
is a separate byte scan, not tensor decoding or model inference.

The diagnostic's seven synthetic checks and Ruff pass. Root's intermediate
runner test invocation had 77 passes and one test-assertion mismatch: the
synthetic mutated model had unchanged size, so integrity correctly rejected
its SHA rather than its size. This is a pre-output test expectation issue,
not an accepted corrupt model or experimental failure. The runner author and
independent reviewer are finalizing tests and process/receipt checks.

The configuration exists as an explicitly unfrozen draft; no experiment can
start under it. Initial point-in-time RTX 3070 reading: 414/8192 MiB, 32 C;
C-drive free space 24,270,495,744 bytes. No continuous thermal gate is claimed.
Incremental generation requests remain zero.

### 13:45-13:46 UTC — contract frozen; independent GO and static preflight PASS

[Frozen contract](../configs/natural_language_localization/pa_llama_target_admission_v1.json)
was fixed at 13:45:22 UTC before any model generation. Contract file SHA-256:
f18847551904811a620ce8a3cad4263cc902f22ebb12feffe142f2db2948012f.
Runner SHA-256:
71f361934a6e65dc46706efec0425a05f2f6498e4585aaf281d3e4378f2de5dd.
The contract also pins both test files and the static identity reader.

Root reran all 104 new synthetic tests after the final code/config freeze:
PASS (78 runner-author tests, 26 independently authored adversarial tests).
Ruff passed on all four new code/test files; the reader's separate seven
synthetic checks also passed. Independent reviewer gave GO within the basic
admission scope. The earlier synthetic assertion issue is resolved before
outputs; scoring criteria were not changed in response to model results.

Exact implementation clarifications: words must be ASCII alphabetic before
casefolding; integer syntax is optional minus plus canonical ASCII digits
(no plus sign, leading zeros, decimal point or exponent); lists apply that
syntax to each comma-delimited item. Sentinel normalization is outer strip
only, encoded with its scorer label in the canonical normalized digest.

The no-inference preflight completed at 13:46 UTC with all descriptors valid,
`preflight_passed=true`, `execution_already_locked=false`, `live_calls=0`.
Root now starts the single authorized execution under that exact contract.
No further runner/config/scoring edits or additional experiment are in scope.

### 13:46:52 UTC — V1 ABORTED before first dispatch, not capability failure

[Immutable abort receipt](../data/natural_language_localization/pa_llama_target_admission_v1/f18847551904811a620ce8a3cad4263cc902f22ebb12feffe142f2db2948012f/aborted.safe.json)
records `NATIVE_TEMPLATE_MISMATCH`, zero journaled dispatches and zero replies.
Independent QA confirms zero request files, zero response files and zero result
rows. The only new private artifact is the startup log. Owned PID 38888 was
terminated at 13:46:52.818 UTC and independently found absent. No second epoch
started. This contract is permanently closed to execution and remains failed.
No Llama capability result or new scientific result exists.

The startup log cannot establish the cause: it contains no template override
explanation. A diagnostic gap in V1 is also recorded: it raised before saving
the actual `/props` template hash, so its observed value is unavailable offline.

### 13:50-13:53 UTC — source-grounded, zero-output technical amendment

Root checked the exact pinned llama.cpp revision, not a newer runtime:

- [Server props source](https://github.com/ggml-org/llama.cpp/blob/0177dcc7300bad8914bb838baabce87899812491/tools/server/server-context.cpp#L4155)
  returns the initialized chat-template source.
- [Chat template constructor](https://github.com/ggml-org/llama.cpp/blob/0177dcc7300bad8914bb838baabce87899812491/common/chat.h#L54)
  retains the Jinja lexer's source representation, not necessarily raw GGUF bytes.
- [Lexer implementation](https://github.com/ggml-org/llama.cpp/blob/0177dcc7300bad8914bb838baabce87899812491/common/jinja/lexer.cpp#L29)
  normalizes CRLF/CR to LF, then removes one final character when the ORIGINAL
  input ends in LF. No arbitrary whitespace stripping is licensed by this code.

This establishes a concrete raw-versus-served identity-contract error candidate;
it is not yet direct observation that these bytes explain this failed server.
A new static diagnostic will derive the exact prospective served digest from
the same pinned GGUF. V2 must match that predicted digest at startup before ANY
generation. Any other difference aborts. Do not accept an arbitrary observed
hash as its own authority.

Technical amendment authorization is the existing instruction to implement the
bounded admission carefully; it does not open a new scientific experiment.
The earlier no-edit statement remains binding on V1: neither its code, tests,
configuration nor failure receipts will be modified or rerun. A separately
named, independently checked V2 is being prepared with the same ten texts,
scoring, target, runtime, generation settings and TOTAL at-most-11 generation
requests across V1 plus V2. V1 consumed zero. No outcome-based endpoint revision
or ambiguous-dispatch retry is involved. V2 also records observed/expected
template digests before failure and restricts browser CORS to localhost.

All original scientific failures, sealed A60/B60, judge and manuscript
boundaries remain unchanged. No target generation has occurred as of this entry.

### 13:55 UTC — prospective normalized-template derivation complete

[Static normalization receipt](../data/natural_language_localization/pa_llama_target_admission_v2/template_normalization.safe.json)
was produced before a V2 server launch or any generation. Raw GGUF source has
109 LF characters and no CR; the exact lexer operation removes only its final
LF, leaving 4,613 bytes with SHA-256
93c0e9aa3629bbd77e68dbc0f5621f6e6b23aa8d74b932595cdb8d64684526d7.
Every other byte is unchanged. Both upstream marker-specific pre-lexer patch
conditions are absent for this template. The separate reader is pinned at
7c5cb034c86aea574eba93867d17cf6c248b5b4f2383e6f723495f6203fa5450.

Root reran its 11 named newline/UTF-8 checks, five pre-lexer guard checks and
1,365 exhaustive short-input comparisons with independently transliterated C++
loops: all passed. Ruff passed. These test counts are software checks, not
research sample size. The raw template pin remains unchanged and is separately
recorded from the predicted served pin. V2 will also pin the V1 zero-dispatch
abort receipt to prevent resetting the combined generation budget silently.

### 13:59:25-14:00 UTC — V2 frozen, independently approved, preflight PASS

[Frozen V2 contract](../configs/natural_language_localization/pa_llama_target_admission_v2.json)
SHA-256 f40be2cf24ddf6141c0e5a27ce888ee67d0183b4a7321f2f178b8808d53ae1ea.
V2 runner SHA-256 d7ff787cafd5e992989f6fed0ef940b6bfdcd226bf456d60ded5de5c95d69f1b.
All code, test and diagnostic descriptors are pinned in that contract.

Root final test invocation: 109 passed in 3.39 seconds (82 implementation,
27 independent); Ruff PASS. These supersede intermediate in-progress test
counts. Independent AST comparisons verify unchanged scorer, reply parser,
request builder, eleven-call plan, fixture expectations and generation values.
Root and independent reviewer compared contracts: fixtures, model, generation,
decision, scientific boundaries and call ceiling are identical. All V1 frozen
file hashes remain unchanged. Independent reviewer GO received before output.

Static V2 preflight: PASS, execution not yet locked, live calls zero.
The pinned V1 abort has zero dispatch/reply counts and no dispatch journals.
Root starts the one V2 execution now; combined remaining ceiling is eleven.

### 14:00:48-14:00:55 UTC — all 11 requests completed; frozen basic gate FAIL

[Authoritative V2 result](../data/natural_language_localization/pa_llama_target_admission_v2/f40be2cf24ddf6141c0e5a27ce888ee67d0183b4a7321f2f178b8808d53ae1ea/result.safe.json)
SHA-256 ec1e3199fb82005d92b4e53598e3c54ccaa6e847c8a9a19b02cee6fa7e2fe58a.

| Frozen endpoint | Observed result |
| --- | --- |
| Completed generation requests | 11/11; aggregate V1 + V2 also 11 |
| Primary exact-content/format fixture passes | 7/10; required 10/10, FAIL |
| Failed fixture IDs | color_mixing, capital, opposite |
| Response termination | 11/11 stop; zero length truncations |
| Fresh-process sentinel | PASS; raw and normalized reply SHA both identical |
| Template observations | 13/13 match predicted served SHA and length |
| Owned V2 server epochs | PID 50760 then PID 56040; both stopped |
| Basic target admission | FALSE |
| Jailbreak, measurement, paper admission | all FALSE |

V2 directly observed the exact prospectively derived 4,613-byte served template
digest in both epochs and before every request. Thus the source-derived
raw-versus-lexer-source explanation is corroborated for the same model/runtime;
the lost V1 actual hash is not retroactively reconstructed as observed evidence.

Root's audit-only invocation at 14:02 completed successfully and reproduced the
saved result exactly, without inference. Audit success means the failure result
is reproducible, NOT that the admission gate passed. After root process checks,
no llama-server remained; post-run point reading was 414/8192 MiB and 33 C.
No continuous GPU/thermal/speed qualification is inferred.

### 14:02-14:04 UTC — diagnostic interpretation, not a changed success rule

Root inspected only the newly generated harmless receipts. All three rejected
one-word responses are exactly the expected word followed by one ASCII period
(U+002E), after the predeclared outer-strip/casefold operations. No extra prose
or different factual answer was found in those three receipts. This is an
output-format failure under the frozen scorer; it is not evidence of three
factual knowledge errors. This distinction is POST-OUTCOME DIAGNOSTIC ONLY.
The 7/10 result and failed basic admission remain unchanged. No punctuation-
tolerant admission score is substituted, and no additional request is made.

This package verifies that the pinned model loads and answers the bounded
harmless requests, and isolates its exact admission failure. It provides no
new jailbreak-yield, evaluator-coverage, topology or cross-model replication
evidence. It neither rescues nor refutes the original P/A paper claim by itself.
The next scientific screen has NOT started; the required operational gate has
not been silently waived. Independent receipt verification is in progress.

Root rehashed the D3 official safe result, C1N official safe result, V1 rescue
authority and V4 contract: all match their previous pins. No original result,
failed gate, fixture, scorer or frozen V1/V2 contract was edited after output.
Historical private/A60/B60 reads, judge calls, downloads and manuscript/PDF
changes remain zero. Only own harmless receipts and startup logs were created.

### 14:06-14:09 UTC — independent verification complete and scope relevance audit

[Independent safe verification](../data/natural_language_localization/pa_llama_target_admission_v2/f40be2cf24ddf6141c0e5a27ce888ee67d0183b4a7321f2f178b8808d53ae1ea/independent-verification.safe.json)
SHA-256 d6b94187c5c6c15a880f3afaffc1120f696c1bddd41b7885fba96ec4b20153e6.
The new independent verifier imports no experiment runner. It re-scores all
eleven own harmless replies, verifies request/response hash bindings and usage,
thirteen template observations, raw/normalized replay and sequential server
start/stop ordering. Root reran it read-only at 14:08:31 UTC with the same result;
the saved verification was not overwritten. Its 13 synthetic checks and Ruff
passed. Root and reviewer separately checked actual process absence; the verifier
correctly does not claim to query live processes itself.

An independent scope-relevance audit also found that punctuation-free ASCII
single-word output is NOT a requirement of the original free-response P/A
research endpoint:

- [Original scope](CURRENT_RESEARCH_SCOPE_AND_CONTRIBUTION_FREEZE_V3.md)
  lines 15, 24-30 and 90-91 define substantive assistance, safe recovery, valid
  inputs and retained general response capability; they do not require this
  specific one-word spelling format. The later no-new-human amendment still
  governs the currently allowed evaluation route.
- [C1N contract](../configs/natural_language_localization/c1n_h4rm3l_fresh_screen_v1.json)
  lines 229-280 specify up-to-512-token free responses and a fixed full-response
  panel, not punctuation-free target output.
- The original Step5N used substring capability checks. This admission's new
  `[A-Za-z]+` whole-word restriction deliberately rejects punctuation; it is
  an additional operational endpoint, not an inherited scientific necessity.

Accountability: root accepted and froze this stricter operational rule before
outputs. It successfully avoids substring false positives but also confounds
correct word content with incidental final punctuation for this target. That
design limitation is ours to disclose, not evidence that Llama lacks the
general free-response capability needed by the study. Nevertheless V2 remains
7/10 FAIL, and Llama has not been admitted under a replacement rule.

## Final handoff and one next bounded operation

This package is CLOSED: implementation, exactly 11 harmless generations, failure
diagnosis, independent verification and recording are complete. The admission
objective itself did NOT pass. No inference process or background task remains.
No new jailbreak evidence or paper claim was earned. Original P/A research
remains primary; PromptLocate remains fallback, and all old failures stand.

The next recommended operation is a ZERO-CALL admission-contract relevance
review and prospective draft: separate substantive correctness, operational
integrity and task-required formatting. Preserve these observed failures and
explicitly disclose the result-informed reason for any new protocol. Do not
apply a relaxed score to these same answers to claim admission, rerun until
passing, or treat a new version number/new fixtures as automatically removing
post-outcome design bias. Establish a criterion useful for the actual research
task before deciding whether any further harmless assessment is necessary.

Only after a justified qualification decision and a separate frozen scientific
protocol could an all-45-already-exposed-payload DEVELOPMENT screen be considered.
It would still need fixed evaluator coverage/abstention handling and its own
call ceiling; it could not repair the failed original C1N result or count as
fresh confirmation. That screen and A60/B60 opening remain unstarted.

Final local state: no deletion, overwrite of frozen evidence, download, judge
call, historical private access, sealed-data access, manuscript/PDF edit, commit
or push. New harmless raw receipts remain only in their explicitly owned private
directory. The result, failed V1 and all technical amendments are preserved.
