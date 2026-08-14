from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from jbspan.adapters.base import TargetModel


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CacheEntry:
    key: str
    request_sha256: str
    model_name: str
    seed: int
    response: str


@dataclass
class ResponseCache:
    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def make_key(
        self,
        *,
        model_name: str,
        model_fingerprint: Mapping[str, Any],
        prompt: str,
        seed: int,
    ) -> tuple[str, str]:
        request_payload = {
            "model_name": model_name,
            "model_fingerprint": dict(model_fingerprint),
            "prompt": prompt,
            "seed": seed,
        }
        request_sha256 = canonical_sha256(request_payload)
        return request_sha256, request_sha256

    def get(self, key: str, *, expected_request_sha256: str) -> str | None:
        path = self._entry_path(key)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("request_sha256") != expected_request_sha256:
            raise RuntimeError("response-cache key collision or corrupted entry")
        response = payload.get("response")
        if not isinstance(response, str):
            raise RuntimeError("response-cache entry has invalid response")
        return response

    def put(self, entry: CacheEntry) -> None:
        path = self._entry_path(entry.key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "key": entry.key,
            "request_sha256": entry.request_sha256,
            "model_name": entry.model_name,
            "seed": entry.seed,
            "response": entry.response,
        }
        temporary = path.with_suffix(f".tmp-{os.getpid()}")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    def _entry_path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"


@dataclass
class CachedTargetModel:
    target: TargetModel
    cache: ResponseCache
    fingerprint: Mapping[str, Any]
    cache_hits: int = field(default=0, init=False)
    cache_misses: int = field(default=0, init=False)

    @property
    def name(self) -> str:
        return self.target.name

    def generate(self, prompt: str, *, seed: int) -> str:
        key, request_sha256 = self.cache.make_key(
            model_name=self.target.name,
            model_fingerprint=self.fingerprint,
            prompt=prompt,
            seed=seed,
        )
        cached = self.cache.get(key, expected_request_sha256=request_sha256)
        if cached is not None:
            self.cache_hits += 1
            return cached

        response = self.target.generate(prompt, seed=seed)
        self.cache.put(
            CacheEntry(
                key=key,
                request_sha256=request_sha256,
                model_name=self.target.name,
                seed=seed,
                response=response,
            )
        )
        self.cache_misses += 1
        return response
