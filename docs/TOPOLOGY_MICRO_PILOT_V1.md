# Topology Micro-Pilot v1

Date: 2026-08-27 (Asia/Seoul)
Evidence class: DEVELOPMENT

## Purpose

This is the decisive experiment for whether the narrowed standalone paper is worth expanding. It does not attempt the full S/F/U matrix. It asks whether two structurally different audited families already exhibit robust, nontrivial minimal-recovery topology.

## Included families

- h4rm3l: semantic-compositional, typed strategy units.
- GCG: non-fluent optimized, frozen block/interval units.

DeepInception, AutoDAN, a second model, held-out payloads, token-level full refinement, keep-only sufficiency, and wavelet search remain closed.

## Execution outline

1. Freeze one open-weight target model, tokenizer, chat template, decoding, and three seeds.
2. Freeze four development payload hashes per family without using topology outcomes.
3. Generate direct and attacked outputs under identical decoding.
4. Use automatic signals only to screen and route disagreements.
5. Blindly audit direct/attacked baselines before opening topology.
6. Retain stable direct-safe / attacked-harmful pairs.
7. Freeze no more than six attack-added coarse units for each pair.
8. Enumerate every subset under two meaningful neutralizers and three seeds.
9. Audit every candidate minimal set and all strict subsets needed to prove minimality.
10. Assign GO, NARROW, or STOP exactly as frozen in the JSON contract.

## Why this is enough to decide

If the project cannot find repeated non-singleton or multiple-pathway topology in this deliberately contrasting micro-pilot, adding more evaluators, attack families, and search algorithms is unlikely to create a strong paper. If the signal exists and is stable, the four-family, two-model confirmatory extension becomes justified.

## Expected computational form

With at most six coarse units, each instance has at most 64 subsets. Under two neutralizers and three seeds, the upper bound is 384 intervened generations per stable instance, plus baselines and audit overhead. The pilot should therefore remain small enough to inspect exactly rather than rely on a heuristic search.

## Claim boundary

A successful pilot supports only a GO decision. It does not itself support an ICLR claim. Paper-valid claims require a fresh confirmatory contract with unseen payloads, two model families, additional attack families, and independent human audit.
