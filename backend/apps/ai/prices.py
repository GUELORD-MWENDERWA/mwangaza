"""Prix des modèles, en micro-dollars par million de jetons (1 $ par million de jetons =
1 000 000). Départ : tarif public à la date de la tâche ; la console les change
(`AiSettings.prices`, IA.1.2). Écrits en entiers : jamais de `float` (règle 2)."""

INPUT, OUTPUT, CACHE_READ, CACHE_WRITE = "input", "output", "cache_read", "cache_write"
PER = 1_000_000
CREDIT = 1_000  # 1 crédit = un millième de dollar = 1 000 micro-dollars


def _price(input_, output, cache_read):
    return {
        INPUT: input_,
        OUTPUT: output,
        CACHE_READ: cache_read,
        CACHE_WRITE: input_ * 5 // 4,  # écriture du cache : 1,25 fois l'entrée
    }


DEFAULT_PRICES = {
    "claude-opus-5-5": _price(4_000_000, 20_000_000, 200_000),
    "claude-sonnet-5-5": _price(2_000_000, 10_000_000, 200_000),
    "claude-haiku-5-5": _price(100_000, 500_000, 10_000),
}


def cost(prices: dict, *, input_=0, output=0, cache_read=0, cache_write=0) -> int:
    """Coût en micro-dollars, arrondi au-dessus (un appel ne coûte jamais zéro de trop peu)."""
    total = (
        input_ * prices[INPUT]
        + output * prices[OUTPUT]
        + cache_read * prices[CACHE_READ]
        + cache_write * prices[CACHE_WRITE]
    )
    return -(-total // PER)
