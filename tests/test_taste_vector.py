from src.task_b_recommendation import taste_vector
from src.task_b_recommendation.taste_vector import (
    build_and_store_user_taste_vector,
    build_user_taste_vector,
    parse_embedding,
    product_matches_category,
    store_user_taste_vector,
    weighted_average,
)


def test_weighted_average_uses_rating_weights() -> None:
    average = weighted_average([[1.0, 0.0], [0.0, 1.0]], [1.0, 2.0])

    assert average == [1 / 3, 2 / 3]


def test_parse_pgvector_string_embedding() -> None:
    assert parse_embedding("[0.1,0.2,0.3]") == [0.1, 0.2, 0.3]


class DummyTable:
    def __init__(self) -> None:
        self.payload = None
        self.on_conflict = None

    def upsert(self, payload, on_conflict=None):
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        return type("Response", (), {"data": []})()


class DummyClient:
    def __init__(self) -> None:
        self.table_obj = DummyTable()

    def table(self, _name):
        return self.table_obj


def test_store_user_taste_vector_records_source_review_count() -> None:
    client = DummyClient()

    store_user_taste_vector(
        "user-1",
        "All_Beauty",
        [0.1, 0.2],
        ["asin-1", "asin-2"],
        client=client,
    )

    assert client.table_obj.payload["source_review_count"] == 2
    assert client.table_obj.payload["source_parent_asins"] == ["asin-1", "asin-2"]


def test_product_matches_category_uses_category_then_fallbacks() -> None:
    assert product_matches_category({"category": "All_Beauty"}, "All Beauty") is True
    assert product_matches_category({"main_category": "Electronics"}, "Electronics") is True
    assert product_matches_category({"categories": ["Books", "Fiction"]}, "Books") is True
    assert product_matches_category({"category": "Books"}, "All_Beauty") is False


def test_build_user_taste_vector_filters_positive_reviews_by_category(monkeypatch) -> None:
    reviews = [
        {"parent_asin": "beauty-4", "rating": 4},
        {"parent_asin": "beauty-5", "rating": 5},
        {"parent_asin": "book-5", "rating": 5},
    ]
    metadata = {
        "beauty-4": {"parent_asin": "beauty-4", "category": "All_Beauty"},
        "beauty-5": {"parent_asin": "beauty-5", "category": "All_Beauty"},
        "book-5": {"parent_asin": "book-5", "category": "Books"},
    }
    embeddings = {
        "beauty-4": [1.0, 0.0],
        "beauty-5": [0.0, 1.0],
        "book-5": [10.0, 10.0],
    }

    monkeypatch.setattr(taste_vector, "fetch_liked_training_reviews", lambda user_id, client=None: reviews)
    monkeypatch.setattr(taste_vector, "fetch_product_metadata", lambda parent_asins, client=None: metadata)
    monkeypatch.setattr(
        taste_vector,
        "fetch_product_embeddings",
        lambda parent_asins, client=None: {asin: embeddings[asin] for asin in parent_asins},
    )

    beauty_vector, beauty_sources = build_user_taste_vector("user-1", "All_Beauty")
    book_vector, book_sources = build_user_taste_vector("user-1", "Books")

    assert beauty_sources == ["beauty-4", "beauty-5"]
    assert beauty_vector == [1 / 3, 2 / 3]
    assert book_sources == ["book-5"]
    assert book_vector == [10.0, 10.0]


def test_build_and_store_taste_vector_records_category_specific_source_count(monkeypatch) -> None:
    reviews = [
        {"parent_asin": "beauty-1", "rating": 5},
        {"parent_asin": "book-1", "rating": 5},
    ]
    metadata = {
        "beauty-1": {"parent_asin": "beauty-1", "category": "All_Beauty"},
        "book-1": {"parent_asin": "book-1", "category": "Books"},
    }
    embeddings = {"beauty-1": [1.0, 0.0], "book-1": [0.0, 1.0]}
    stored = []

    monkeypatch.setattr(taste_vector, "fetch_liked_training_reviews", lambda user_id, client=None: reviews)
    monkeypatch.setattr(taste_vector, "fetch_product_metadata", lambda parent_asins, client=None: metadata)
    monkeypatch.setattr(
        taste_vector,
        "fetch_product_embeddings",
        lambda parent_asins, client=None: {asin: embeddings[asin] for asin in parent_asins},
    )
    monkeypatch.setattr(taste_vector, "store_user_taste_vector", lambda *args, **kwargs: stored.append(args))

    build_and_store_user_taste_vector("user-1", "All_Beauty")

    assert stored[0][3] == ["beauty-1"]
    assert len(stored[0][3]) == 1
