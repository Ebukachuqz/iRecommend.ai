from langchain_core.prompts import PromptTemplate

TASK_A_PROMPT_VERSION = "task_a_simulation_v1"

NIGERIAN_CONTEXT_SECTION = """Nigerian shopping context is enabled.
Consider practical consumer concerns only when relevant to the product metadata:
- affordability and value for money
- durability and long-lasting use
- delivery or packaging condition
- authenticity or fake-product risk
- hot or humid weather fit for beauty or skincare products
Do not force slang or Pidgin. Do not claim the user is Nigerian unless the persona supports it."""

NO_NIGERIAN_CONTEXT_SECTION = """Nigerian shopping context is disabled.
Do not add Nigerian-specific framing."""

TASK_A_REVIEW_PROMPT = PromptTemplate.from_template(
    """You simulate how this specific user would review this specific product.
Return JSON only. Do not include markdown fences or extra commentary.

Rules:
- Match the persona's writing style, strictness, review length, and rating behavior.
- Ground the review in the provided product metadata only.
- Do not invent product facts, delivery events, ingredients, sizes, brands, or usage outcomes.
- Use the statistical rating as guidance, but make an independent LLM rating estimate.
- The JSON must follow the output contract exactly.

Persona JSON:
{persona_json}

Product metadata:
{product_json}

Statistical rating prediction:
{statistical_prediction_json}

Context:
{context_json}

Nigerian context:
{nigerian_context}

Output contract:
{{
  "llm_predicted_rating": 4,
  "simulated_review_title": "string",
  "simulated_review_text": "string",
  "confidence": 0.0,
  "reasoning_summary": "short explanation",
  "evidence_used": ["persona signal", "product signal"]
}}
"""
)

TASK_A_REPAIR_PROMPT = PromptTemplate.from_template(
    """The following JSON is invalid or missing required fields according to the strict schema.

Required Schema:
{{
  "llm_predicted_rating": number,
  "simulated_review_title": string,
  "simulated_review_text": string,
  "confidence": number,
  "reasoning_summary": string,
  "evidence_used": [string]
}}

Raw Output to Repair:
{raw_text}

Return the repaired JSON exactly matching the schema. No markdown, no explanations."""
)
