# Evaluator Panel E1C Selection Repair v1

Date: 2026-08-25 (Asia/Seoul)

## Why this step exists

The E1C prompt-source freeze v2 stopped before any HarmBench model output was
generated. The frozen 200-row selection contained three rows associated with
two behavior identifiers that were present in the official validation JSON but
absent from the pinned text-plus-multimodal behavior registry. The notebook
replay therefore could not reconstruct the behavior/context fields for those
rows.

This is a source/selection ambiguity, not a classifier result.

## Repair rule frozen before live output

The repair does not manually choose replacements. It reruns the original
label-balanced behavior round-robin algorithm after filtering the official
validation records to behavior IDs that resolve in the pinned registry and
contain the notebook-required fields.

The expected mechanical consequence is:

- old selection: 200 rows, 100/100 human-majority labels;
- unresolved old rows: 3, spanning two frozen behavior hashes;
- repaired selection: 200 rows, 100/100 labels;
- dropped records: 3;
- deterministically added records: 3;
- unresolved repaired rows: 0.

The old selection remains committed as development history and is never
silently overwritten. The repaired selection receives a new identity.

## Safety and claim boundary

This step:

- downloads no model weights;
- performs no model inference;
- produces no live HarmBench predictions;
- generates no new jailbreak outputs;
- opens no Stage A, causal oracle, sufficiency oracle, held-out split, or
  wavelet experiment.

A pass authorizes only a new prompt-source freeze using the repaired selection.
It does not authorize live HarmBench inference by itself.

## GitHub execution issue also addressed

The previous branch head was authored by `github-actions[bot]`, which caused
new pull-request checks to end immediately as `action_required` with no jobs.
This repair is committed through the authenticated GitHub connector so the
branch head returns to a user-authored commit and the static repair workflow can
execute normally.
