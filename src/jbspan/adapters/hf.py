from __future__ import annotations

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

    def __post_init__(self) -> None:
        try:
            import torch  # type: ignore[import-not-found]
            from transformers import (  # type: ignore[import-not-found]
                AutoModelForCausalLM,
                AutoTokenizer,
            )
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("install jbspan with the 'hf' extra") from exc

        self.name = self.model_id
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            revision=self.tokenizer_revision or self.revision,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            revision=self.revision,
            device_map=self.device_map,
            torch_dtype=torch.bfloat16,
        )
        self._model.eval()

    def generate(self, prompt: str, *, seed: int) -> str:  # pragma: no cover - GPU path
        import torch  # type: ignore[import-not-found]

        torch.manual_seed(seed)
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
        with torch.inference_mode():
            output = self._model.generate(**batch, **generation_kwargs)
        generated = output[0, batch["input_ids"].shape[1] :]
        return str(self._tokenizer.decode(generated, skip_special_tokens=True))
