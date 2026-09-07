# Step 5N Preferred-Target Harmless Admission Result V1

Date: 2026-09-05 (Asia/Seoul)  
Decision: **PASS — Qwen2.5 + official Google Gemma 4 admitted for a separately frozen C1N**  
Evidence class: **operational qualification only; not paper evidence**

## Outcome

The prospectively selected preferred target pair passed every frozen harmless runtime gate on the
local RTX 3070. Qwen2.5 and Gemma 4 each completed 11/11 independent-process invocations, passed
all 10/10 distinct capability prompts, reproduced the deterministic sentinel byte-for-byte after
normalization, used the embedded chat template and Vulkan GPU offload, and stayed within the
predeclared speed, VRAM, temperature, echo, and truncation bounds.

The independent verifier reconstructed the 22-call plan, every safe projection, both model
summaries, and the final decision from the frozen contract and private harmless-only records. All
18/18 verification checks passed.

This result does **not** test a jailbreak, observe attack success, call an evaluator, open a
topology, or support a paper claim. The official cross-family D3 result remains failed. It only
removes the operational uncertainty about using the preferred Qwen2.5/Gemma 4 pair in the next,
separately frozen h4rm3l-only C1N screen.

## Frozen boundary

- Author decision: accept the D3 `NARROW` route to h4rm3l and select Qwen2.5 plus official Google
  Gemma 4 as the preferred pair.
- Allowed here: one exact Gemma text-GGUF download and harmless target admission.
- Forbidden here: h4rm3l rendering, confirmation-reservation content, harmful payload access,
  evaluator calls, attack-success observation, topology output, and C1N/C2N/C3N scientific
  output.
- Llama 3.1 fallback: not activated. It remains allowable only under a newly frozen pre-C1N
  operational contract if Gemma has an operational admission failure; an unattractive scientific
  result can never authorize substitution.

The three prospective scientific-output roots remained absent through independent verification.

## Exact artifacts

The runner requested only:

`google/gemma-4-E4B-it-qat-q4_0-gguf@4b4a2c1d584be7264f87aac328a1bc739ce81b6c/gemma-4-E4B_q4_0-it.gguf`

- expected and observed size: `5,154,941,280` bytes;
- expected and observed SHA-256:
  `676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee`;
- multimodal projector downloaded: no;
- incomplete download residue: zero;
- duplicate model copy: none. The Hugging Face local metadata cache was below 0.01 MiB.

The existing two-file official Qwen2.5 Q4_K_M artifact and llama.cpp `b10441` Vulkan runtime were
rehash-verified before use. The machine snapshot had 8,192 MiB VRAM, 31.715 GiB system RAM, and
30.315 GiB free disk before acquisition. Free disk after acquisition was 25.512 GiB.

## Frozen harmless design

- two target models;
- 10 fixed harmless capability prompts per model;
- a second independent-process execution of the exact sentinel per model;
- 11 calls per model and 22 calls total;
- seed 17, temperature 0, top-k 1, top-p 1, 4,096-token context, and 48-token maximum output;
- private file prompt transport and the frozen simple-I/O V3 extractor;
- atomic safe checkpoint after every invocation;
- all 10 capabilities required, all 11 generations required, deterministic replay required;
- median decode rate at least 8 tokens/s;
- maximum observed VRAM at most 8,064 MiB and temperature at most 85 C;
- at least 1,024 MiB GPU-memory delta, an active embedded chat template, no full prompt echo, and
  no maximum-token truncation.

## Results

| Model | Calls | Capabilities | Median decode | Median cold process | Max VRAM | Max GPU delta | Max temp | Deterministic |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Qwen2.5-7B-Instruct Q4_K_M | 11/11 | 10/10 | 56.51 tok/s | 4.344 s | 4,948 MiB | 4,534 MiB | 40 C | yes |
| Google Gemma 4 E4B IT QAT Q4_0 | 11/11 | 10/10 | 55.51 tok/s | 3.844 s | 3,391 MiB | 2,977 MiB | 44 C | yes |

The 22-call live phase took 104.171 seconds with zero cache hits. llama.cpp did not expose a
separately parseable `load_ms` field in these records, so that optional descriptive field is null;
the gate was prospectively based on end-to-end cold-process time, decode rate, VRAM, and
temperature and does not depend on `load_ms`.

## Independent reconstruction

The verifier does not import the Step 5N runner. It independently checked:

- frozen dependency, runner, helper, and verifier hashes;
- exact reconstruction of all 22 unique plan identities;
- exact private harmless-record set and execution identities;
- exact reconstruction of the safe progress rows and their file hash;
- preparation and final-result identities;
- both model summaries and all gate decisions;
- absence of raw prompt/response fields from safe outputs;
- empty private staging and absent C1N/C2N/C3N output roots.

Result identity:
`7a8487a72fd631650fc90c15f9926476f3aefd4815dea8ea170fce54f2fa53a4`  
Independent reconstruction identity:
`e6e01b4f7736beaaf13d066868e8f1cb68e3baf44230ccbdb6c0eac1c611b4ee`  
Verification identity:
`3a4d5f81383edc2442c8d72f3edf1f8f1f15214888bf76d7330eb95b8b8765f7`

## Reproducibility record

- frozen contract SHA-256:
  `23ef4e5fa47389ff587322acd2d2c956d460ee5f52af4ffc7b7f9c21e59917a6`;
- runner SHA-256:
  `becbec71e6ddf8b03b31ed013f2da47c4a4a55d3b0927958fef1d9130c567269`;
- independent verifier SHA-256:
  `e3671805b3649210ac2ac4381515b89b467d5139f04dfa63c3c44d06056fc2cd`;
- immutable plan SHA-256:
  `7a0af10f41151069c8d9b9d255bb4d871eea78d74bd344da840ccc973dd10c05`;
- safe progress SHA-256:
  `17f76b20d023a95100185811cddff0b73bc2f84fc3d30fe1544aaa799dac50fb`;
- safe result file SHA-256:
  `7fef340b6660aec94adf63755b7f391ba1f1486073eb5e3baceacb52ce5140a0`;
- independent verification file SHA-256:
  `ecb8d3cad807651dce9c2140307c5b4c10027dfa3a8bc271ccbf48d1c6b1124a`.

Step-focused tests passed 19/19. The complete 503-test repository suite and Ruff passed after updating
one historical preauthorization test to verify its immutable receipt rather than incorrectly
rerun an old temporal-absence predicate after the authorized transition.

## Scientific interpretation and next gate

Earned: the preferred contemporary two-target runtime pair is operationally usable and does not
need the Llama fallback.

Not earned: stable jailbreak-pair prevalence, minimal recovery sets, neutralizer agreement,
cross-model recurrence, fresh-seed replication, or a paper contribution.

Next operation: build, independently test, and freeze a new target-scoped C1N h4rm3l-only screen
contract before reading the reserved payloads or generating any scientific target output. The
contract must put `target_id` in every plan/record/path identity, share no responses across target
models, retain every eligible stable pair, and preserve the official D3 failure and coarsening
limitation.
