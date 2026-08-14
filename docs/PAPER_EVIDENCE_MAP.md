# Paper Evidence Map

## Planned main claim

A meaningful subset of successful jailbreaks is causally concentrated in small, human-editable semantic span sets, and those sets can be found under a practical query budget without deleting the underlying requested behavior.

## Evidence required

### Claim 1 — The task is distinct and well-defined

- formal definition;
- comparison to LOCA, Token Highlighter, PromptLocate, and attention-head work;
- explicit access assumptions;
- examples that separate harmful payload from jailbreak-enabling framing.

### Claim 2 — The phenomenon exists

- localizable fraction with confidence interval;
- span-size distribution;
- neutralizer and seed robustness;
- human audit of intent preservation;
- failure taxonomy.

### Claim 3 — The search method helps

- exhaustive-oracle comparison on short prompts;
- quality-versus-query curves;
- wavelet-free and coefficient ablations;
- matched random controls.

### Claim 4 — Findings generalize

- multiple model families;
- held-out attack types;
- paraphrase/position perturbations;
- full-response judge swap.

### Supporting, not central

- known safety-head or residual-stream changes after the localized span is neutralized;
- targeted prompt sanitation demonstration;
- case studies.

## Paper section budget

1. Introduction — 1 page
2. Related work and task boundary — 1 page
3. Problem definition — 1 page
4. Method — 2 pages
5. Experimental protocol — 1 page
6. Main results — 2 pages
7. Analysis, limitations, ethics — 1 page

Appendix: full algorithms, prompt-neutralization details, additional models, judge audits, compute, and examples.
