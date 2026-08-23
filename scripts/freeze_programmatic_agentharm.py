from __future__ import annotations

import argparse
import ast
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from jbspan.programmatic_agentharm import (
    SourceGate,
    assign_grouped_splits,
    audit_grading_source,
    load_behavior_records,
    safe_manifest,
    select_programmatic_records,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Freeze the judge-free AgentHarm source contract without model inference."
    )
    value.add_argument("--config", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--cache-dir", type=Path, required=True)
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def request_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "jbspan-gate0/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(request_bytes(url))


def download_github_file(
    *,
    repository: str,
    revision: str,
    path: str,
    expected_blob_sha: str,
    destination: Path,
) -> None:
    quoted_path = urllib.parse.quote(path, safe="/")
    metadata_url = (
        f"https://api.github.com/repos/{repository}/contents/{quoted_path}"
        f"?ref={urllib.parse.quote(revision, safe='')}"
    )
    metadata = json.loads(request_bytes(metadata_url).decode("utf-8"))
    if not isinstance(metadata, dict):
        raise RuntimeError("GitHub contents metadata must be an object")
    observed_blob = metadata.get("sha")
    if observed_blob != expected_blob_sha:
        raise RuntimeError(
            f"Git blob changed for {path}: {observed_blob!r} != {expected_blob_sha!r}"
        )
    download_url = metadata.get("download_url")
    if not isinstance(download_url, str) or not download_url:
        raise RuntimeError(f"GitHub returned no download URL for {path}")
    download(download_url, destination)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def required_object(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{where} must be an object")
    return value


def required_string(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{where} must be a non-empty string")
    return value


def required_int(value: object, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise RuntimeError(f"{where} must be an integer")
    return value


def pinned_dataset_revision(utils_source: str) -> str:
    tree = ast.parse(utils_source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "AGENTHARM_DATASET_REVISION":
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
    raise RuntimeError("official AgentHarm dataset revision assignment not found")


def main() -> int:
    args = parser().parse_args()
    config = load_json(args.config)
    if config.get("schema_version") != "programmatic-agentharm-gate0-config-v1":
        raise RuntimeError("unsupported Gate 0 config")
    if config.get("frozen") is not True:
        raise RuntimeError("Gate 0 config must be frozen before source observation")

    sources = required_object(config.get("sources"), "sources")
    thresholds = required_object(config.get("minimum_inventory"), "minimum_inventory")
    split = required_object(config.get("split"), "split")

    inspect_repository = required_string(
        sources.get("inspect_evals_repository"), "inspect_evals_repository"
    )
    source_revision = required_string(
        sources.get("inspect_evals_revision"), "inspect_evals_revision"
    )
    dataset_revision = required_string(
        sources.get("agentharm_dataset_revision"), "agentharm_dataset_revision"
    )
    grading_path = required_string(sources.get("grading_path"), "grading_path")
    grading_blob = required_string(
        sources.get("grading_git_blob_sha"), "grading_git_blob_sha"
    )
    utils_path = required_string(sources.get("utils_path"), "utils_path")
    utils_blob = required_string(sources.get("utils_git_blob_sha"), "utils_git_blob_sha")
    validation_path = required_string(
        sources.get("validation_dataset_path"), "validation_dataset_path"
    )
    test_path = required_string(sources.get("test_dataset_path"), "test_dataset_path")

    grading_file = args.cache_dir / "harmful_grading_functions.py"
    utils_file = args.cache_dir / "utils.py"
    validation_file = args.cache_dir / "harmful_behaviors_validation.json"
    test_file = args.cache_dir / "harmful_behaviors_test_public.json"
    download_github_file(
        repository=inspect_repository,
        revision=source_revision,
        path=grading_path,
        expected_blob_sha=grading_blob,
        destination=grading_file,
    )
    download_github_file(
        repository=inspect_repository,
        revision=source_revision,
        path=utils_path,
        expected_blob_sha=utils_blob,
        destination=utils_file,
    )
    official_revision = pinned_dataset_revision(utils_file.read_text(encoding="utf-8"))
    if official_revision != dataset_revision:
        raise RuntimeError(
            "dataset revision differs from official adapter: "
            f"{official_revision} != {dataset_revision}"
        )

    dataset_base = (
        "https://huggingface.co/datasets/ai-safety-institute/AgentHarm/resolve/"
        f"{dataset_revision}/"
    )
    download(dataset_base + validation_path + "?download=true", validation_file)
    download(dataset_base + test_path + "?download=true", test_file)

    observed_hashes = {
        "grading": sha256_file(grading_file),
        "utils": sha256_file(utils_file),
        "validation": sha256_file(validation_file),
        "test_public": sha256_file(test_file),
    }

    grading_source = grading_file.read_text(encoding="utf-8")
    audits = audit_grading_source(grading_source)
    validation_all = load_behavior_records(load_json(validation_file))
    test_all = load_behavior_records(load_json(test_file))
    validation_records = select_programmatic_records(validation_all, audits)
    test_records = select_programmatic_records(test_all, audits)

    gate = SourceGate(
        minimum_base_behaviors=required_int(
            thresholds.get("base_behaviors"), "minimum_inventory.base_behaviors"
        ),
        minimum_total_rows=required_int(
            thresholds.get("total_rows"), "minimum_inventory.total_rows"
        ),
        minimum_categories=required_int(
            thresholds.get("categories"), "minimum_inventory.categories"
        ),
    )
    split_names = split.get("names")
    split_weights = split.get("weights")
    if not isinstance(split_names, list) or not all(
        isinstance(item, str) and item for item in split_names
    ):
        raise RuntimeError("split.names must be a list of strings")
    if not isinstance(split_weights, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in split_weights
    ):
        raise RuntimeError("split.weights must be a list of integers")

    assignments = assign_grouped_splits(
        test_records,
        seed=required_string(split.get("seed"), "split.seed"),
        split_names=tuple(split_names),
        split_weights=tuple(split_weights),
    )
    manifest = safe_manifest(
        source_revision=source_revision,
        dataset_revision=dataset_revision,
        grading_source_sha256=observed_hashes["grading"],
        utils_source_sha256=observed_hashes["utils"],
        grading_git_blob_sha=grading_blob,
        utils_git_blob_sha=utils_blob,
        validation_source_sha256=observed_hashes["validation"],
        test_source_sha256=observed_hashes["test_public"],
        audits=audits,
        validation_records=validation_records,
        test_records=test_records,
        assignments=assignments,
        gate=gate,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest["test_inventory"], indent=2, sort_keys=True))
    return 0 if manifest["status"] == "PROGRAMMATIC_AGENTHARM_GATE0_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
