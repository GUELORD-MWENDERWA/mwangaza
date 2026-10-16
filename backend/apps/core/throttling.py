"""Limites de débit de l'API (PERF.5a) : la recherche et les sorties lourdes (PDF, Excel, exports)
sont comptées par compte connecté, sinon par adresse. La connexion a déjà ses propres blocages
(`accounts/attempts.py`).

Un PDF déjà en préparation ou prêt est rendu par `PrintJobMiddleware` avant la vue : l'actualisation
de la page d'attente n'est donc pas comptée, seule une nouvelle demande l'est. Les compteurs sont
dans le cache (Redis en production, partagé entre les travailleurs de Gunicorn)."""

from rest_framework.throttling import SimpleRateThrottle

from apps.core.http import client_ip

OUTPUTS = {"pdf", "xlsx", "csv"}


class _Throttle(SimpleRateThrottle):
    def applies(self, request) -> bool:
        raise NotImplementedError

    def get_cache_key(self, request, view) -> str | None:
        user = request.user
        ident = f"u{user.pk}" if user and user.is_authenticated else f"ip{client_ip(request)}"
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def allow_request(self, request, view) -> bool:
        return super().allow_request(request, view) if self.applies(request) else True


class SearchThrottle(_Throttle):
    scope = "search"

    def applies(self, request) -> bool:
        return bool(request.query_params.get("search"))


class OutputThrottle(_Throttle):
    scope = "output"

    def applies(self, request) -> bool:
        return request.query_params.get("output") in OUTPUTS or request.path.endswith("/export/")
