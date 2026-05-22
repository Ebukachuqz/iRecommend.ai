from src.personas.generator import PersonaGenerator


class QueryRecorder:
    def __init__(self) -> None:
        self.filters = []
        self.payload = None
        self.on_conflict = None

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def upsert(self, payload, on_conflict=None):
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        return type("Response", (), {"data": []})()


class ClientRecorder:
    def __init__(self) -> None:
        self.queries = {}

    def table(self, name):
        query = QueryRecorder()
        self.queries[name] = query
        return query


def test_fetch_user_reviews_does_not_filter_by_category() -> None:
    client = ClientRecorder()
    generator = PersonaGenerator(client=client)

    generator.fetch_user_reviews("user-1")

    filters = client.queries["amazon_reviews"].filters
    assert ("user_id", "user-1") in filters
    assert ("task_split", "persona_train") in filters
    assert ("used_for_persona", True) in filters
    assert not any(column == "category" for column, _value in filters)


def test_store_persona_payload_includes_review_stats() -> None:
    client = ClientRecorder()
    generator = PersonaGenerator(client=client)
    stats = {
        "review_count": 8,
        "average_rating": 4.25,
        "source_review_ids": ["r1", "r2"],
    }

    generator.store_persona("user-1", "All_Beauty", {"writing_style": {}}, stats)

    query = client.queries["user_personas"]
    assert query.on_conflict == "user_id,category"
    assert query.payload["review_count"] == 8
    assert query.payload["average_rating"] == 4.25
    assert query.payload["source_review_ids"] == ["r1", "r2"]
