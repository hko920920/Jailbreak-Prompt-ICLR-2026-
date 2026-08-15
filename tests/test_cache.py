from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from jbspan.cache import CachedTargetModel, ResponseCache


@dataclass
class CountingModel:
    name: str = "counting-model"
    calls: int = field(default=0, init=False)

    def generate(self, prompt: str, *, seed: int) -> str:
        del prompt
        self.calls += 1
        return f"response:{seed}"


def test_cache_avoids_duplicate_generation_and_hides_request(tmp_path: Path) -> None:
    underlying = CountingModel()
    cached = CachedTargetModel(
        target=underlying,
        cache=ResponseCache(tmp_path / "cache"),
        fingerprint={"revision": "abc", "temperature": 0.0},
    )
    secret = "sensitive-prompt-text"
    assert cached.generate(secret, seed=7) == "response:7"
    assert cached.generate(secret, seed=7) == "response:7"
    assert underlying.calls == 1
    assert cached.cache_hits == 1
    assert cached.cache_misses == 1
    cache_text = "".join(path.read_text() for path in (tmp_path / "cache").rglob("*.json"))
    assert secret not in cache_text


def test_fingerprint_changes_cache_key(tmp_path: Path) -> None:
    underlying = CountingModel()
    cache = ResponseCache(tmp_path / "cache")
    first = CachedTargetModel(underlying, cache, {"revision": "a"})
    second = CachedTargetModel(underlying, cache, {"revision": "b"})
    first.generate("prompt", seed=0)
    second.generate("prompt", seed=0)
    assert underlying.calls == 2
