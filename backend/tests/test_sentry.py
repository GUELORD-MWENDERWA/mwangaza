"""Suivi d'erreurs : sans DSN rien n'est branché ; avec DSN, aucune donnée personnelle ne part."""

import sentry_sdk

from config.sentry import init_sentry


def test_without_dsn_nothing_is_sent():
    assert init_sentry(None) is False
    assert init_sentry("") is False


def test_with_dsn_no_personal_data_is_sent():
    try:
        assert init_sentry("https://cle@sentry.example/1") is True
        options = sentry_sdk.get_client().options
        assert options["send_default_pii"] is False
        assert options["include_local_variables"] is False
        assert options["max_request_body_size"] == "never"
    finally:
        sentry_sdk.get_global_scope().set_client(None)
