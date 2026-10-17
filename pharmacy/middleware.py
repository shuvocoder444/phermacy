"""Resolve a pharmacy from the request host and scope database access."""

from collections.abc import Callable
from typing import Any

from django.db import connection, transaction
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound

from .models import TenantDomain


class TenantMiddleware:
    """Wrap a request in tenant context so PostgreSQL RLS can enforce isolation."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        hostname = request.get_host().split(":", 1)[0].rstrip(".").lower()
        domain = TenantDomain.objects.select_related("tenant").filter(
            domain=hostname, tenant__is_active=True
        ).first()
        if domain is None:
            return HttpResponseNotFound("No active pharmacy is configured for this domain.")

        request.tenant = domain.tenant  # type: ignore[attr-defined]
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    [str(domain.tenant_id)],
                )
            response = self.get_response(request)
            return response
