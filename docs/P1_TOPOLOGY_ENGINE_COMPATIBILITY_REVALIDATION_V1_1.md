# P1 Topology Engine Compatibility Revalidation V1.1

Date: 2026-09-04 (Asia/Seoul)  
Decision: **PASS**  
Evidence class: **PROTOCOL IMPLEMENTATION; NO PAPER-VALID TOPOLOGY EVIDENCE**

T0 introduced the panel-level `SAFE_NONASSISTANCE` ontology value while retaining both legacy safe
subtypes. This was an additive implementation change. The current topology engine was therefore
rerun on the unchanged harmless P1 synthetic contract before T0 was finalized.

- current harmless synthetic self-checks: **10/10 PASS**;
- current result identity: `079758ed31856eb0b1c23cfd7240c9c81439814170b41deb33ca667efaea84f8`;
- current result file SHA-256: `bca4cd85ede77123906756a9c529c756cfba1a03f1aa033f2ddfb2144fed328b`;
- current result: [`p1_gate.safe.json`](../data/natural_language_localization/topology_engine_p1_v1_1/p1_gate.safe.json).

The original 2026-08-31 artifact remains byte-identical at its original path because the frozen P2
contract refers to it:

- historical identity: `360427235f8954723cb6de4d001f12d4fb541285301096d5b15dd220b5c6d2f4`;
- historical file SHA-256: `7aae440ba84398db6958d4f2d6f08e46bf69c3de8b260dc3dd352a41a9f954b3`;
- historical result: [`p1_gate.safe.json`](../data/natural_language_localization/topology_engine_p1_v1/p1_gate.safe.json).

T0 refers only to the current compatibility-revalidation artifact. P2 historical provenance still
resolves to the preserved original artifact. Neither run called a target model, used a harmful
payload, or observed a topology outcome.
