from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}: found {count} for {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    step3 = Path("src/jbspan/gate1/step3.py")
    replace_once(
        step3,
        '    if float(generation.get("temperature", -1.0)) <= 0.0:\n',
        '    if _number(generation.get("temperature"), "generation.temperature") <= 0.0:\n',
    )
    replace_once(
        step3,
        '    harmful = float(consensus.get("harmful_strongreject_min", -1.0))\n',
        '    harmful = _number(\n'
        '        consensus.get("harmful_strongreject_min"),\n'
        '        "consensus.harmful_strongreject_min",\n'
        '    )\n',
    )
    replace_once(
        step3,
        '    safe = float(consensus.get("safe_strongreject_max", -1.0))\n',
        '    safe = _number(\n'
        '        consensus.get("safe_strongreject_max"),\n'
        '        "consensus.safe_strongreject_max",\n'
        '    )\n',
    )
    replace_once(
        step3,
        '    return matches[0] == "yes"\n',
        '    return str(matches[0]) == "yes"\n',
    )
    replace_once(
        step3,
        '    harmful_min = float(config["harmful_strongreject_min"])\n',
        '    harmful_min = _number(\n'
        '        config.get("harmful_strongreject_min"),\n'
        '        "consensus.harmful_strongreject_min",\n'
        '    )\n',
    )
    replace_once(
        step3,
        '    safe_max = float(config["safe_strongreject_max"])\n',
        '    safe_max = _number(\n'
        '        config.get("safe_strongreject_max"),\n'
        '        "consensus.safe_strongreject_max",\n'
        '    )\n',
    )
    integer_marker = (
        'def _integer(value: object, where: str) -> int:\n'
        '    if not isinstance(value, int) or isinstance(value, bool):\n'
        '        raise ContractValidationError(f"{where} must be an integer")\n'
        '    return value\n'
    )
    number_helper = (
        'def _number(value: object, where: str) -> float:\n'
        '    if isinstance(value, bool) or not isinstance(value, (int, float)):\n'
        '        raise ContractValidationError(f"{where} must be a number")\n'
        '    return float(value)\n\n\n'
    )
    replace_once(step3, integer_marker, number_helper + integer_marker)

    hf = Path("src/jbspan/adapters/hf.py")
    hf.write_text(
        '''from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HuggingFaceCausalLMAdapter:
    """Optional local adapter loaded only when the `hf` extra is installed.

    Model revision, tokenizer revision, generation parameters, dtype, and device
    mapping must be frozen in experiment manifests before paper-scale runs.
    """

    model_id: str
    revision: str | None = None
    tokenizer_revision: str | None = None
    max_new_tokens: int = 256
    temperature: float = 0.0
    device_map: str = "auto"
    name: str = field(init=False)
    _model: Any = field(init=False, repr=False)
    _tokenizer: Any = field(init=False, repr=False)
    _torch: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            self._torch = importlib.import_module("torch")
            transformers: Any = importlib.import_module("transformers")
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("install jbspan with the 'hf' extra") from exc

        tokenizer_loader: Any = transformers.AutoTokenizer.from_pretrained
        model_loader: Any = transformers.AutoModelForCausalLM.from_pretrained
        self.name = self.model_id
        self._tokenizer = tokenizer_loader(
            self.model_id,
            revision=self.tokenizer_revision or self.revision,
        )
        self._model = model_loader(
            self.model_id,
            revision=self.revision,
            device_map=self.device_map,
            torch_dtype=self._torch.bfloat16,
        )
        self._model.eval()

    def generate(self, prompt: str, *, seed: int) -> str:  # pragma: no cover - GPU path
        self._torch.manual_seed(seed)
        messages = [{"role": "user", "content": prompt}]
        rendered = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        batch = self._tokenizer(rendered, return_tensors="pt").to(self._model.device)
        do_sample = self.temperature > 0.0
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": self.max_new_tokens,
            "do_sample": do_sample,
        }
        if do_sample:
            generation_kwargs["temperature"] = self.temperature
        with self._torch.inference_mode():
            output = self._model.generate(**batch, **generation_kwargs)
        generated = output[0, batch["input_ids"].shape[1] :]
        return str(self._tokenizer.decode(generated, skip_special_tokens=True))
''',
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
