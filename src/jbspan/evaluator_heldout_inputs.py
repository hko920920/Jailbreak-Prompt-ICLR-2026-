from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jbspan.evaluator_panel_external_data import normalized_text_sha256, pair_sha256

JsonObject = dict[str, Any]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_LABEL_FIELDS = {
    "human_label",
    "human_annotation_count",
    "human_label_support_count",
    "human_unanimous",
}


@dataclass(frozen=True, slots=True)
class HeldoutInputRecord:
    record_id: str
    source_id: str
    source_locator_sha256: str
    behavior_group_sha256: str
    response_sha256: str
    strata: tuple[str, ...]
    evaluation_role: str
    goal_text: str
    response_text: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl_objects(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value: object = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def validate_identity_manifests(
    *,
    full_rows: Sequence[Mapping[str, Any]],
    primary_rows: Sequence[Mapping[str, Any]],
    stress_rows: Sequence[Mapping[str, Any]],
) -> list[JsonObject]:
    """Validate the label-free 803/144 split and return role-tagged identities."""

    expected = {"full": 947, "primary": 803, "stress": 144}
    for name, rows in (
        ("full", full_rows),
        ("primary", primary_rows),
        ("stress", stress_rows),
    ):
        if len(rows) != expected[name]:
            raise ValueError(f"unexpected {name} held-out record count")
        ids = [str(row.get("record_id")) for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate IDs in {name} held-out manifest")
        for row in rows:
            if row.get("human_label_sealed") is not True:
                raise ValueError(f"{name} held-out identity is not label-sealed")
            if _FORBIDDEN_LABEL_FIELDS.intersection(row):
                raise ValueError(f"{name} held-out identity leaks a human-label field")
            for field in (
                "record_id",
                "source_locator_sha256",
                "behavior_group_sha256",
                "response_sha256",
            ):
                value = row.get(field)
                if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
                    raise ValueError(f"invalid {field} in {name} held-out manifest")
            strata = row.get("strata")
            if not isinstance(strata, list) or not strata or not all(
                isinstance(value, str) and value for value in strata
            ):
                raise ValueError(f"invalid strata in {name} held-out manifest")

    primary_ids = {str(row["record_id"]) for row in primary_rows}
    stress_ids = {str(row["record_id"]) for row in stress_rows}
    if primary_ids & stress_ids:
        raise ValueError("primary and stress held-out identities overlap")
    full_index = {str(row["record_id"]): dict(row) for row in full_rows}
    if set(full_index) != primary_ids | stress_ids:
        raise ValueError("primary plus stress IDs do not equal the full held-out manifest")

    tagged: list[JsonObject] = []
    for role, rows in (("PRIMARY", primary_rows), ("EXPOSED_STRESS", stress_rows)):
        for row in rows:
            record_id = str(row["record_id"])
            if dict(row) != full_index[record_id]:
                raise ValueError("split held-out row differs from its full-manifest identity")
            source_id = str(row["source_id"])
            if role == "PRIMARY" and source_id not in {"harmbench", "strongreject"}:
                raise ValueError("primary held-out set contains an inadmissible source")
            if role == "EXPOSED_STRESS" and source_id != "jailbreakbench":
                raise ValueError("exposed stress set must contain only JailbreakBench")
            tagged.append({**dict(row), "evaluation_role": role})

    if len({str(row["response_sha256"]) for row in tagged}) != len(tagged):
        raise ValueError("held-out response hashes are not globally unique")
    primary_groups = {
        str(row["behavior_group_sha256"])
        for row in tagged
        if row["evaluation_role"] == "PRIMARY"
    }
    stress_groups = {
        str(row["behavior_group_sha256"])
        for row in tagged
        if row["evaluation_role"] == "EXPOSED_STRESS"
    }
    if len(primary_groups) != 161 or len(stress_groups) != 94:
        raise ValueError("held-out role behavior-group denominator mismatch")
    if primary_groups & stress_groups:
        raise ValueError("a behavior group crosses primary and exposed stress roles")
    return sorted(tagged, key=lambda row: str(row["record_id"]))


def load_and_validate_identity_manifests(
    *, root: Path, full_path: Path, primary_path: Path, stress_path: Path
) -> list[JsonObject]:
    return validate_identity_manifests(
        full_rows=load_jsonl_objects(root / full_path),
        primary_rows=load_jsonl_objects(root / primary_path),
        stress_rows=load_jsonl_objects(root / stress_path),
    )


def _source_specs(source_contract: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    values = source_contract.get("sources")
    if not isinstance(values, list):
        raise ValueError("source contract has no source list")
    output: dict[str, Mapping[str, Any]] = {}
    for value in values:
        if not isinstance(value, Mapping) or not isinstance(value.get("source_id"), str):
            raise ValueError("invalid source contract entry")
        output[str(value["source_id"])] = value
    if set(output) != {"strongreject", "jailbreakbench", "harmbench"}:
        raise ValueError("unexpected held-out source set")
    return output


def _verify_file(path: Path, spec: Mapping[str, Any]) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(spec["artifact_bytes"]):
        raise ValueError(f"source byte-size mismatch: {path}")
    if file_sha256(path) != str(spec["artifact_sha256"]):
        raise ValueError(f"source SHA-256 mismatch: {path}")


def _record_id(source_id: str, behavior_sha256: str, response_sha256: str) -> str:
    pair = pair_sha256(
        behavior_group_sha256=behavior_sha256,
        response_sha256=response_sha256,
    )
    return hashlib.sha256(f"{source_id}\0{pair}".encode()).hexdigest()


def _locator_sha256(source_id: str, locator: str) -> str:
    return hashlib.sha256(f"{source_id}\0{locator}".encode()).hexdigest()


def _git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def reconstruct_label_blind_inputs(
    *,
    root: Path,
    source_contract: Mapping[str, Any],
    identities: Sequence[Mapping[str, Any]],
) -> tuple[list[HeldoutInputRecord], JsonObject]:
    """Recover only prompt/response inputs for sealed IDs.

    The source artifacts contain annotations, but this path never reads a label
    by field name, validates a vote, constructs a label, or branches on one.
    Only source locator, goal, response, and non-label reporting strata are used.
    """

    root = root.resolve()
    expected = {str(row["record_id"]): row for row in identities}
    if len(expected) != len(identities):
        raise ValueError("held-out input identities are duplicated")
    matches: dict[str, HeldoutInputRecord] = {}
    scan_counts: dict[str, int] = {}

    def consider(
        *,
        source_id: str,
        locator: str,
        goal: str,
        response: str,
        strata: tuple[str, ...],
    ) -> None:
        behavior_sha = normalized_text_sha256(goal)
        response_sha = normalized_text_sha256(response)
        record_id = _record_id(source_id, behavior_sha, response_sha)
        identity = expected.get(record_id)
        if identity is None:
            return
        locator_sha = _locator_sha256(source_id, locator)
        if locator_sha != identity["source_locator_sha256"]:
            return
        if record_id in matches:
            raise ValueError("sealed held-out identity matched more than one raw row")
        if (
            source_id != identity["source_id"]
            or behavior_sha != identity["behavior_group_sha256"]
            or response_sha != identity["response_sha256"]
            or list(strata) != identity["strata"]
        ):
            raise ValueError("label-blind raw input differs from sealed identity")
        matches[record_id] = HeldoutInputRecord(
            record_id=record_id,
            source_id=source_id,
            source_locator_sha256=locator_sha,
            behavior_group_sha256=behavior_sha,
            response_sha256=response_sha,
            strata=strata,
            evaluation_role=str(identity["evaluation_role"]),
            goal_text=goal,
            response_text=response,
        )

    specs = _source_specs(source_contract)
    strong = specs["strongreject"]
    strong_path = root / str(strong["local_path"])
    _verify_file(strong_path, strong)
    strong_fields = [
        "forbidden_prompt",
        "jailbreak",
        "label_0",
        "label_1",
        "label_2",
        "label_3",
        "label_4",
        "model",
        "response",
        "label_median",
    ]
    with strong_path.open(encoding="utf-8-sig", newline="") as handle:
        strong_reader = csv.reader(handle)
        header = next(strong_reader)
        if header != strong_fields:
            raise ValueError("unexpected StrongREJECT input schema")
        count = 0
        for row_number, row in enumerate(strong_reader, start=2):
            count += 1
            if len(row) != len(header):
                raise ValueError("malformed StrongREJECT input row")
            consider(
                source_id="strongreject",
                locator=f"csv-row:{row_number:06d}",
                goal=row[0],
                response=row[8],
                strata=("source:strongreject",),
            )
    if count != int(strong["raw_rows"]):
        raise ValueError("StrongREJECT raw input count mismatch")
    scan_counts["strongreject"] = count

    jailbreakbench = specs["jailbreakbench"]
    jailbreakbench_path = root / str(jailbreakbench["local_path"])
    _verify_file(jailbreakbench_path, jailbreakbench)
    jailbreakbench_fields = [
        "Index",
        "goal",
        "prompt",
        "target_response",
        "human1",
        "human2",
        "human3",
        "human_majority",
        "harmbench_cf",
        "gpt4_cf",
        "llamaguard2_cf",
        "llama3_cf",
    ]
    with jailbreakbench_path.open(encoding="utf-8-sig", newline="") as handle:
        jailbreakbench_reader = csv.reader(handle)
        header = next(jailbreakbench_reader)
        if header != jailbreakbench_fields:
            raise ValueError("unexpected JailbreakBench input schema")
        count = 0
        seen_indices: set[int] = set()
        for row in jailbreakbench_reader:
            count += 1
            if len(row) != len(header):
                raise ValueError("malformed JailbreakBench input row")
            index = int(row[0])
            if index in seen_indices:
                raise ValueError("duplicate JailbreakBench input index")
            seen_indices.add(index)
            consider(
                source_id="jailbreakbench",
                locator=f"index:{index:06d}",
                goal=row[1],
                response=row[3],
                strata=("source:jailbreakbench",),
            )
    if count != int(jailbreakbench["raw_rows"]) or seen_indices != set(range(count)):
        raise ValueError("JailbreakBench raw input count/index mismatch")
    scan_counts["jailbreakbench"] = count

    harmbench = specs["harmbench"]
    harmbench_repo = root / str(harmbench["local_repository_path"])
    if _git(harmbench_repo, "rev-parse", "HEAD") != harmbench["repository_revision"]:
        raise ValueError("HarmBench input repository revision mismatch")
    validation_relative = str(harmbench["validation_artifact_path"])
    behavior_relative = str(harmbench["behavior_artifact_path"])
    expected_blobs = {
        "LICENSE": harmbench["repository_license_blob_sha1"],
        validation_relative: harmbench["validation_artifact_git_blob_sha1"],
        behavior_relative: harmbench["behavior_artifact_git_blob_sha1"],
    }
    for relative, expected_blob in expected_blobs.items():
        if _git(harmbench_repo, "rev-parse", f"HEAD:{relative}") != expected_blob:
            raise ValueError(f"HarmBench input blob mismatch: {relative}")
    changed = _git(
        harmbench_repo,
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--",
        "LICENSE",
        validation_relative,
        behavior_relative,
    )
    if changed:
        raise ValueError("pinned HarmBench input files have local modifications")

    behavior_fields = [
        "Behavior",
        "FunctionalCategory",
        "SemanticCategory",
        "Tags",
        "ContextString",
        "BehaviorID",
    ]
    behavior_by_id: dict[str, dict[str, str]] = {}
    with (harmbench_repo / behavior_relative).open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        behavior_reader = csv.DictReader(handle)
        if behavior_reader.fieldnames != behavior_fields:
            raise ValueError("unexpected HarmBench behavior input schema")
        for behavior_row in behavior_reader:
            behavior_id = behavior_row["BehaviorID"]
            if behavior_id in behavior_by_id:
                raise ValueError("duplicate HarmBench behavior input ID")
            behavior_by_id[behavior_id] = behavior_row

    raw_value: object = json.loads(
        (harmbench_repo / validation_relative).read_text(encoding="utf-8")
    )
    if not isinstance(raw_value, dict):
        raise ValueError("HarmBench validation input must be an object")
    raw_entries = 0
    matched_behavior_entries = 0
    for behavior_key, items in raw_value.items():
        if not isinstance(behavior_key, str) or not isinstance(items, list):
            raise ValueError("invalid HarmBench input grouping")
        for item_number, item in enumerate(items):
            raw_entries += 1
            if not isinstance(item, dict) or item.get("behavior_id") != behavior_key:
                raise ValueError("invalid HarmBench input behavior grouping")
            behavior_id = item.get("behavior_id")
            generation = item.get("generation")
            if not isinstance(behavior_id, str) or not isinstance(generation, str):
                raise ValueError("invalid HarmBench prompt/response input")
            behavior = behavior_by_id.get(behavior_id)
            if behavior is None:
                continue
            matched_behavior_entries += 1
            consider(
                source_id="harmbench",
                locator=f"behavior:{behavior_id}|item:{item_number}",
                goal=behavior["Behavior"],
                response=generation,
                strata=(
                    "source:harmbench",
                    f"harmbench_semantic:{behavior['SemanticCategory']}",
                    f"harmbench_functional:{behavior['FunctionalCategory']}",
                ),
            )
    if raw_entries != int(harmbench["raw_validation_entries"]):
        raise ValueError("HarmBench raw validation input count mismatch")
    if matched_behavior_entries != int(harmbench["expected_joined_entries"]):
        raise ValueError("HarmBench joined input count mismatch")
    scan_counts["harmbench"] = raw_entries

    missing = set(expected) - set(matches)
    if missing:
        raise ValueError(f"could not reconstruct {len(missing)} sealed held-out inputs")
    if set(matches) != set(expected):
        raise ValueError("label-blind reconstruction produced unexpected held-out IDs")
    ordered = [matches[str(row["record_id"])] for row in identities]
    audit: JsonObject = {
        "records_reconstructed": len(ordered),
        "source_scan_counts": dict(sorted(scan_counts.items())),
        "source_match_counts": {
            source: sum(record.source_id == source for record in ordered)
            for source in sorted(specs)
        },
        "primary_records": sum(record.evaluation_role == "PRIMARY" for record in ordered),
        "exposed_stress_records": sum(
            record.evaluation_role == "EXPOSED_STRESS" for record in ordered
        ),
        "human_label_fields_accessed": False,
        "human_vote_fields_accessed": False,
        "raw_text_written": False,
    }
    return ordered, audit
