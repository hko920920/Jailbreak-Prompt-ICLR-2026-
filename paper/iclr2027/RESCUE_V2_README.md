# Recovery identification manuscript V2

`rescue_v2.tex` is a self-contained English methods/pilot manuscript reporting completed retrospective results. `main.tex` is the preserved earlier prospective draft. The V2 manuscript does not claim submission, acceptance, ICLR readiness, prospective replication, human validation of the local responses, or new GuidedEval output.

The main evidence is the safe 12-instance / nine-payload D3 decision table, the new necessary/possible-family identification audit, the deduplicated operator/seed witness provenance, and the immutable D3 and C1N negative results. In particular, all three distinct adjacent atomic reversals are blanking-specific; omission is safe on the three sampled closure outputs. The manuscript reports the small scope and this limitation explicitly.

Build from this directory with the existing official style and math assets:

```powershell
pdflatex -disable-installer -interaction=nonstopmode -halt-on-error rescue_v2.tex
pdflatex -disable-installer -interaction=nonstopmode -halt-on-error rescue_v2.tex
```

The inline `thebibliography` contains ten citations checked against primary arXiv, PMLR, JMLR, ACL Anthology, or publisher sources on 2026-09-05. No BibTeX invocation or additional bibliography file is required. The conference style's default review-status header is overridden in this manuscript to say “Retrospective methods and pilot study — working manuscript.”

Scientific result sources:

- `data/natural_language_localization/rescue_identification_v2/audit.safe.json`, result identity `52e114d41d998e161c720b6ce89da87d8da908e89b2d7e3e873e3b0d8e102acc`.
- `data/natural_language_localization/rescue_identification_v2/witness_provenance.safe.json`.
- `data/natural_language_localization/d3_exact_topology_v1/instance_results.safe.jsonl` and the original D3 result/verification receipts.
- `data/natural_language_localization/c1n_h4rm3l_fresh_screen_v1/result.safe.json` and its separate independent verification receipt.

The audit was developed after the failed original gates. This chronology is part of the methods and must remain visible in any later version. Updating a judge or obtaining new outcomes requires a separately recorded study; it must not silently replace the historical endpoint or its negative results.
