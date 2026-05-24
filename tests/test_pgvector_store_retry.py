import httpx

from src.task_b_recommendation.pgvector_store import SupabasePgVectorStore


class ExecuteFlaky:
    def __init__(self, *, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def execute(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise httpx.ReadError("connection reset")
        return type("Resp", (), {"data": []})()


class TableRecorder:
    def __init__(self, flaky: ExecuteFlaky) -> None:
        self.flaky = flaky
        self.last_payload = None
        self.last_on_conflict = None

    def upsert(self, payload, on_conflict=None):
        self.last_payload = payload
        self.last_on_conflict = on_conflict
        return self.flaky


class ClientRecorder:
    def __init__(self, flaky: ExecuteFlaky) -> None:
        self.flaky = flaky
        self.table_calls = []

    def table(self, name):
        self.table_calls.append(name)
        return TableRecorder(self.flaky)


def test_upsert_product_embedding_retries_transient_network_errors(monkeypatch) -> None:
    flaky = ExecuteFlaky(fail_times=2)
    client = ClientRecorder(flaky)
    store = SupabasePgVectorStore(client=client)

    monkeypatch.setattr("src.task_b_recommendation.pgvector_store.time.sleep", lambda _s: None)

    store.upsert_product_embedding(
        parent_asin="asin-1",
        embedding=[0.0] * 384,
        embedding_model="test-model",
        product_text="Title: Test",
    )

    assert flaky.calls == 3
