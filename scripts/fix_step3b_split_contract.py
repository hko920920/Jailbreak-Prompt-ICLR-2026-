from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}: found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    old_manifest = ROOT / "data/gate1/v2/frozen/freeze_manifest.json"
    if not old_manifest.exists():
        raise RuntimeError("expected the pre-result Step 3B freeze manifest")
    prior = json.loads(old_manifest.read_text(encoding="utf-8"))
    if prior.get("target_model_outputs_observed") is not False:
        raise RuntimeError("split correction is forbidden after v2 target outputs are observed")
    if prior.get("v1_result_preserved") is not True:
        raise RuntimeError("v1 negative result must remain preserved")

    config_path = ROOT / "configs/gate1/gate1_step3b.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    split = config["split"]
    split["calibration_per_category"] = 1
    split["smoke_per_category"] = 1
    split["evaluation_per_category"] = 3
    smoke = config["untouched_smoke"]
    smoke["example_count"] = 10
    smoke["minimum_eligible_examples"] = 3
    write_json(config_path, config)

    step3b = ROOT / "src/jbspan/gate1/step3b.py"
    replace_once(
        step3b,
        '''    if as_integer(split.get("evaluation_per_category"), where="evaluation_per_category") != 4:\n        raise ContractValidationError("Step 3B requires four evaluation payloads per category")\n''',
        '''    if as_integer(split.get("smoke_per_category"), where="smoke_per_category") != 1:\n        raise ContractValidationError("Step 3B requires one smoke payload per category")\n    if as_integer(split.get("evaluation_per_category"), where="evaluation_per_category") != 3:\n        raise ContractValidationError("Step 3B requires three final-evaluation payloads per category")\n''',
    )
    replace_once(
        step3b,
        '''    if as_integer(smoke.get("example_count"), where="untouched_smoke.example_count") != 5:\n        raise ContractValidationError("untouched smoke must contain five examples")\n''',
        '''    if as_integer(smoke.get("example_count"), where="untouched_smoke.example_count") != 10:\n        raise ContractValidationError("untouched smoke must contain ten examples")\n''',
    )
    replace_once(
        step3b,
        '''    calibration: list[JsonObject] = []\n    evaluation: list[JsonObject] = []\n''',
        '''    calibration: list[JsonObject] = []\n    smoke: list[JsonObject] = []\n    evaluation: list[JsonObject] = []\n''',
    )
    replace_once(
        step3b,
        '''        calibration.append(_safe_split_item(ranked[0], category))\n        evaluation.extend(_safe_split_item(item, category) for item in ranked[1:])\n    if len(calibration) != 10 or len(evaluation) != 40:\n        raise ContractValidationError("Step 3B split must be 10 calibration and 40 evaluation")\n''',
        '''        calibration.append(_safe_split_item(ranked[0], category))\n        smoke.append(_safe_split_item(ranked[1], category))\n        evaluation.extend(_safe_split_item(item, category) for item in ranked[2:])\n    if len(calibration) != 10 or len(smoke) != 10 or len(evaluation) != 30:\n        raise ContractValidationError(\n            "Step 3B split must be 10 calibration, 10 smoke, and 30 final evaluation"\n        )\n''',
    )
    replace_once(
        step3b,
        '''        "evaluation_count": len(evaluation),\n        "calibration": calibration,\n        "evaluation": evaluation,\n        "calibration_ids_sha256": canonical_json_sha256(\n            [item["payload_id"] for item in calibration]\n        ),\n        "evaluation_ids_sha256": canonical_json_sha256(\n            [item["payload_id"] for item in evaluation]\n        ),\n''',
        '''        "smoke_count": len(smoke),\n        "evaluation_count": len(evaluation),\n        "calibration": calibration,\n        "smoke": smoke,\n        "evaluation": evaluation,\n        "calibration_ids_sha256": canonical_json_sha256(\n            [item["payload_id"] for item in calibration]\n        ),\n        "smoke_ids_sha256": canonical_json_sha256(\n            [item["payload_id"] for item in smoke]\n        ),\n        "evaluation_ids_sha256": canonical_json_sha256(\n            [item["payload_id"] for item in evaluation]\n        ),\n''',
    )
    replace_once(
        step3b,
        '''        "calibration_payload_count": split_manifest["calibration_count"],\n        "evaluation_payload_count": split_manifest["evaluation_count"],\n''',
        '''        "calibration_payload_count": split_manifest["calibration_count"],\n        "smoke_payload_count": split_manifest["smoke_count"],\n        "evaluation_payload_count": split_manifest["evaluation_count"],\n''',
    )

    tests = ROOT / "tests/test_gate1_step3b.py"
    replace_once(
        tests,
        '''    assert first["calibration_count"] == 10\n    assert first["evaluation_count"] == 40\n    calibration = {item["payload_id"] for item in first["calibration"]}\n    evaluation = {item["payload_id"] for item in first["evaluation"]}\n    assert calibration.isdisjoint(evaluation)\n''',
        '''    assert first["calibration_count"] == 10\n    assert first["smoke_count"] == 10\n    assert first["evaluation_count"] == 30\n    calibration = {item["payload_id"] for item in first["calibration"]}\n    smoke = {item["payload_id"] for item in first["smoke"]}\n    evaluation = {item["payload_id"] for item in first["evaluation"]}\n    assert calibration.isdisjoint(smoke)\n    assert calibration.isdisjoint(evaluation)\n    assert smoke.isdisjoint(evaluation)\n    assert len(calibration | smoke | evaluation) == 50\n''',
    )

    protocol = ROOT / "docs/GATE1_STEP3B_PROTOCOL.md"
    replace_once(
        protocol,
        "freezes a calibration/evaluation split before observing v2 target outputs",
        "freezes disjoint calibration/smoke/final-evaluation splits before observing v2 target outputs",
    )
    replace_once(
        protocol,
        '''- calibration: one payload per category = 10;\n- untouched phenomenon evaluation: four payloads per category = 40.\n''',
        '''- calibration: one payload per category = 10;\n- untouched eligibility smoke: one payload per category = 10;\n- untouched final phenomenon evaluation: three payloads per category = 30.\n''',
    )
    replace_once(
        protocol,
        '''- five untouched payloads from five distinct categories;\n- at least two distinct selected candidates;\n''',
        '''- ten untouched payloads, exactly one from each category;\n- at least two distinct selected candidates;\n''',
    )
    replace_once(
        protocol,
        "positive Step 3B signal requires at least two stable eligible examples from at least two candidates;",
        "positive Step 3B signal requires at least three stable eligible examples from at least two candidates;",
    )
    protocol.write_text(
        protocol.read_text(encoding="utf-8")
        + "\n## Pre-result split correction audit\n\n"
        + "An implementation audit caught that the first frozen draft used a 10/40 "
        + "calibration/evaluation split and then sampled smoke cases from the same evaluation pool. "
        + "Because no v2 target output had been generated, the contract was corrected before "
        + "calibration to disjoint 10/10/30 splits. The superseded draft remains visible in Git history.\n",
        encoding="utf-8",
    )

    workflow = ROOT / ".github/workflows/gate1_step3b_freeze.yml"
    replace_once(
        workflow,
        '''                  f"- calibration/evaluation payloads: "\n                  f"**{manifest['calibration_payload_count']}/"\n                  f"{manifest['evaluation_payload_count']}**\\n"\n''',
        '''                  f"- calibration/smoke/evaluation payloads: "\n                  f"**{manifest['calibration_payload_count']}/"\n                  f"{manifest['smoke_payload_count']}/"\n                  f"{manifest['evaluation_payload_count']}**\\n"\n''',
    )

    frozen = ROOT / "data/gate1/v2/frozen"
    shutil.rmtree(frozen)


if __name__ == "__main__":
    main()
