"""Synthetic-only tests: never inspect project data or launch inference."""

import copy
import hashlib
import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts/prepare_pa_llama_development_source_v1.py"
)
SPEC = importlib.util.spec_from_file_location("pa_development_source_new", MODULE_PATH)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def h(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


@pytest.fixture
def records():
    plans, generations, materials = [], [], []
    for target in (m.TARGET, m.OTHER_TARGET):
        for position in range(45):
            for condition in m.CONDITIONS:
                payload = h(("P", position))
                prompt = payload if condition == "DIRECT" else h(("A", position))
                base = {
                    "target_id": target,
                    "payload_position": position,
                    "condition": condition,
                    "pair_id": h((target, position)),
                    "payload_sha256": payload,
                    "prompt_sha256": prompt,
                }
                record_id = h((target, position, condition))
                plans.append(
                    {
                        **base,
                        "phase_seed": 11,
                        "contract_sha256": m.OLD_CONTRACT,
                        "record_id": record_id,
                        "topic_sha256": h(("T", position // 3)),
                    }
                )
                generations.append(
                    {
                        **base,
                        "seed": 11,
                        "record_id": record_id,
                        "execution_identity_sha256": h(("E", record_id)),
                        "private_record_sha256": h(("F", record_id)),
                        "eligible_for_panel": False,
                        "response_sha256": h(("R", record_id)),
                    }
                )
                materials.append(
                    {
                        **base,
                        "topic_sha256": h(("T", position // 3)),
                        "partition_pass": True,
                        "payload_byte_occurrence_count": 1,
                        "prompt_utf8_bytes": 10,
                        "reserved_chat_marker_count": 0,
                        "unit_count": 0 if condition == "DIRECT" else 3,
                        "unit_manifest_sha256": h(("U", condition)),
                        "fragment_manifest_sha256": h(("V", condition)),
                    }
                )
    return plans, generations, materials


def test_all45_both_conditions_even_ineligible(records):
    rows = m.build_rows(*records)
    assert len(rows) == 90
    assert [row["payload_position"] for row in rows] == [p for p in range(45) for _ in range(2)]
    assert [row["condition"] for row in rows] == list(m.CONDITIONS) * 45
    assert all(row["source_target_id"] == m.TARGET for row in rows)
    assert all("response_sha256" not in row for row in rows)
    assert all("response" not in row for row in rows)


def test_order_does_not_select_cases(records):
    expected = m.build_rows(*records)
    assert m.build_rows(*(list(reversed(rows)) for rows in records)) == expected


def test_duplicate_execution_reference_rejected(records):
    records[1][2]["execution_identity_sha256"] = records[1][0]["execution_identity_sha256"]
    with pytest.raises(ValueError, match="DUPLICATE_PRIVATE_SOURCE_PATH"):
        m.build_rows(*records)


@pytest.mark.parametrize("source", [0, 1, 2])
def test_missing_record_rejected(records, source):
    records[source].pop()
    with pytest.raises(ValueError, match="FULL_DENOMINATOR"):
        m.build_rows(*records)


@pytest.mark.parametrize("source", [0, 1, 2])
def test_duplicates_rejected(records, source):
    records[source][1] = copy.deepcopy(records[source][0])
    with pytest.raises(ValueError):
        m.build_rows(*records)


@pytest.mark.parametrize(
    "field,value",
    [
        ("phase_seed", 23),
        ("phase_seed", True),
        ("contract_sha256", "0" * 64),
        ("payload_position", True),
        ("target_id", "new-target"),
        ("condition", "FAVORABLE"),
        ("payload_sha256", "bad"),
        ("prompt_sha256", "bad"),
        ("topic_sha256", "bad"),
    ],
)
def test_plan_identity_changes_rejected(records, field, value):
    records[0][0][field] = value
    with pytest.raises(ValueError):
        m.build_rows(*records)


@pytest.mark.parametrize(
    "field,value",
    [
        ("seed", 23),
        ("seed", True),
        ("private_record_sha256", "bad"),
        ("execution_identity_sha256", "../x"),
        ("prompt_sha256", "0" * 64),
    ],
)
def test_generation_changes_rejected(records, field, value):
    records[1][0][field] = value
    with pytest.raises(ValueError):
        m.build_rows(*records)


@pytest.mark.parametrize(
    "field,value",
    [
        ("partition_pass", False),
        ("payload_byte_occurrence_count", 2),
        ("payload_byte_occurrence_count", True),
        ("prompt_utf8_bytes", 0),
        ("prompt_utf8_bytes", True),
        ("reserved_chat_marker_count", 1),
        ("reserved_chat_marker_count", False),
        ("unit_count", 1),
        ("unit_count", False),
        ("topic_sha256", "0" * 64),
        ("unit_manifest_sha256", "bad"),
        ("fragment_manifest_sha256", "bad"),
    ],
)
def test_material_changes_rejected(records, field, value):
    records[2][0][field] = value
    with pytest.raises(ValueError):
        m.build_rows(*records)


@pytest.mark.parametrize("source", [0, 1, 2])
def test_raw_keys_rejected(records, source):
    records[source][0]["response"] = "synthetic text"
    with pytest.raises(ValueError, match="RAW_CONTENT"):
        m.build_rows(*records)


def test_nested_raw_key_rejected(records):
    records[1][0]["extra"] = [{"prompt": "synthetic"}]
    with pytest.raises(ValueError, match="RAW_CONTENT"):
        m.build_rows(*records)


def test_duplicate_json_key_rejected():
    with pytest.raises(ValueError, match="DUPLICATE_KEY"):
        m.strict_json('{"a":1,"a":2}')


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_rejected(constant):
    with pytest.raises(ValueError, match="NONFINITE"):
        m.strict_json('{"a":' + constant + "}")


@pytest.mark.parametrize("relative", ["../x", "C:/Windows/x", "x\\y"])
def test_unsafe_paths_rejected(tmp_path, relative):
    with pytest.raises(ValueError):
        m.resolve_path(tmp_path.resolve(), relative)


def test_prepare_stats_private_but_does_not_read(records, tmp_path_factory, monkeypatch):
    tmp_path = tmp_path_factory.mktemp("s")
    expected = m.build_rows(*records)
    for row in expected:
        path = tmp_path / row["private_source"]["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")  # Newly generated synthetic file, NOT old private data.
    calls = iter(records)
    monkeypatch.setattr(m, "read_pinned_safe", lambda *_: next(calls))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Private contents must not be read")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    result = m.prepare(tmp_path)
    assert result["old_private_content_reads"] == 0
    assert result["private_record_metadata_stats"] == 90
    assert result["prospective_files_also_contain_historical_responses"] is True
    assert result["execution_authorized"] is False
    assert result["private_content_access_authorized"] is False
    assert all(row["private_source"]["size_bytes"] == 1 for row in result["rows"])


def test_pinned_safe_source_must_match(tmp_path):
    path = tmp_path / "safe.jsonl"
    path.write_bytes(b"{}\n")
    pin = {"path": "safe.jsonl", "size_bytes": 3, "sha256": h("wrong")}
    with pytest.raises(ValueError, match="SAFE_SOURCE_DRIFT"):
        m.read_pinned_safe(tmp_path, pin)
