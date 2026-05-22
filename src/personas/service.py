from typing import Any

from supabase import Client

from src.personas.generator import PersonaGenerator


class PersonaService:
    def __init__(self, client: Client | None = None) -> None:
        self.generator = PersonaGenerator(client=client)

    def regenerate_persona(self, user_id: str, category: str | None = None) -> dict[str, Any]:
        return self.generator.regenerate_persona(user_id=user_id, category=category, store=True)
