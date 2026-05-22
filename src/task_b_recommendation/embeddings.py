from __future__ import annotations

from functools import lru_cache


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


@lru_cache
def load_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_texts(texts: list[str], model_name: str = DEFAULT_EMBEDDING_MODEL) -> list[list[float]]:
    model = load_embedding_model(model_name)
    embeddings = model.encode(texts, normalize_embeddings=True)
    return [embedding.astype(float).tolist() for embedding in embeddings]


def embed_text(text: str, model_name: str = DEFAULT_EMBEDDING_MODEL) -> list[float]:
    return embed_texts([text], model_name=model_name)[0]
