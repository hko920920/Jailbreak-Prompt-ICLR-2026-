# E1C HarmBench paired-invariance live requalification

This workflow executes the separately frozen 288-request canary contract after
the original E1C scientific failure. It cannot erase or revise the predecessor
result.

Eight independent CPU workers each evaluate three frozen human-labeled records
under six transformations and two prompt modes. Every worker uses the same
immutable HarmBench Q4_K_M runtime, llama.cpp revision, `LLAMA2_CLS_PROMPT`, seed,
temperature, parser, and production hardening as the completed E1C run.

Only hash-based and aggregate safe records are uploaded and committed. Raw
behaviors, generations, prompts, and classifier outputs remain in a private
temporary directory that is deleted at worker termination.

The final job requires an exact 288-cell grid with no missing or duplicate
`record × transformation × mode` entry. It applies the frozen hardened gate and
returns exactly one of:

- `E1C_HARMBENCH_CANARY_REQUALIFICATION_PASS`;
- `E1C_HARMBENCH_CANARY_REQUALIFICATION_SCIENTIFIC_FAIL`;
- `E1C_HARMBENCH_CANARY_REQUALIFICATION_OPERATIONAL_FAIL`.

A scientific pass authorizes E1D actionability-component qualification. A
scientific failure excludes HarmBench from the production panel while allowing
E1D to proceed without opening Stage A. An operational failure permits only a
runtime repair with the selection, model, prompt, transformations, and gate
unchanged.
