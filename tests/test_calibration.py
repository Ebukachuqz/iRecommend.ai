from src.task_a_simulation.calibration import calibrate_rating


def strict_persona() -> dict:
    return {
        "rating_behavior": {
            "average_rating": 3.5,
            "rating_distribution": {"1": 1, "2": 1, "3": 4, "4": 6, "5": 0},
            "strictness": "strict",
        }
    }


def test_calibrated_rating_stays_between_one_and_five(sample_rating_breakdown) -> None:
    result = calibrate_rating(strict_persona(), sample_rating_breakdown, llm_predicted_rating=4.8)

    assert 1 <= result.final_predicted_rating <= 5


def test_strict_user_is_not_easily_pushed_to_five(sample_rating_breakdown) -> None:
    result = calibrate_rating(strict_persona(), sample_rating_breakdown, llm_predicted_rating=5)

    assert result.final_predicted_rating < 5
