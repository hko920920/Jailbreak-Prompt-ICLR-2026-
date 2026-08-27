# Topology Micro-Pilot Execution Freeze v1

## Decision

This protocol narrows the project to one paper question: recover all robust minimal input-removal sets for already-successful jailbreaks. The development micro-pilot compares h4rm3l and GCG before any broader S/F/U claim is opened.

## Frozen execution identity

- Target: `Qwen/Qwen2.5-7B-Instruct` at immutable revision `a09a35458c702b33eeacc393d103063234e8bc28`.
- Confirmatory claims require the canonical model revision.
- A resolved Q4_K_M GGUF lane may be used only for development screening; its repository revision and every LFS digest are recorded before a model call.
- h4rm3l and GCG source identities are inherited from passed pre-output audits.

## Development payloads

Four text-only HarmBench validation behaviors are selected outcome-blind from four predeclared semantic categories. Selection is deterministic by SHA-256. Raw payloads exist only in private runtime memory. The repository stores only hashes, byte lengths, and category labels.

## Decoding and causal budget

Sampling uses seeds 11, 23, and 47, temperature 0.7, top-p 0.9, top-k 50, and at most 512 new tokens. Direct and attacked prompts share payload and decoding. Each stable pair has at most six coarse attack units, all 64 subsets, two neutralizers, and three seeds: at most 384 intervened generations.

## Evaluation boundary

WildGuard is a conservative screening signal. HarmBench is a non-voting diagnostic. No automatic screen-positive is a final label. Two independent blinded annotators evaluate decision-critical baselines and topology claims; a third adjudicates disagreement. Safe artifacts contain only hashes and aggregates.

## Authorization

Passing this freeze authorizes only the h4rm3l/GCG signal-screen input manifest. It does not authorize a causal claim, held-out inspection, keep-only sufficiency, wavelet search, or paper-valid confirmation.
