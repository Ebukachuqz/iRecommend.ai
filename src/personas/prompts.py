from langchain_core.prompts import PromptTemplate


PERSONA_SYSTEM_INSTRUCTIONS = """You generate structured user personas from review history.
Return JSON only. Do not include markdown fences or commentary.
Preserve the requested schema exactly and base claims on the provided evidence.
Do not force Nigerian slang, Pidgin, or unsupported identity details."""


PERSONA_PROMPT = PromptTemplate.from_template(
    """{instructions}

Category: {category}

User statistics:
{user_stats}

Review evidence:
{review_context}

Output JSON schema:
{schema_example}
"""
)


PERSONA_SCHEMA_EXAMPLE = {
    "writing_style": {
        "tone": "",
        "length": "medium",
        "detail_level": "medium",
        "formality": "mixed",
        "vocabulary_markers": [],
        "common_phrases": [],
    },
    "preferences": {
        "liked_product_types": [],
        "disliked_product_types": [],
        "liked_attributes": [],
        "disliked_attributes": [],
        "what_they_value": [],
        "common_complaints": [],
    },
    "rating_behavior": {
        "average_rating": 0.0,
        "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        "strictness": "moderate",
        "rating_patterns": "",
    },
    "purchase_behavior": {
        "preferred_categories": [],
        "price_sensitivity": "unknown",
        "quality_sensitivity": "medium",
        "verified_purchase_ratio": 0.0,
    },
    "cultural_signals": "",
    "evidence": {
        "positive_examples": [],
        "negative_examples": [],
    },
}
