from src.task_b_recommendation.candidate_retriever import (
    fetch_quality_fallback_products,
    retrieve_candidates,
    retrieve_candidates_with_sources,
)
from src.task_b_recommendation.schema import RecommendationIntent


class QueryRecorder:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.in_values = None
        self.in_column = None
        self.order_calls = 0
        self.gte_filters = []
        self.lte_filters = []
        self.ilike_filter = None
        self.limit_count = None

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def in_(self, column, values):
        self.in_column = column
        self.in_values = set(values)
        return self

    def gte(self, column, value):
        self.gte_filters.append((column, value))
        return self

    def lte(self, column, value):
        self.lte_filters.append((column, value))
        return self

    def ilike(self, column, pattern):
        self.ilike_filter = (column, pattern.replace("%", "").lower())
        return self

    def range(self, _start, _end):
        return self

    def order(self, *_args, **_kwargs):
        self.order_calls += 1
        return self

    def limit(self, _limit):
        self.limit_count = _limit
        return self

    def execute(self):
        rows = self.rows
        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]
        if self.in_values is not None:
            rows = [row for row in rows if row.get(self.in_column) in self.in_values]
            self.in_values = None
            self.in_column = None
        for column, value in self.gte_filters:
            rows = [row for row in rows if row.get(column) is not None and row.get(column) >= value]
        for column, value in self.lte_filters:
            rows = [row for row in rows if row.get(column) is not None and row.get(column) <= value]
        if self.ilike_filter is not None:
            column, term = self.ilike_filter
            rows = [row for row in rows if term in str(row.get(column) or "").lower()]
            self.ilike_filter = None
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        self.filters = []
        self.in_values = None
        self.in_column = None
        self.gte_filters = []
        self.lte_filters = []
        self.ilike_filter = None
        self.limit_count = None
        return type("Response", (), {"data": rows})()


class ClientRecorder:
    def __init__(self):
        self.review_query = QueryRecorder([{"user_id": "user-1", "parent_asin": "seen-1"}])
        self.product_query = QueryRecorder(
            [
                {"parent_asin": "seen-1", "title": "Already reviewed", "average_rating": 5},
                {"parent_asin": "new-1", "title": "New product", "average_rating": 4.8},
            ]
        )

    def table(self, name):
        if name == "amazon_reviews":
            return self.review_query
        return self.product_query


def test_reviewed_products_are_excluded_from_fallback_candidates() -> None:
    candidates = fetch_quality_fallback_products("user-1", limit=5, client=ClientRecorder())

    assert [candidate.parent_asin for candidate in candidates] == ["new-1"]


class VectorStoreRecorder:
    def __init__(self, matches):
        self.matches = matches
        self.similar_users = []
        self.calls = []
        self.similar_user_calls = []

    def upsert_product_embedding(self, parent_asin, embedding, embedding_model, product_text):
        raise NotImplementedError

    def search_products(self, query_embedding, limit, exclude_parent_asins=None):
        self.calls.append(
            {
                "query_embedding": query_embedding,
                "limit": limit,
                "exclude_parent_asins": exclude_parent_asins,
            }
        )
        return self.matches

    def get_product_embedding(self, parent_asin):
        raise NotImplementedError

    def search_similar_users(self, query_embedding, category, limit, exclude_user_id=None):
        self.similar_user_calls.append(
            {
                "query_embedding": query_embedding,
                "category": category,
                "limit": limit,
                "exclude_user_id": exclude_user_id,
            }
        )
        return self.similar_users


class ProductClientRecorder:
    def __init__(self):
        self.product_query = QueryRecorder(
            [
                {"parent_asin": "skin-1", "title": "Affordable oily skin cleanser", "average_rating": 4.6},
                {"parent_asin": "skin-2", "title": "Gentle oil control moisturizer", "average_rating": 4.5},
                {"parent_asin": "fallback-1", "title": "Popular fallback product", "average_rating": 4.9},
            ]
        )

    def table(self, name):
        assert name == "amazon_product_metadata"
        return self.product_query


def test_cold_start_request_query_searches_vector_store(monkeypatch) -> None:
    client = ProductClientRecorder()
    vector_store = VectorStoreRecorder([{"parent_asin": "skin-1", "similarity": 0.82}])
    monkeypatch.setattr("src.task_b_recommendation.candidate_retriever.embed_text", lambda text: [0.1, 0.2])

    candidates = retrieve_candidates(
        user_id=None,
        category="All_Beauty",
        intent=RecommendationIntent(retrieval_query="affordable skincare for oily skin"),
        limit=1,
        client=client,
        vector_store=vector_store,
    )

    assert len(vector_store.calls) == 1
    assert candidates[0].retrieval_source == "request_query"
    assert candidates[0].semantic_similarity == 0.82


def test_request_query_candidates_keep_semantic_similarity(monkeypatch) -> None:
    client = ProductClientRecorder()
    vector_store = VectorStoreRecorder([{"parent_asin": "skin-2", "similarity": 0.67}])
    monkeypatch.setattr("src.task_b_recommendation.candidate_retriever.embed_text", lambda text: [0.3, 0.4])

    candidates = retrieve_candidates(
        user_id=None,
        category="All_Beauty",
        intent=RecommendationIntent(retrieval_query="gentle moisturizer"),
        limit=1,
        client=client,
        vector_store=vector_store,
    )

    assert candidates[0].retrieval_source == "request_query"
    assert candidates[0].semantic_similarity > 0


def test_quality_fallback_only_fills_when_vector_results_are_too_few(monkeypatch) -> None:
    client = ProductClientRecorder()
    vector_store = VectorStoreRecorder(
        [
            {"parent_asin": "skin-1", "similarity": 0.8},
            {"parent_asin": "skin-2", "similarity": 0.7},
        ]
    )
    monkeypatch.setattr("src.task_b_recommendation.candidate_retriever.embed_text", lambda text: [0.5, 0.6])

    candidates = retrieve_candidates(
        user_id=None,
        category="All_Beauty",
        intent=RecommendationIntent(retrieval_query="skincare"),
        limit=2,
        client=client,
        vector_store=vector_store,
    )

    assert [candidate.retrieval_source for candidate in candidates] == ["request_query", "request_query"]
    assert client.product_query.order_calls == 0

    short_vector_store = VectorStoreRecorder([{"parent_asin": "skin-1", "similarity": 0.8}])
    filled_client = ProductClientRecorder()
    candidates = retrieve_candidates(
        user_id=None,
        category="All_Beauty",
        intent=RecommendationIntent(retrieval_query="skincare"),
        limit=2,
        client=filled_client,
        vector_store=short_vector_store,
    )

    assert [candidate.retrieval_source for candidate in candidates] == ["request_query", "quality_fallback"]
    assert filled_client.product_query.order_calls > 0


class MultiSourceClient:
    def __init__(self):
        self.review_query = QueryRecorder(
            [
                {"user_id": "user-1", "parent_asin": "seen-1", "task_split": "persona_train", "rating": 5},
                {"user_id": "similar-1", "parent_asin": "collab-1", "task_split": "persona_train", "rating": 5},
            ]
        )
        self.product_query = QueryRecorder(
            [
                {
                    "parent_asin": "taste-1",
                    "title": "Taste vector cleanser",
                    "category": "All_Beauty",
                    "average_rating": 4.5,
                    "rating_number": 100,
                },
                {
                    "parent_asin": "query-1",
                    "title": "Request query moisturizer",
                    "category": "All_Beauty",
                    "average_rating": 4.6,
                    "rating_number": 90,
                },
                {
                    "parent_asin": "collab-1",
                    "title": "Similar user toner",
                    "category": "All_Beauty",
                    "average_rating": 4.7,
                    "rating_number": 80,
                },
                {
                    "parent_asin": "attr-1",
                    "title": "Fragrance free cream",
                    "category": "All_Beauty",
                    "average_rating": 4.8,
                    "rating_number": 70,
                },
                {
                    "parent_asin": "fallback-1",
                    "title": "Popular quality fallback",
                    "category": "All_Beauty",
                    "average_rating": 4.9,
                    "rating_number": 500,
                },
            ]
        )
        self.embedding_query = QueryRecorder(
            [
                {"parent_asin": "attr-1", "product_text": "Title: Fragrance free cream\nFeatures: gentle hydrating"},
            ]
        )

    def table(self, name):
        if name == "amazon_reviews":
            return self.review_query
        if name == "product_embeddings":
            return self.embedding_query
        assert name == "amazon_product_metadata"
        return self.product_query


def test_taste_vector_retrieval_runs_when_taste_vector_exists(monkeypatch) -> None:
    client = MultiSourceClient()
    vector_store = VectorStoreRecorder([{"parent_asin": "taste-1", "similarity": 0.9}])
    monkeypatch.setattr("src.task_b_recommendation.candidate_retriever.embed_text", lambda text: [0.3, 0.4])

    result = retrieve_candidates_with_sources(
        user_id="user-1",
        category="All_Beauty",
        intent=RecommendationIntent(),
        limit=1,
        client=client,
        vector_store=vector_store,
        taste_vector_row={"embedding": [0.1, 0.2]},
    )

    assert result.candidates[0].retrieval_source == "taste_vector"
    assert result.candidates[0].semantic_similarity == 0.9
    assert result.source_counts["taste_vector"] == 1


def test_collaborative_retrieval_collects_similar_users_liked_products(monkeypatch) -> None:
    client = MultiSourceClient()
    vector_store = VectorStoreRecorder([])
    vector_store.similar_users = [{"user_id": "similar-1", "similarity": 0.88}]
    monkeypatch.setattr("src.task_b_recommendation.candidate_retriever.embed_text", lambda text: [0.3, 0.4])

    result = retrieve_candidates_with_sources(
        user_id="user-1",
        category="All_Beauty",
        intent=RecommendationIntent(),
        limit=1,
        client=client,
        vector_store=vector_store,
        taste_vector_row={"embedding": [0.1, 0.2]},
    )

    assert result.candidates[0].parent_asin == "collab-1"
    assert result.candidates[0].retrieval_source == "collaborative"
    assert result.candidates[0].collaborative_similarity == 0.88
    assert result.source_counts["collaborative"] == 1


def test_attribute_match_retrieval_uses_persona_and_intent_signals(monkeypatch) -> None:
    client = MultiSourceClient()
    vector_store = VectorStoreRecorder([])
    monkeypatch.setattr("src.task_b_recommendation.candidate_retriever.embed_text", lambda text: [0.3, 0.4])

    result = retrieve_candidates_with_sources(
        user_id=None,
        category="All_Beauty",
        intent=RecommendationIntent(required_attributes=["hydrating"]),
        limit=1,
        client=client,
        vector_store=vector_store,
        persona={"preferences": {"liked_attributes": ["fragrance free"]}},
    )

    assert result.candidates[0].parent_asin == "attr-1"
    assert result.candidates[0].retrieval_source == "attribute_match"
    assert "fragrance free" in result.candidates[0].source_evidence


def test_dedupe_preserves_multiple_retrieval_sources(monkeypatch) -> None:
    client = MultiSourceClient()
    vector_store = VectorStoreRecorder([{"parent_asin": "taste-1", "similarity": 0.75}])
    monkeypatch.setattr("src.task_b_recommendation.candidate_retriever.embed_text", lambda text: [0.3, 0.4])

    result = retrieve_candidates_with_sources(
        user_id="user-1",
        category="All_Beauty",
        intent=RecommendationIntent(retrieval_query="same product"),
        limit=1,
        client=client,
        vector_store=vector_store,
        taste_vector_row={"embedding": [0.1, 0.2]},
    )

    assert result.candidates[0].parent_asin == "taste-1"
    assert result.candidates[0].retrieval_sources == ["taste_vector", "request_query"]
    assert result.source_counts["taste_vector"] == 1
    assert result.source_counts.get("request_query", 0) == 0


def test_reviewed_products_are_excluded_from_vector_sources(monkeypatch) -> None:
    client = MultiSourceClient()
    vector_store = VectorStoreRecorder([{"parent_asin": "seen-1", "similarity": 0.95}])
    monkeypatch.setattr("src.task_b_recommendation.candidate_retriever.embed_text", lambda text: [0.3, 0.4])

    result = retrieve_candidates_with_sources(
        user_id="user-1",
        category="All_Beauty",
        intent=RecommendationIntent(retrieval_query="seen product"),
        limit=1,
        client=client,
        vector_store=vector_store,
        taste_vector_row={"embedding": [0.1, 0.2]},
    )

    assert all(candidate.parent_asin != "seen-1" for candidate in result.candidates)


def test_explicit_excluded_parent_asins_are_removed_from_all_retrieval_sources(monkeypatch) -> None:
    client = MultiSourceClient()
    vector_store = VectorStoreRecorder(
        [
            {"parent_asin": "taste-1", "similarity": 0.95},
            {"parent_asin": "query-1", "similarity": 0.9},
        ]
    )
    vector_store.similar_users = [{"user_id": "similar-1", "similarity": 0.88}]
    monkeypatch.setattr("src.task_b_recommendation.candidate_retriever.embed_text", lambda text: [0.3, 0.4])

    result = retrieve_candidates_with_sources(
        user_id="user-1",
        category="All_Beauty",
        intent=RecommendationIntent(retrieval_query="query", required_attributes=["hydrating"]),
        limit=3,
        client=client,
        vector_store=vector_store,
        persona={"preferences": {"liked_attributes": ["fragrance free"]}},
        taste_vector_row={"embedding": [0.1, 0.2]},
        exclude_parent_asins={"taste-1", "query-1", "collab-1", "attr-1"},
    )

    assert all(candidate.parent_asin not in {"taste-1", "query-1", "collab-1", "attr-1"} for candidate in result.candidates)
    assert vector_store.calls[0]["exclude_parent_asins"] == {"seen-1", "taste-1", "query-1", "collab-1", "attr-1"}
    assert [candidate.parent_asin for candidate in result.candidates] == ["fallback-1"]
