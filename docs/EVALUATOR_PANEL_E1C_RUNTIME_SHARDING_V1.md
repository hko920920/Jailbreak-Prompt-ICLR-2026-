# Evaluator Panel E1C Runtime Sharding V1

Date: 2026-08-26 (Asia/Seoul)

## Decision

The first live HarmBench qualification did not yield a scientific pass or fail.
It ended in an operational timeout while evaluating the frozen 200-record raw
official-template block.

- source run: `32822371869`
- terminal status: `E1C_HARMBENCH_COMPONENT_OPERATIONAL_FAIL`
- failure stage: `evaluate_raw_and_hardened_full_selection`
- exit code: `124`
- server readiness: passed
- completed progress visible in the job log: `120 / 200` raw-template records
- scientific interpretation: prohibited

The model, data, prompt family, parser, hardening rule, thresholds, and request
denominators remain frozen. The only change is how the same requests are
scheduled across GitHub-hosted runners.

## Runtime-only remediation

The 400 full-selection requests are partitioned into eight deterministic
workers.

\[
\operatorname{shard}(i) = \operatorname{position}(i) \bmod 8
\]

Each full worker receives exactly 25 of the frozen 200 records and evaluates
both frozen modes:

- 25 raw official-template requests;
- 25 hardened production-template requests;
- 50 requests per worker;
- 400 requests after exact merge.

A separate auxiliary worker runs only after the full hardened predictions have
been merged:

- 24 frozen repeatability requests;
- 24 frozen injection-canary requests;
- 48 auxiliary requests.

The final denominator remains:

\[
400 + 24 + 24 = 448.
\]

No partial prediction from the timed-out run is reused.

## Exact merge requirements

Aggregation is allowed only when all eight full workers succeed and the merged
safe rows satisfy all of the following:

1. exactly 200 positions for each mode;
2. positions are exactly `0..199`;
3. no duplicate position;
4. record ID, behavior hash, and human-majority label match the frozen
   selection at every position;
5. every row reports the expected evaluation mode.

Global raw and hardened metrics are recomputed from the merged rows rather than
averaging shard-level metrics.

## Frozen scientific contract

The following remain unchanged:

- official model and community Q4_K_M runtime identity;
- runtime SHA-256 and byte size;
- `LLAMA2_CLS_PROMPT`;
- 200 repaired validation records and 100/100 label balance;
- temperature `0`, seed `17`, one generated token;
- 4096-token context;
- strict Yes/No parser and abstention semantics;
- generation-only hardening;
- all accuracy, error-rate, repeatability, and canary thresholds;
- all 448 request denominators.

The original `finalize` implementation applies the original frozen scientific
gate after the exact 400-request merge and 48-request auxiliary block.

## Evidence boundary

This is runtime-remediation and evaluator-development evidence. It is not a
paper-valid jailbreak-topology result. Safe artifacts may contain IDs, hashes,
labels, binary predictions, parse state, metrics, and execution identities.
They may not contain raw behaviors, contexts, generations, rendered prompts, or
classifier outputs.

The following remain closed:

- semantic-only and cross-regime Stage A;
- prior evaluation and held-out partitions;
- causal cut-set oracle;
- keep-only sufficiency oracle;
- wavelet and other approximate search.

## Terminal branches

- complete 448 requests and pass the frozen gate:
  `E1D_ACTIONABILITY_COMPONENT_QUALIFICATION`;
- complete 448 requests but miss a scientific gate:
  exclude or repair the HarmBench axis without opening Stage A;
- any worker or merge failure:
  runtime-only repair under the same scientific contract.
