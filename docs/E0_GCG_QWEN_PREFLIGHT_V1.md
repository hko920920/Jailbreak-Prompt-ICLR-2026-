# E0 GCG–Qwen Tokenizer Preflight v1

This gate closes the compatibility gap left by the GCG static audit before the
h4rm3l–GCG signal screen can materialize any private prompt or call the target
model.

It downloads only the pinned Qwen2.5 tokenizer and metadata. It never imports
or loads an `AutoModel`, performs a forward pass, generates text, optimizes a
control, or uses a real harmful payload.

The harmless audit renders one synthetic user/assistant exchange with the
official 20-unit GCG control initialization. It verifies:

- the control text maps to exactly 20 Qwen tokens;
- the assistant target starts after the control slice;
- the 20 control positions partition into six contiguous blocks;
- all 64 block-subset masks preserve token count and slice positions;
- at least two neutralizer candidates are one-token, position-aware
  replacements at every control position;
- every transformed sequence decodes and re-encodes to the identical token ID
  sequence.

Only hashes, counts, slice indices, symbolic candidate identifiers, and PASS or
FAIL states enter the public result. A PASS authorizes the already-frozen
signal-screen runtime bundle. A compatibility failure blocks target inference
and requires an adapter repair under a new frozen contract.
