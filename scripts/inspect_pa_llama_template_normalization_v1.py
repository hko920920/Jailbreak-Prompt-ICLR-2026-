"""Derive the pinned llama.cpp Jinja lexer source digest without model execution.

Read-only and stdout-only. The raw GGUF metadata reader remains unchanged. This
implements source normalization at the exact runtime revision, not arbitrary
whitespace stripping or an observed-output-derived digest.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import inspect_pa_llama_gguf_identity_v1 as frozen_reader

READER_SHA256 = "9640a7c175fc0f83cc1ab9756dd08ce9ac23c0f0eab06cd178c7de9cfd84dc6e"
RAW_SHA256 = "e10ca381b1ccc5cf9db52e371f3b6651576caee0a630b452e2816b2d404d4b65"
RAW_BYTES = 4614
REVISION = "0177dcc7300bad8914bb838baabce87899812491"
LEXER_URL = (
    "https://raw.githubusercontent.com/ggml-org/llama.cpp/" + REVISION + "/common/jinja/lexer.cpp"
)


def lexer_source_normalization(source: bytes) -> bytes:
    """Equivalent to lexer.cpp lines 35-54; the suffix test uses ORIGINAL bytes."""
    if not source:
        return source
    normalized = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if source.endswith(b"\n"):
        normalized = normalized[:-1]
    return normalized


def literal_cpp_loop_reference(source: bytes) -> bytes:
    """Independent transliteration of the two find/erase/replace loops."""
    if not source:
        return source
    normalized = bytearray(source)
    position = 0
    while True:
        position = normalized.find(b"\r\n", position)
        if position < 0:
            break
        del normalized[position]
        position += 1
    position = 0
    while True:
        position = normalized.find(b"\r", position)
        if position < 0:
            break
        normalized[position] = 10
        position += 1
    if source[-1] == 10:
        normalized.pop()
    return bytes(normalized)


def newline_counts(source: bytes) -> dict:
    crlf = source.count(b"\r\n")
    return {
        "crlf_pairs": crlf,
        "lone_cr": source.count(b"\r") - crlf,
        "lone_lf": source.count(b"\n") - crlf,
        "ends_lf": source.endswith(b"\n"),
        "ends_cr": source.endswith(b"\r"),
    }


def prelexer_patch_conditions(source: bytes) -> dict:
    """Exact conjunction guards in common/chat.cpp lines 694-710, one-based."""
    return {
        "channel_content_guard_matches": (
            b"<|channel|>" in source and b"in message.content or" in source
        ),
        "tool_calls_content_guard_matches": (
            b"[TOOL_CALLS]" in source and b"if (message['content'] is none or" in source
        ),
    }


def read_template(root: Path) -> tuple[bytes, dict]:
    root = root.resolve(strict=True)
    reader_path = Path(frozen_reader.__file__).resolve(strict=True)
    reader_path.relative_to(root)
    if frozen_reader.descriptor(reader_path, root)["sha256"] != READER_SHA256:
        raise ValueError("frozen GGUF reader changed")
    path = (root / frozen_reader.MODEL).resolve(strict=True)
    path.relative_to(root)
    with path.open("rb") as stream:
        metadata = frozen_reader.inspect_metadata(stream, path.stat().st_size)
        if metadata["native_chat_template_sha256"] != RAW_SHA256:
            raise ValueError("raw template differs from pre-existing authority")
        stream.seek(0)
        reader = frozen_reader.MetadataReader(stream, path.stat().st_size)
        reader.read(24)
        template = None
        for _ in range(metadata["metadata_count"]):
            key = reader.string(keep=True)
            value_type = reader.u32()
            if key == b"tokenizer.chat_template":
                if value_type != 8:
                    raise ValueError("native template is not a string")
                template = reader.string(keep=True)
            else:
                reader.skip_value(value_type)
    if template is None or len(template) != RAW_BYTES:
        raise ValueError("raw template length differs from pre-existing authority")
    if hashlib.sha256(template).hexdigest() != RAW_SHA256:
        raise ValueError("second metadata traversal disagrees with frozen reader")
    template.decode("utf-8", errors="strict")
    return template, metadata


def inspect(root: Path) -> dict:
    raw, metadata = read_template(root)
    patch_conditions = prelexer_patch_conditions(raw)
    if any(patch_conditions.values()):
        raise ValueError("a pre-lexer template patch condition matches; newline-only proof invalid")
    normalized = lexer_source_normalization(raw)
    normalized.decode("utf-8", errors="strict")
    if normalized != literal_cpp_loop_reference(raw):
        raise ValueError("normalization implementations disagree")

    def without_newlines(value: bytes) -> bytes:
        return value.replace(b"\r", b"").replace(b"\n", b"")

    if without_newlines(raw) != without_newlines(normalized):
        raise ValueError("non-newline bytes changed")
    return {
        "schema_version": "jbspan-pa-llama-native-template-normalization-v1",
        "evidence_class": "STATIC_SOURCE_DERIVED_RUNTIME_IDENTITY_NOT_MODEL_OUTPUT",
        "model_path": frozen_reader.MODEL,
        "frozen_reader_sha256": READER_SHA256,
        "raw_template_utf8_bytes": len(raw),
        "raw_template_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_newline_counts": newline_counts(raw),
        "lexer_source_utf8_bytes": len(normalized),
        "lexer_source_sha256": hashlib.sha256(normalized).hexdigest(),
        "lexer_source_newline_counts": newline_counts(normalized),
        "normalization": "CRLF to LF; CR to LF; remove one final byte iff ORIGINAL ends LF",
        "other_bytes_unchanged": True,
        "prelexer_patch_conditions": patch_conditions,
        "both_prelexer_patch_conditions_absent": True,
        "reference_loop_equivalence": True,
        "upstream_revision": REVISION,
        "upstream_source_url": LEXER_URL,
        "upstream_source_lines_one_based": [30, 54],
        "prelexer_source_url": (
            "https://raw.githubusercontent.com/ggml-org/llama.cpp/" + REVISION + "/common/chat.cpp"
        ),
        "prelexer_source_lines_one_based": [692, 711],
        "metadata_end_offset": metadata["metadata_end_offset"],
        "full_model_rehashed_this_inspection": False,
        "tensor_descriptors_or_data_parsed": False,
        "inference_calls": 0,
        "server_launches": 0,
        "files_written": 0,
    }


def self_test() -> dict:
    guards = [
        (b"<|channel|>", False, False),
        (b"<|channel|> in message.content or", True, False),
        (b"[TOOL_CALLS]", False, False),
        (b"[TOOL_CALLS] if (message['content'] is none or", False, True),
        (b"in message.content or if (message['content'] is none or", False, False),
    ]
    for source, channel_expected, tools_expected in guards:
        assert prelexer_patch_conditions(source) == {
            "channel_content_guard_matches": channel_expected,
            "tool_calls_content_guard_matches": tools_expected,
        }
    fixtures = [
        (b"", b""),
        (b"x", b"x"),
        (b"x\n", b"x"),
        (b"x\n\n", b"x\n"),
        (b"x\r\n", b"x"),
        (b"x\r", b"x\n"),
        (b"x\r\n\r\n", b"x\n"),
        (b"x\r\ny\rz\n", b"x\ny\nz"),
        (b"x\n \t", b"x\n \t"),
        ("가\r\né\t \n".encode(), "가\né\t ".encode()),
        (bytes(range(256)), bytes(range(13)) + b"\n" + bytes(range(14, 256))),
    ]
    for source, expected in fixtures:
        assert lexer_source_normalization(source) == expected
        assert literal_cpp_loop_reference(source) == expected
    exhaustive_checks = 0
    for size in range(6):
        for pieces in itertools.product((b"\r", b"\n", b"\t", b"x"), repeat=size):
            source = b"".join(pieces)
            actual = lexer_source_normalization(source)
            assert actual == literal_cpp_loop_reference(source)
            assert source.replace(b"\r", b"").replace(b"\n", b"") == (
                actual.replace(b"\r", b"").replace(b"\n", b"")
            )
            exhaustive_checks += 1
    return {
        "named_synthetic_checks_passed": len(fixtures),
        "prelexer_patch_guard_checks_passed": len(guards),
        "exhaustive_reference_and_other_byte_checks_passed": exhaustive_checks,
        "model_calls": 0,
        "files_written": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    result = self_test() if args.self_test else inspect(args.root)
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
