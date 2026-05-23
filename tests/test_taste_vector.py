from src.task_b_recommendation.taste_vector import parse_embedding, store_user_taste_vector, weighted_average


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
