"""Suivi d'erreurs (4.7.2) : Sentry, seulement si `SENTRY_DSN` est donné.

Rien de personnel ne part : ni adresse IP, ni cookies, ni corps de requête, ni variables locales
(qui pourraient contenir le nom d'un élève ou un montant), seulement la trace de l'erreur.
"""


def init_sentry(dsn: str | None, release: str | None = None) -> bool:
    if not dsn:
        return False
    # Chargé seulement s'il sert (≈ 18 Mo par processus sinon, PERF.8).
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        release=release,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=0,
    )
    return True
