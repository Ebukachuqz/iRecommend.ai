from src.task_b_recommendation.product_text import build_product_text, get_category_path, get_price_tier, is_embeddable


def test_product_text_includes_rich_metadata() -> None:
    text = build_product_text(
        {
            "title": "Gentle Face Cream",
            "categories": [["Beauty", "Skin Care", "Face Creams"]],
            "features": ["non greasy", "fragrance free"],
            "description": ["Good for daily use.", "Works under makeup.", "Third useful sentence.", "Extra noise."],
            "store": "Example Brand",
            "price": 18.99,
            "details": {"skin_type": "oily", "size": "50ml"},
        }
    )

    assert "Gentle Face Cream" in text
    assert "Beauty > Skin Care > Face Creams" in text
    assert "non greasy" in text
    assert "Good for daily use" in text
    assert "Example Brand" in text
    assert "Price tier: mid-range" in text
    assert "skin_type: oily" in text
    assert "18.99" not in text


def test_price_tier_thresholds() -> None:
    assert get_price_tier(5) == "budget"
    assert get_price_tier(18.99) == "mid-range"
    assert get_price_tier(45) == "premium"
    assert get_price_tier(120) == "luxury"


def test_category_path_uses_categories_then_fallbacks() -> None:
    assert get_category_path({"categories": [["Beauty", "Skin Care"]]}) == "Beauty > Skin Care"
    assert get_category_path({"main_category": "Books"}) == "Books"
    assert get_category_path({"category": "Electronics"}) == "Electronics"


def test_is_embeddable_requires_title_and_category_signal() -> None:
    assert is_embeddable({"title": "Cream", "category": "All_Beauty"}) is True
    assert is_embeddable({"title": "Cream"}) is False
    assert is_embeddable({"category": "All_Beauty"}) is False
