from __future__ import annotations

import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).parents[1] / "scripts/qualify_jailmeter_runtime_e0g1b.py"
    spec = importlib.util.spec_from_file_location("jailmeter_runtime_e0g1b", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parser_requires_exactly_one_final_label_candidate() -> None:
    module = _module()
    parser = {
        "label_regex": r"<label>\s*(0|1)\s*</label>",
        "require_exactly_one_label_match": True,
    }
    assert module.parse_label("<reason>done</reason><label>1</label>", parser) == {
        "label": 1,
        "match_count": 1,
    }
    assert module.parse_label("no decision", parser) == {"label": None, "match_count": 0}
    assert module.parse_label("<label>1</label><label>0</label>", parser) == {
        "label": None,
        "match_count": 2,
    }


def test_system_prompt_extraction_is_static_and_does_not_import_runner(tmp_path: Path) -> None:
    module = _module()
    marker = tmp_path / "should-not-exist"
    runner = tmp_path / "runner.py"
    runner.write_text(
        'system_prompt_with_cot = "frozen prompt"\n'
        f'open({str(marker)!r}, "w").write("imported")\n',
        encoding="utf-8",
    )
    assert module.extract_system_prompt(runner) == "frozen prompt"
    assert not marker.exists()


def test_runtime_manifest_is_stable_and_sorted(tmp_path: Path) -> None:
    module = _module()
    (tmp_path / "z.dll").write_bytes(b"z")
    (tmp_path / "a.exe").write_bytes(b"a")
    rows, total, identity = module.runtime_manifest(tmp_path)
    assert [row["path"] for row in rows] == ["a.exe", "z.dll"]
    assert total == 2
    assert len(identity) == 64
