"""Hachage Argon2 qui ne s'exécute qu'un à la fois par processus (PERF.5a).

Argon2 réserve ≈ 100 Mo pour chaque mot de passe vérifié. Avec plusieurs fils par processus
Gunicorn, une dizaine de connexions simultanées (début de journée dans une école) demandaient
plusieurs centaines de Mo d'un coup et le conteneur était arrêté pour manque de mémoire
(constaté sur `make prod-local`, limite de 448 Mo). Ici les fils attendent leur tour : le
format des mots de passe enregistrés ne change pas."""

import threading

from django.contrib.auth.hashers import Argon2PasswordHasher

_one_at_a_time = threading.BoundedSemaphore(1)


class SerialArgon2PasswordHasher(Argon2PasswordHasher):
    # Même nom d'algorithme : les mots de passe déjà enregistrés restent valables.
    algorithm = "argon2"

    def encode(self, password, salt, *args, **kwargs):
        with _one_at_a_time:
            return super().encode(password, salt, *args, **kwargs)

    def verify(self, password, encoded):
        with _one_at_a_time:
            return super().verify(password, encoded)
