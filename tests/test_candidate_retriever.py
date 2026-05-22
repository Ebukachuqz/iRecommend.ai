from src.task_b_recommendation.candidate_retriever import fetch_quality_fallback_products


class QueryRecorder:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def range(self, _start, _end):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        return type("Response", (), {"data": self.rows})()


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
