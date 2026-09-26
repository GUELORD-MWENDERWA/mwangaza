"""Réglages du schéma OpenAPI (drf-spectacular), lu par le client typé du front."""

# Champs d'une réponse qui peuvent manquer : les erreurs de saisie ne viennent qu'avec `invalid`.
OPTIONAL_RESPONSE_FIELDS = {"Error": {"fields"}}


def responses_always_have_every_field(result, generator, request, public):
    """Dans une réponse, un serializer renvoie toujours tous ses champs (null s'il le faut) : ils
    sont obligatoires dans les types du front, même avec une valeur par défaut dans le modèle.
    Les schémas d'envoi (`…Request`, `Patched…Request`) ne changent pas."""
    for name, schema in result.get("components", {}).get("schemas", {}).items():
        if name.endswith("Request") or "properties" not in schema:
            continue
        optional = OPTIONAL_RESPONSE_FIELDS.get(name, set())
        schema["required"] = [field for field in schema["properties"] if field not in optional]
    return result
