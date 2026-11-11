import re

import numpy as np

from backend.chatbot.guards import periods
from backend.core.config import settings
from backend.knowledge.loader import FAQ

_model = None


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def embed(texts) -> np.ndarray:
    """Unit-length sentence embeddings (cosine similarity == dot product)."""
    global _model
    texts = list(texts)
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(settings.embedding_model, cache_dir=str(settings.model_cache_dir))
    vectors = np.array(list(_model.embed(texts)), dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


class SemanticIndex:
    def __init__(self, faqs: list[FAQ], example_questions: list[str]):
        self.faqs = faqs
        self.matrix = embed(f.question for f in faqs)
        self.periods = [periods(f.question) for f in faqs]
        self.examples = embed(example_questions)
        self.example_questions = example_questions

    def scores(self, query: str):
        vector = embed([query])[0]
        return self.matrix @ vector, vector

    def example_scores(self, vector: np.ndarray) -> np.ndarray:
        return self.examples @ vector
