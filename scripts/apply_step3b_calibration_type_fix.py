from __future__ import annotations

from pathlib import Path

TARGET = Path("src/jbspan/gate1/step3b_calibration.py")


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match, found {count}: {old[:80]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''def _array(value: object, *, where: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(f"{where} must be an array")
    return value


''',
        '''def _array(value: object, *, where: str) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(f"{where} must be an array")
    return value


def _integer(value: object, *, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"{where} must be an integer")
    return value


def _number(value: object, *, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError(f"{where} must be numeric")
    return float(value)


''',
    )
    text = replace_once(
        text,
        '''            -int(row["eligible_count"]),
            int(row["attack_abstention_count"]),
''',
        '''            -_integer(row["eligible_count"], where="eligible_count"),
            _integer(
                row["attack_abstention_count"],
                where="attack_abstention_count",
            ),
''',
    )
    text = replace_once(
        text,
        '''        row for row in ranked if int(row["eligible_count"]) >= minimum_eligible
''',
        '''        row
        for row in ranked
        if _integer(row["eligible_count"], where="eligible_count")
        >= minimum_eligible
''',
    )
    text = replace_once(
        text,
        '''        row = source_index[int(item["source_row_index"])]
''',
        '''        source_row_index = _integer(
            item["source_row_index"],
            where="source_row_index",
        )
        row = source_index[source_row_index]
''',
    )
    text = replace_once(
        text,
        '''    frozen_candidate_index = {
        str(item["candidate_id"]): _object(item, where="candidate")
        for item in _array(frozen_candidates["candidates"], where="candidates")
    }
''',
        '''    frozen_candidate_index: dict[str, JsonDict] = {}
    for raw_candidate in _array(
        frozen_candidates["candidates"],
        where="candidates",
    ):
        candidate = _object(raw_candidate, where="candidate")
        frozen_candidate_index[str(candidate["candidate_id"])] = candidate
''',
    )
    text = replace_once(
        text,
        '''        if len(rendered.nodes) != int(expected["node_count"]):
''',
        '''        expected_node_count = _integer(
            expected["node_count"],
            where="candidate.node_count",
        )
        if len(rendered.nodes) != expected_node_count:
''',
    )
    text = replace_once(
        text,
        '''    if int(split["smoke_count"]) != 10 or int(split["evaluation_count"]) != 30:
''',
        '''    smoke_count = _integer(split["smoke_count"], where="smoke_count")
    evaluation_count = _integer(
        split["evaluation_count"],
        where="evaluation_count",
    )
    if smoke_count != 10 or evaluation_count != 30:
''',
    )
    text = replace_once(
        text,
        '''    tokenizer = AutoTokenizer.from_pretrained(
''',
        '''    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
''',
    )
    text = replace_once(
        text,
        '''    seed = int(calibration["seed"])
    if seed not in [
        int(item) for item in _array(generation["seeds"], where="generation seeds")
    ]:
''',
        '''    seed = _integer(calibration["seed"], where="calibration.seed")
    generation_seeds = [
        _integer(item, where="generation seed")
        for item in _array(generation["seeds"], where="generation seeds")
    ]
    if seed not in generation_seeds:
''',
    )
    text = replace_once(
        text,
        '''                "n_predict": int(generation["max_tokens"]),
                "temperature": float(generation["temperature"]),
                "top_p": float(generation["top_p"]),
                "top_k": int(generation["top_k"]),
''',
        '''                "n_predict": _integer(
                    generation["max_tokens"],
                    where="generation.max_tokens",
                ),
                "temperature": _number(
                    generation["temperature"],
                    where="generation.temperature",
                ),
                "top_p": _number(
                    generation["top_p"],
                    where="generation.top_p",
                ),
                "top_k": _integer(
                    generation["top_k"],
                    where="generation.top_k",
                ),
''',
    )
    text = replace_once(
        text,
        '''        minimum_eligible=int(selection["minimum_eligible_payloads_per_candidate"]),
        minimum_selected=int(selection["minimum_selected_candidates"]),
        maximum_selected=int(selection["maximum_selected_candidates"]),
''',
        '''        minimum_eligible=_integer(
            selection["minimum_eligible_payloads_per_candidate"],
            where="minimum_eligible_payloads_per_candidate",
        ),
        minimum_selected=_integer(
            selection["minimum_selected_candidates"],
            where="minimum_selected_candidates",
        ),
        maximum_selected=_integer(
            selection["maximum_selected_candidates"],
            where="maximum_selected_candidates",
        ),
''',
    )

    TARGET.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
