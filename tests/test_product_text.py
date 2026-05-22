from src.task_b_recommendation.product_text import build_product_text


def test_product_text_includes_rich_metadata() -> None:
    text = build_product_text(
        {
            "title": "Gentle Face Cream",
            "features": ["non greasy", "fragrance free"],
            "description": ["Good for daily use"],
            "details": {"skin_type": "oily"},
        }
    )

    assert "Gentle Face Cream" in text
    assert "non greasy" in text
    assert "Good for daily use" in text
    assert "skin_type: oily" in text
