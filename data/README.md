# Data handling

This repository does not commit raw jailbreak benchmark data or unrestricted model outputs.

## Expected local layout

```text
data/
  raw/                  # ignored; original licensed sources
  processed/            # ignored; normalized paired examples
  manifests/            # safe IDs, hashes, licenses, split definitions
```

## Pair schema

Required fields:

- `id`
- `behavior`
- `original_prompt`
- `jailbreak_prompt`
- `attack_family`
- `metadata`

## Freeze protocol

1. Normalize and deduplicate examples.
2. Remove prompt leakage or overlap across development and evaluation sets.
3. Freeze evaluation IDs before tuning thresholds or search parameters.
4. Store SHA-256 hashes and source/license metadata.
5. Never commit provider credentials, full request logs, or unrestricted harmful completions.
6. Use redacted examples in public artifacts when necessary.
