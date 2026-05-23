from src.task_b_recommendation.candidate_retriever import fetch_quality_fallback_products, retrieve_candidates
from src.task_b_recommendation.schema import RecommendationIntent


class QueryRecorder:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.in_values = None
        self.order_calls = 0

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def in_(self, _column, values):
        self.in_values = set(values)
        return self

    def range(self, _start, _end):
        return self

    def order(self, *_args, **_kwargs):
        self.order_calls += 1
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        rows = self.rows
        if self.in_values is not None:
            rows = [row for row in rows if row.get("parent_asin") in self.in_values]
            self.in_values = None
        return type("Response", (), {"data": rows})()


class ClientRecorder:
    def __init__(self):
        self.review_query = QueryRecorder([{"parent_asin": "seen-1"}])
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
        self.calls = []

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
