from src.task_b_recommendation.schema import RecommendationSessionState
from src.task_b_recommendation.session_state import apply_request_constraints, load_session, store_session


class DummyQuery:
    def __init__(self, rows=None) -> None:
        self.rows = rows or []
        self.payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def upsert(self, payload, on_conflict=None):
        self.payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        return type("Response", (), {"data": self.rows})()


class DummyClient:
    def __init__(self, rows=None) -> None:
        self.query = DummyQuery(rows)

    def table(self, _name):
        return self.query


def test_store_session_writes_state_blob_and_inspectable_columns() -> None:
    client = DummyClient()
    state = RecommendationSessionState(
        session_id="session-1",
        user_id="user-1",
        category="All_Beauty",
        persona={"preferences": {"liked_attributes": ["gentle"]}},
        conversation_history=[{"role": "user", "content": "something gentle"}],
        shown_products=["asin-1"],
    )

    store_session(state, client=client)

    payload = client.query.payload
    assert payload["state"]["session_id"] == "session-1"
    assert payload["persona"] == state.persona
    assert payload["conversation_history"] == state.conversation_history
    assert payload["active_constraints"] == state.active_constraints
    assert payload["shown_products"] == ["asin-1"]


def test_load_session_supports_top_level_columns_when_state_blob_missing() -> None:
    client = DummyClient(
        [
            {
                "session_id": "session-1",
                "user_id": "user-1",
                "category": "All_Beauty",
                "state": None,
                "persona": {"preferences": {"liked_attributes": ["gentle"]}},
                "conversation_history": [{"role": "user", "content": "gentle"}],
                "active_constraints": {"price_max": 25},
                "shown_products": ["asin-1"],
            }
        ]
    )

    state = load_session("session-1", client=client)

    assert state is not None
    assert state.session_id == "session-1"
    assert state.persona["preferences"]["liked_attributes"] == ["gentle"]
    assert state.shown_products == ["asin-1"]


def test_apply_request_constraints_updates_follow_up_state() -> None:
    state = RecommendationSessionState(
        session_id="session-1",
        shown_products=["asin-old"],
        active_constraints={"price_max": None, "excluded_products": [], "required_attributes": [], "excluded_attributes": []},
    )

    updated = apply_request_constraints(
        state,
        "something cheaper, fragrance-free, actually I want skincare not haircare, avoid that product",
        append_history=True,
    )

    assert updated.active_constraints["price_max"] == 25
    assert "fragrance free" in updated.active_constraints["required_attributes"]
    assert updated.active_constraints["category_filter"] == "skincare"
    assert "haircare" in updated.active_constraints["excluded_attributes"]
    assert "asin-old" in updated.active_constraints["excluded_products"]
    assert updated.conversation_history[-1]["content"].startswith("something cheaper")
