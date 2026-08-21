# Automated Gate 1 data contract

This directory contains public, non-operational registry metadata and JSON schemas. It must not
contain raw harmful payloads, rendered attack prompts, or target-model harmful completions.

## Files

- `payload_source_registry.json`: pinned source and deterministic stratified split policy.
- `payload_registry.schema.json`: safe generated payload-registry schema; no raw payload field.
- `primitive_registry.json`: typed wrapper primitives and neutral templates.
- `composition_grammar.json`: primary and held-out composition families.
- `neutralizer_registry.json`: two primary typed interventions plus one diagnostic operator.
- `benchmark_record.schema.json`: character/UTF-8 provenance before tokenizer freeze.
- `tokenized_provenance.schema.json`: model-specific token provenance bound by prompt hash.

The source revision prefix must be resolved to a full immutable revision and source-file digest
when Step 2 materializes the payload registry.
