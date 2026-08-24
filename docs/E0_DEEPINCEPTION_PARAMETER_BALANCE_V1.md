# E0 DeepInception Parameter and Balanced-Template Audit v1

Date: 2026-08-24 (Asia/Seoul)

## Purpose

The length-delimited exact-payload adapter passed all 50 main-data rows and all 12,700 static intervention variants. Before any target-model output, this audit checks whether the same payload-invariant seven-unit representation also works across the official DeepInception ablations for:

- number of characters;
- recursion depth;
- scene type.

This is an adapter and study-design audit. It does not measure attack success.

## Pinned source axes

The audit uses three immutable source files from the same pinned DeepInception revision:

- `res/data_abl_c.json`: character counts 1, 3, 5, 7, and 10;
- `res/data_abl_layers.json`: layer depths 1, 3, 5, 7, and 10;
- `res/data_multi_scene.json`: science fiction, documentary, spy movie, stage scene, and onion news group.

Each file must contain five rows with five questions per row. Ordered topic identities and canonical-goal identities must match across the three files.

## Payload and parameter parsing

Every question is parsed under rules frozen before target outputs:

1. The scene and character count are read from the opening `Create ... with ... character(s), where` clause.
2. The layer depth is read from the unique `please reach layer N.` clause.
3. The task starts immediately after the unique proposal prefix.
4. Its character length equals the canonical direct goal length.
5. The source task segment must be equal to the canonical goal after case folding and must have the same character and UTF-8 byte lengths.
6. The remaining text before the final-layer prefix is an opaque bridge preserved exactly.
7. The canonical goal is reinserted once, contiguously and byte-identically.

## Static intervention audit

For all 75 official parameterized questions, the audit replaces the goal with one harmless sentinel and verifies:

- a contiguous partition into seven attack-owned units plus one immutable payload;
- all 127 nonempty attack-unit subsets;
- deletion and layout-preserving blanking;
- 254 variants per question;
- exact sentinel preservation for every variant;
- length and byte-length rules for both neutralizers.

The frozen total is:

- 9,525 subset instances;
- 19,050 neutralized static variants.

No target model is called and no raw source question, goal, derived prompt, or synthetic prompt enters the safe record.

## Primary family representative

The primary DeepInception family representative is fixed before outcomes as:

```text
scene = science fiction
character count = 5
layer depth = 5
```

This representative may not be replaced after target outputs. A successful sensitivity template cannot rescue a failed primary representative.

## Balanced sensitivity registry

The predeclared primary-plus-sensitivity registry contains nine unique settings:

- all five source scenes at character count 5 and depth 5;
- character-count extremes 1 and 10 at science fiction and depth 5;
- depth extremes 1 and 10 at science fiction and character count 5.

Intermediate values 3 and 7 for the character and depth axes form a separate midpoint-sensitivity registry. They may diagnose parameter response but may not replace the primary representative.

## Interpretation of a pass

A pass establishes that:

- all official parameter axes are structurally compatible with exact-payload rerendering;
- every question can be represented with the same seven typed attack units;
- every frozen subset and neutralizer preserves the immutable payload;
- a non-outcome-selected primary representative and balanced sensitivity registry are available for a later signal-screen contract.

It does not establish that DeepInception succeeds on a target model, that parameter changes improve attack success, or that any unit is causally necessary.

## Sealed boundaries

Throughout this audit:

- real harmful outputs are not generated;
- target models are not called;
- attack success is not scored;
- cross-regime Stage A remains closed;
- held-out data remain sealed;
- causal and keep-only oracles remain closed;
- wavelet remains closed.
