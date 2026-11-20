"""Abstract provider interfaces isolating future AI/ML integrations from core inventory domains."""

from typing import Protocol


class AIProviderPort(Protocol):
    """Port implemented by future AI providers (e.g., forecasting, anomaly detection, NLQ)."""

    @property
    def provider_name(self) -> str:
        """Return the configured provider identifier."""
        ...

    def is_available(self) -> bool:
        """Return True when the AI provider is enabled and ready."""
        ...

