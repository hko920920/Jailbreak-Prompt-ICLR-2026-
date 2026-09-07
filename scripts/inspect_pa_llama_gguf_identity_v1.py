"""Read-only, bounded metadata and runtime identity inspection for PA admission.

No model loading, inference, remote access, artifact writes, or raw template output.
GGUF v2/v3 little-endian metadata are read only up to their final key/value pair;
tensor descriptors/data are not parsed. Full-file hashing is a separate byte scan.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
import zipfile
from pathlib import Path
from typing import BinaryIO

MODEL = (
    "artifacts/p2_runtime_qualification_v1/models/meta-llama-3.1-8b-instruct-q4-k-m/"
    "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
)
MODEL_SHA256 = "7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c"
ARCHIVE = "artifacts/p2_runtime_qualification_v1/downloads/llama-b10441-bin-win-vulkan-x64.zip"
ARCHIVE_SHA256 = "7fdbac5860ad1c64bf1e5703e4491612562e953a709a9f190affd6141147c6aa"
RUNTIME = "artifacts/p2_runtime_qualification_v1/runtime/llama-b10441-vulkan"
TYPE_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
MAX_METADATA_BYTES = 256 * 1024 * 1024
MAX_STRING_BYTES = 8 * 1024 * 1024
MAX_ARRAY_COUNT = 2_000_000


class MetadataReader:
    def __init__(self, stream: BinaryIO, file_size: int):
        self.stream = stream
        self.limit = min(file_size, MAX_METADATA_BYTES)

    def read(self, size: int) -> bytes:
        if size < 0 or self.stream.tell() + size > self.limit:
            raise ValueError("metadata extent exceeds bounded prefix or file size")
        value = self.stream.read(size)
        if len(value) != size:
            raise ValueError("truncated metadata")
        return value

    def skip(self, size: int) -> None:
        if size < 0 or self.stream.tell() + size > self.limit:
            raise ValueError("metadata skip exceeds bounded prefix or file size")
        self.stream.seek(size, io.SEEK_CUR)

    def u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.read(8))[0]

    def string(self, keep: bool = False) -> bytes | None:
        size = self.u64()
        if size > MAX_STRING_BYTES:
            raise ValueError("metadata string exceeds bound")
        if keep:
            return self.read(size)
        self.skip(size)
        return None

    def skip_value(self, value_type: int) -> None:
        if value_type in TYPE_SIZES:
            self.skip(TYPE_SIZES[value_type])
        elif value_type == 8:
            self.string()
        elif value_type == 9:
            element_type = self.u32()
            count = self.u64()
            if count > MAX_ARRAY_COUNT:
                raise ValueError("metadata array exceeds bound")
            if element_type in TYPE_SIZES:
                self.skip(TYPE_SIZES[element_type] * count)
            elif element_type == 8:
                for _ in range(count):
                    self.string()
            else:
                raise ValueError("unsupported or nested array element type")
        else:
            raise ValueError("unknown metadata type")


def inspect_metadata(stream: BinaryIO, file_size: int) -> dict:
    reader = MetadataReader(stream, file_size)
    if reader.read(4) != b"GGUF":
        raise ValueError("not a little-endian GGUF")
    version = reader.u32()
    if version not in (2, 3):
        raise ValueError("only GGUF v2/v3 are supported")
    tensor_count, metadata_count = reader.u64(), reader.u64()
    if tensor_count > 1_000_000 or metadata_count > 10_000:
        raise ValueError("GGUF entry counts exceed bounds")
    keys: list[str] = []
    template: bytes | None = None
    for _ in range(metadata_count):
        key_bytes = reader.string(keep=True)
        assert key_bytes is not None
        key = key_bytes.decode("utf-8", errors="strict")
        if key in keys:
            raise ValueError("duplicate metadata key")
        keys.append(key)
        value_type = reader.u32()
        if key == "tokenizer.chat_template":
            if value_type != 8:
                raise ValueError("native chat template is not a string")
            template = reader.string(keep=True)
            assert template is not None
            if (
                not template
                or template.decode("utf-8", errors="strict").encode("utf-8") != template
            ):
                raise ValueError("native chat template is empty or not losslessly UTF-8")
        else:
            reader.skip_value(value_type)
    if template is None:
        raise ValueError("native chat template missing")
    return {
        "gguf_version": version,
        "tensor_count": tensor_count,
        "metadata_count": metadata_count,
        "metadata_keys": keys,
        "metadata_end_offset": stream.tell(),
        "native_chat_template_type": "GGUF_TYPE_STRING",
        "native_chat_template_utf8_bytes": len(template),
        "native_chat_template_sha256": hashlib.sha256(template).hexdigest(),
        "native_chat_template_decode": "UTF-8 strict; no normalization or newline conversion",
        "tensor_descriptors_or_data_parsed": False,
    }


def digest_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(4 * 1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def descriptor(path: Path, root: Path) -> dict:
    actual = path.resolve(strict=True)
    actual.relative_to(root)
    with actual.open("rb") as stream:
        sha256 = digest_stream(stream)
    return {
        "path": actual.relative_to(root).as_posix(),
        "size_bytes": actual.stat().st_size,
        "sha256": sha256,
    }


def inspect(root: Path) -> dict:
    root = root.resolve(strict=True)
    model_path = (root / MODEL).resolve(strict=True)
    model_path.relative_to(root)
    with model_path.open("rb") as stream:
        metadata = inspect_metadata(stream, model_path.stat().st_size)
    model = descriptor(model_path, root)
    archive_path = (root / ARCHIVE).resolve(strict=True)
    archive = descriptor(archive_path, root)
    if model["sha256"] != MODEL_SHA256 or archive["sha256"] != ARCHIVE_SHA256:
        raise ValueError("model or runtime archive does not match pre-existing authority hash")
    runtime_path = (root / RUNTIME).resolve(strict=True)
    runtime_path.relative_to(root)
    paths = sorted(runtime_path.glob("*.dll")) + [runtime_path / "llama-server.exe"]
    if len(paths) < 2:
        raise ValueError("runtime inventory unexpectedly empty")
    runtime_files = []
    with zipfile.ZipFile(archive_path, "r") as archive_zip:
        entries = archive_zip.infolist()
        for path in paths:
            entry = descriptor(path, root)
            matches = [
                item
                for item in entries
                if not item.is_dir() and Path(item.filename).name == path.name
            ]
            if len(matches) != 1:
                raise ValueError("runtime archive filename absent or ambiguous")
            zip_entry = matches[0]
            if zip_entry.file_size != entry["size_bytes"]:
                raise ValueError("runtime byte count differs from pinned archive")
            with archive_zip.open(zip_entry, "r") as stream:
                zip_sha256 = digest_stream(stream)
            if zip_sha256 != entry["sha256"]:
                raise ValueError("runtime bytes differ from pinned archive")
            entry["archive_entry"] = zip_entry.filename
            entry["archive_sha256_match"] = True
            runtime_files.append(entry)
    return {
        "schema_version": "jbspan-pa-llama-static-identity-v1",
        "model": model,
        "gguf_metadata": metadata,
        "runtime_archive": archive,
        "runtime_files": runtime_files,
        "all_runtime_files_match_pinned_archive": True,
        "inference_calls": 0,
        "server_launches": 0,
        "files_written": 0,
    }


def self_test() -> dict:
    def string(value: bytes) -> bytes:
        return struct.pack("<Q", len(value)) + value

    def fixture(value_type: int = 8, template: bytes = b"native\r\n{{ messages }}") -> bytes:
        return (
            b"GGUF"
            + struct.pack("<IQQ", 3, 2, 2)
            + string(b"tokenizer.tokens")
            + struct.pack("<IIQ", 9, 8, 2)
            + string(b"x")
            + string(b"y")
            + string(b"tokenizer.chat_template")
            + struct.pack("<I", value_type)
            + string(template)
        )

    source = fixture()
    result = inspect_metadata(io.BytesIO(source), len(source))
    assert (
        result["native_chat_template_sha256"]
        == hashlib.sha256(b"native\r\n{{ messages }}").hexdigest()
    )
    assert result["metadata_end_offset"] == len(source)
    malformed = [
        source[:-1],
        fixture(4),
        fixture(template=b""),
        fixture(template=b"\xff"),
        b"NOPE" + source[4:],
    ]
    malformed.append(
        b"GGUF" + struct.pack("<IQQ", 3, 0, 1) + struct.pack("<Q", MAX_STRING_BYTES + 1)
    )
    for bad in malformed:
        try:
            inspect_metadata(io.BytesIO(bad), len(bad))
        except (ValueError, UnicodeError):
            continue
        raise AssertionError("malformed GGUF accepted")
    return {"synthetic_checks_passed": 1 + len(malformed), "files_written": 0, "model_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            self_test() if args.self_test else inspect(args.root), indent=2, ensure_ascii=True
        )
    )


if __name__ == "__main__":
    main()
