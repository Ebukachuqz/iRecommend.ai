from src.db import queries


class QueryRecorder:
    def __init__(self, data):
        self.data = data
        self.filters = []

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def range(self, _start, _end):
        return self

    def execute(self):
        return type("Response", (), {"data": self.data})()


class ClientRecorder:
    def __init__(self):
        self.review_query = QueryRecorder([{"parent_asin": "seen-1"}])
        self.product_query = QueryRecorder(
            [
                {"parent_asin": "seen-1", "title": "Seen"},
                {"parent_asin": "new-1", "title": "New"},
            ]
        )

    def table(self, name):
        if name == "amazon_reviews":
            return self.review_query
        return self.product_query


def test_fetch_unseen_products_does_not_require_review_category() -> None:
    client = ClientRecorder()

    unseen = queries.fetch_unseen_products("user-1", limit=1, client=client)

    assert unseen == [{"parent_asin": "new-1", "title": "New"}]
    assert ("user_id", "user-1") in client.review_query.filters
    assert not any(column == "category" for column, _value in client.review_query.filters)
