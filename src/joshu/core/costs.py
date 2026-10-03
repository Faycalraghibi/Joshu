"""
Cost of model requests.

Providers that report cost (OpenRouter returns it in the usage of every
response) are taken at their word. For others, `model_pricing` in config.yaml
gives prices in USD per million tokens:

    model_pricing:
      gpt-4.1-mini: {input: 0.40, output: 1.60}

A request whose cost can't be determined makes the total unknown rather than
silently counting it as free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CostTracker:
    """Running cost of a conversation."""

    total_usd: float = 0.0
    unknown_requests: int = 0

    @property
    def known(self) -> bool:
        return self.unknown_requests == 0

    def add(self, cost: Optional[float]) -> None:
        if cost is None:
            self.unknown_requests += 1
        else:
            self.total_usd += cost

    def merge(self, other: "CostTracker") -> None:
        self.total_usd += other.total_usd
        self.unknown_requests += other.unknown_requests

    def as_dict(self) -> Dict[str, Any]:
        return {"total_usd": self.total_usd, "unknown_requests": self.unknown_requests}

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "CostTracker":
        data = data or {}
        return cls(
            total_usd=float(data.get("total_usd", 0.0) or 0.0),
            unknown_requests=int(data.get("unknown_requests", 0) or 0),
        )


def request_cost(
    usage: Dict[str, Any], model: str, pricing: Optional[Dict[str, Any]] = None
) -> Optional[float]:
    """
    Cost in USD of one request, or None when it can't be determined.

    Args:
        usage: Usage from the response; a provider-reported `cost` wins
        model: Model id, looked up in `pricing`
        pricing: model id -> {"input": usd_per_million, "output": usd_per_million}
    """
    if usage.get("cost") is not None:
        return float(usage["cost"])

    price = (pricing or {}).get(model)
    if not isinstance(price, dict):
        return None
    try:
        input_price = float(price.get("input", 0))
        output_price = float(price.get("output", 0))
    except (TypeError, ValueError):
        return None
    return (
        usage.get("prompt_tokens", 0) * input_price
        + usage.get("completion_tokens", 0) * output_price
    ) / 1_000_000


def format_cost(tracker: CostTracker) -> str:
    """'$0.0123', or 'cost unknown' (with a known lower bound if any)."""
    if tracker.known:
        return f"${tracker.total_usd:.4f}"
    if tracker.total_usd:
        return f"at least ${tracker.total_usd:.4f} (some prices unknown)"
    return "cost unknown"
