"""Le seul fichier qui parle à l'API d'Anthropic (IA.1.1). Appelé par `ai.services.execute`,
jamais par une vue : un appel dure de quelques secondes à une minute. La clé n'existe que sur le
serveur (`ANTHROPIC_API_KEY` de `serveur.env`) ; aucune application ne la voit.

Le texte reçu ne sort pas d'ici sauf dans `Reply.text` : les services notent les jetons, jamais
le texte."""

from dataclasses import dataclass

from django.conf import settings

TIMEOUT = 100  # secondes, sous la limite dure de la tâche (`tasks.py`)


class NotConfigured(Exception):
    """Pas de clé sur ce serveur."""


@dataclass(frozen=True)
class Reply:
    text: str
    stop_reason: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


def complete(
    *, model: str, system: str, messages: list[dict], max_tokens: int, schema: dict | None = None
) -> Reply:
    """Une demande, une réponse. `system` : consignes fixes de l'usage (mises en cache) ; `schema` :
    schéma JSON de la réponse, vérifié par l'API. Plus d'une tentative de reprise : un appel de
    trop se paie."""
    if not settings.ANTHROPIC_API_KEY:
        raise NotConfigured
    import anthropic  # lourd (pydantic, httpx2) : chargé ici, pas au démarrage de chaque processus

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=TIMEOUT, max_retries=1)
    output_config: dict = {"effort": "medium"}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
        output_config=output_config,
    )
    usage = response.usage
    return Reply(
        text="".join(block.text for block in response.content if block.type == "text"),
        stop_reason=response.stop_reason or "",
        model=model,
        input_tokens=usage.input_tokens or 0,
        output_tokens=usage.output_tokens or 0,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )
