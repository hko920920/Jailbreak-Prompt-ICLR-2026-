# E0 GCG Static Adapter and Intervention-Boundary Audit v1

Date: 2026-08-24 (Asia/Seoul)

## Purpose

This E0 step qualifies the pinned `llm-attacks/llm-attacks` GCG route before any target-model attack outcome is observed.

It does **not** execute GCG, load target-model weights, use a real harmful payload, generate an adversarial suffix, measure attack success, or open the causal oracle.

The audit asks only whether the source route can support the later causal-topology study under a defensible input boundary:

1. the explicit goal and adversarial control are represented separately;
2. candidate optimization modifies the control slice rather than rewriting the goal;
3. the official template budget and candidate-update rules can be frozen;
4. a position-preserving block intervention vocabulary can be defined before outputs;
5. a harmless synthetic placeholder remains byte-identical under every preliminary block intervention.

## Pinned source

- repository: `llm-attacks/llm-attacks`
- revision: `098262edf85f807224e70ecd87b9d83716bf6b73`
- tree: `aa64fc78c0bed738c6952210cd0eb83d8bc0da9b`
- license: MIT

The workflow verifies immutable Git blob identities for the experiment template, main entry point, base attack manager, GCG implementation, minimal-GCG utilities, setup file, and license.

## Source properties tested

The audit verifies from source that:

- `goal` and `control` are distinct fields;
- `_goal_slice` and `_control_slice` are distinct token regions;
- candidate logits scatter candidate IDs only into `_control_slice`;
- GCG gradients are calculated for the control/input slice;
- each sampled candidate changes a single coordinate selected from a gradient top-k set;
- filtered-candidate handling is present;
- the main entry point forwards frozen `n_steps`, `batch_size`, `topk`, temperature, filtering, and ASCII policy to the attack loop.

These checks establish a viable source adapter boundary. They do not establish attack effectiveness or causal necessity.

## Frozen official template values

The pinned template is expected to declare:

- control initialization: 20 whitespace-separated exclamation units;
- steps: 500;
- batch size: 512;
- top-k: 256;
- temperature: 1;
- target/control loss weights: 1.0 / 0.0;
- non-ASCII candidates disabled;
- candidate filtering enabled;
- success early stopping disabled.

The final study budget may use a separately frozen and justified development budget, but it may not be selected after observing attack-success outcomes. This E0 audit records the upstream defaults rather than authorizing target execution.

## Preliminary intervention vocabulary

The initial control text is divided into four equal lexical blocks solely for a harmless adapter smoke test.

For all 15 non-empty block subsets and all 10 contiguous block intervals, selected units are replaced with an equal-count neutral lexical unit. The audit requires:

- the synthetic goal remains the exact byte prefix;
- the goal appears exactly once;
- the control lexical length is unchanged;
- no raw composed text is committed.

This lexical partition is **not** the final token-level oracle. After target model and tokenizer selection, actual token boundaries, chat-template slices, block count, and neutral replacement tokens must be frozen again. Deletion remains an auxiliary control because it changes downstream token positions.

## Pass meaning

A pass authorizes only:

> `FREEZE_GCG_TOKENIZER_TEMPLATE_BUDGET_AND_POSITION_PRESERVING_NEUTRALIZER_AUDIT`

It does not admit GCG to the balanced signal screen. Admission additionally requires target/tokenizer compatibility, chat-template and slice stability, a fixed regeneration or artifact route, a frozen candidate-selection budget, a position-preserving neutralizer smoke, evaluator-panel GO, and the balanced signal-screen contract.

## Sealed boundaries

- real harmful payload: not used;
- target weights: not downloaded;
- target inference: not called;
- cross-regime Stage A: closed;
- prior evaluation and held-out data: sealed;
- causal and keep-only oracles: closed;
- wavelet: closed.
