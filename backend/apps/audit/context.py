"""Adresse IP, navigateur et session support de la requête en cours, pour chaque entrée du
journal.

Posés une fois par requête par `AuditMiddleware`, comme l'école courante : les services n'ont pas
à recevoir la requête. Vides dans une commande ou une tâche Celery.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class RequestInfo:
    ip: str | None = None
    user_agent: str = ""
    # Super-admin en session support (A3) dans l'école `support_school_id`.
    impersonated_by: Any = None
    support_school_id: UUID | None = None
    # Appareil enregistré de la session, dans l'école `device_school_id`.
    device_id: str | None = None
    device_school_id: UUID | None = None


_NO_REQUEST = RequestInfo()
_request_info: ContextVar[RequestInfo | None] = ContextVar("audit_request_info", default=None)


def current_request_info() -> RequestInfo:
    return _request_info.get() or _NO_REQUEST


@contextmanager
def use_request_info(info: RequestInfo) -> Iterator[RequestInfo]:
    token = _request_info.set(info)
    try:
        yield info
    finally:
        _request_info.reset(token)
