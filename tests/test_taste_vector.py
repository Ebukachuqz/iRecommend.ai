from src.task_b_recommendation.taste_vector import parse_embedding, weighted_average


def test_weighted_average_uses_rating_weights() -> None:
    average = weighted_average([[1.0, 0.0], [0.0, 1.0]], [1.0, 2.0])

    assert average == [1 / 3, 2 / 3]


def test_parse_pgvector_string_embedding() -> None:
    assert parse_embedding("[0.1,0.2,0.3]") == [0.1, 0.2, 0.3]
