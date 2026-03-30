from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ResponsesClientConfig:
    model: str = "gpt-5.4"
    temperature: float = 0.0


class ResponsesFallbackClient:
    def __init__(self, config: ResponsesClientConfig | None = None) -> None:
        self.config = config or ResponsesClientConfig()

    def available(self) -> bool:
        return False

    def call(self, *_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("LLM fallback is disabled in the default pipeline")
