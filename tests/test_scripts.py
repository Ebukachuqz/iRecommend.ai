from scripts.create_holdout_split import build_holdout_updates
from scripts import regenerate_personas


def test_holdout_split_does_not_require_review_category() -> None:
    updates = build_holdout_updates(
        [
            {"review_id": "old", "user_id": "u1", "rating": 5, "timestamp": "2024-01-01T00:00:00Z"},
            {"review_id": "mid", "user_id": "u1", "rating": 4, "timestamp": "2024-02-01T00:00:00Z"},
            {"review_id": "new", "user_id": "u1", "rating": 3, "timestamp": "2024-03-01T00:00:00Z"},
        ]
    )

    by_id = {update["review_id"]: update for update in updates}
    assert by_id["new"]["task_split"] == "task_a_holdout"
    assert by_id["mid"]["task_split"] == "task_b_holdout"
    assert by_id["old"]["task_split"] == "persona_train"


class QueryRecorder:
    def __init__(self) -> None:
        self.filters = []
        self.execute_count = 0

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def range(self, _start, _end):
        return self

    def execute(self):
        self.execute_count += 1
        data = [{"user_id": "u1"}] if self.execute_count == 1 else []
        return type("Response", (), {"data": data})()


class ClientRecorder:
    def __init__(self) -> None:
        self.query = QueryRecorder()

    def table(self, _name):
        return self.query


def test_regenerate_user_lookup_does_not_filter_by_category(monkeypatch) -> None:
    client = ClientRecorder()
    monkeypatch.setattr(regenerate_personas, "get_supabase_client", lambda: client)

    assert regenerate_personas.fetch_user_ids() == ["u1"]
    assert not any(column == "category" for column, _value in client.query.filters)
    assert not any(column == "used_for_persona" for column, _value in client.query.filters)
