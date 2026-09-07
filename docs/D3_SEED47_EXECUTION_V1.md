# D3 seed-47 execution V1

**EXACT 398-RECORD FINAL-SEED PLAN VERIFIED; BOUNDED TARGET GENERATION IN PROGRESS**

Seed 47 is the third and final target-generation seed in the frozen D3 exact-topology contract.
The plan contains only groups without a valid nontruncated panel-HARMFUL witness in seeds 11 or 23.
An independent group-key reconstruction matched the persisted plan exactly: 398 expected and
actual records, 398 unique IDs, and zero missing, unexpected, reordered, seed, or contract-hash
defects. It contains 333 DeepInception and 65 h4rm3l records, split across 192
`LAYOUT_PRESERVING_BLANK` and 206 `SOURCE_AWARE_OMIT` records. Plan SHA-256:
`a76509a45c9c459ede3485694ee6a2f9ed49958685884a03dcd1b973edf68c99`.

Four focused test files (10 tests) and Ruff passed before target execution. The first bounded chunk
committed execution orders 0--63 and stopped cleanly at 64/398. The cumulative audit found exact
plan-prefix order, 64 unique IDs, 64 matching private-record hashes, 64/64 operational and
evaluator-eligible rows, zero truncations, zero temporary files, zero residual experiment
processes, and zero storage retries. Mean inference time was 11.385 seconds. The next execution
order is 64.

The second bounded chunk committed execution orders 64--127 and stopped cleanly at 128/398. The
same cumulative audit passed over all 128 rows with zero plan-prefix, private-hash, operational,
eligibility, truncation, temporary-file, residual-process, or storage-retry defects. Mean inference
time for the new 64 rows was 10.524 seconds. The next execution order is 128.

The third bounded chunk committed execution orders 128--191 and stopped cleanly at 192/398. The
same cumulative audit passed over all 192 rows without a defect. Mean inference time for the new
64 rows was 11.287 seconds. The next execution order is 192.

The fourth bounded chunk committed execution orders 192--255 and stopped cleanly at 256/398. The
same cumulative audit passed over all 256 rows without a defect. Mean inference time for the new
64 rows was 9.739 seconds. The next execution order is 256.

The fifth bounded chunk committed execution orders 256--319 and stopped cleanly at 320/398. The
same cumulative audit passed over all 320 rows without a defect. Mean inference time for the new
64 rows was 10.395 seconds. The next execution order is 320, with 78 target calls remaining.

The sixth bounded chunk committed execution orders 320--383 and stopped cleanly at 384/398. The
same cumulative audit passed over all 384 rows without a defect. Mean inference time for the new
64 rows was 7.193 seconds. The next execution order is 384, with 14 target calls remaining.

The final chunk committed execution orders 384--397 and finalized all 398 target rows. The final
audit found exact plan order, 398 unique IDs, 398 matching private-record hashes, 398/398
operational and evaluator-eligible rows, zero truncations, matching data-byte/data-hash/plan-hash
summary bindings, and no progress, temporary, or process residue. Summed per-record target
inference time was 1.100 hours. Generation SHA-256:
`2414b2154c5490a163e95759a39ac4ad005f115c9198982bb20f60d0e0179b09`.

The target-generation stage is complete. The next operation is the unchanged seed-47 Qwen3Guard
axis; panel and topology outcomes remain sealed.

The Qwen3Guard axis then completed 398/398 rows in 278.473 seconds. The independent audit found
exact plan ID/order agreement, 398 unique rows, 398/398 strict safety and refusal parses, zero
output-limit stops, matching data/summary/contract bindings, and no progress, temporary, or process
residue. Fifteen `Controversial` safety labels are valid parser outputs and remain subject to the
frozen abstaining-panel rule. One transient destination lock was recovered by the operational
launcher. Data SHA-256:
`b00723e187ec1738dd39035132a8fbe62b253e155028c752be25f716568eaca7`.

The next operation is the unchanged sequential JailMeter axis. Panel and topology outcomes remain
sealed until both axes are immutable.

The sequential JailMeter axis completed 398/398 rows in 4,380.917 seconds. The independent audit
found exact plan ID/order agreement, 398 unique rows, 397 strict binary parses, and one frozen
output-limit stop at execution order 192. That row is retained as a measurement-ineligible panel
ABSTAIN observation; there was no retry or post-outcome parameter change. No other parse failure
occurred. Data/summary/contract bindings matched, no progress, temporary, or process residue
remained, and GPU memory returned to 375 MiB. Data SHA-256:
`bd72f427fc5d4b1190fd1be0a2f5d74c615e069db4695ca7296a948a942c43a3`.

Both seed-47 evaluator axes are now immutable. The next operation is the hash-guarded V1.1 phase
finalizer followed by an implementation-independent panel reconstruction.

The phase finalizer produced HARMFUL 86, SAFE 256, and ABSTAIN 56, with 397/398 rows
measurement-eligible. A separate implementation reconstructed every panel field directly from the
generation and two evaluator-axis rows and found zero decision, ID/order, metadata, response-hash,
or result-binding mismatch. Across the original 888 exact groups, 576 now have a valid HARMFUL
witness and 312 have none.

Applying the frozen candidate rule leaves 81 nonempty subsets that are panel SAFE under both
neutralizers in all three seeds: 56 DeepInception and 25 h4rm3l. The fixed control universe maps
these candidates to exactly 324 structure-matched capability controls, four per subset. This is a
control denominator, not a recovered/minimal-topology result. Control outcomes and the D3 gate
remain unopened.

Before the 324-control run, a V1 operational wrapper was frozen to reuse the already tested atomic
replace retry primitive for safe progress files. It changes no candidate, prompt, target model,
decoding setting, capability predicate, or final gate. Ten focused tests and Ruff passed. The
authoritative amendment is
`configs/natural_language_localization/d3_controls_operational_v1.json`.

The control run completed 324/324 records in 1,471.286 seconds: 302 passed and 22 failed the frozen
capability predicate. The independent audit exactly reconstructed the 81-candidate/324-control
selection and found zero selected-plan, order, metadata, private-hash, or predicate mismatches;
there were zero operational failures, truncations, prompt echoes, temporary files, residual
processes, or storage retries. Sixty-four candidate subsets passed all four controls and 17 were
capability-confounded. All 22 record-level failures were required-substring misses on
DeepInception structure-matched controls; h4rm3l controls had zero failures. This distribution is
reported, not repaired or filtered post hoc. The exact-topology finalizer is next.

No seed-47 evaluator or panel output exists yet. Consequently, no recovered/minimal topology,
neutralizer recurrence, capability-control, Jaccard, or D3 gate claim is open.
