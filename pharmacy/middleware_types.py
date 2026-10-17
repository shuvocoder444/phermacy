"""Request annotations used by tenant-aware views."""

from django.http import HttpRequest

from .models import Tenant


class TenantRequest(HttpRequest):
    tenant: Tenant
