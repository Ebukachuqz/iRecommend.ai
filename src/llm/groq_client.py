import os

from langchain_groq import ChatGroq

from src.config import get_settings


def get_groq_chat(model_name: str | None = None, temperature: float = 0.2) -> ChatGroq:
    settings = get_settings()
    api_key = settings.require_groq_api_key()
    os.environ["GROQ_API_KEY"] = api_key
    return ChatGroq(model=model_name or settings.groq_model, temperature=temperature)
