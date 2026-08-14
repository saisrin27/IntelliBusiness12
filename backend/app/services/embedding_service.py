import hashlib
import os
from typing import List


class EmbeddingService:
    """Simple deterministic embedding service for local development.

    The project specification allows a modular embedding provider and expects
    an API key check for external models. This implementation avoids hard-coded
    secrets and supports a future swap to Gemini/OpenAI without changing callers.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("AI_API_KEY")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_embedding(self, text: str, dimension: int = 8) -> List[float]:
        if not text:
            return [0.0 for _ in range(dimension)]

        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        values = []
        for idx in range(dimension):
            token = digest[(idx * 2):(idx * 2) + 2]
            numeric = int(token, 16) / 255.0
            values.append(round(float(numeric), 6))
        return values

    def generate_embeddings(self, chunks: List[str]) -> List[List[float]]:
        return [self.generate_embedding(chunk) for chunk in chunks]
