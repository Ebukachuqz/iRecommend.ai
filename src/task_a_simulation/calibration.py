from __future__ import annotations

from math import sqrt
from typing import Any

from src.task_a_simulation.rating_predictor import clamp_rating, get_persona_section, user_average_from_persona
from src.task_a_simulation.schema import RatingPredictionBreakdown


def rating_distribution_stddev(distribution: dict[str, Any], average: float) -> float:
    total = sum(int(value or 0) for value in distribution.values())
    if total <= 1:
        return 1.0
    variance = sum(((int(rating) - average) ** 2) * int(count or 0) for rating, count in distribution.items()) / total
    return max(0.5, sqrt(variance))


def user_has_never_given_five(distribution: dict[str, Any]) -> bool:
    return int(distribution.get("5", 0) or 0) == 0


def calibrate_rating(
    persona: dict[str, Any],
    statistical_prediction: RatingPredictionBreakdown,
    llm_predicted_rating: float,
) -> RatingPredictionBreakdown:
    rating_behavior = get_persona_section(persona, "rating_behavior")
    distribution = rating_behavior.get("rating_distribution", {})
    strictness = rating_behavior.get("strictness", "moderate")
    user_average = user_average_from_persona(persona)
    blended = (
        0.45 * statistical_prediction.statistical_predicted_rating
        + 0.35 * llm_predicted_rating
        + 0.20 * user_average
    )
    explanations = [
        "Weighted blend used 0.45 statistical, 0.35 LLM, and 0.20 user average."
    ]

    stddev = rating_distribution_stddev(distribution, user_average)
    if blended > user_average + stddev:
        blended = user_average + (0.65 * stddev)
        explanations.append("Pulled rating toward user mean because it was unusually high.")

    if strictness == "strict" and blended > 4.4:
        blended = min(blended, 4.4)
        explanations.append("Strict user calibration capped an overly high score.")

    if user_has_never_given_five(distribution) and blended >= 4.75:
        strong_evidence = (
            statistical_prediction.preference_match_score >= 0.45
            and statistical_prediction.disliked_attribute_penalty == 0
            and llm_predicted_rating >= 4.8
        )
        if not strong_evidence:
            blended = 4.49
            explanations.append("Avoided a 5-star result because the user has no historical 5-star ratings.")

    final_rating = clamp_rating(blended)
    return statistical_prediction.model_copy(
        update={
            "llm_predicted_rating": round(float(llm_predicted_rating), 3),
            "final_predicted_rating": round(final_rating, 3),
            "explanation": f"{statistical_prediction.explanation} {' '.join(explanations)}",
        }
    )
