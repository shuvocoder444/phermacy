from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

from .models import Membership

View = TypeVar("View", bound=Callable[..., HttpResponse])


def tenant_role_required(*roles: str) -> Callable[[View], View]:
    """Require an active membership in the resolved pharmacy."""
    def decorate(view: View) -> View:
        @wraps(view)
        def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            tenant = getattr(request, "tenant", None)
            if tenant is None or not request.user.is_authenticated:
                return HttpResponseForbidden("A pharmacy membership is required.")
            membership = Membership.objects.filter(
                tenant=tenant, user=request.user, is_active=True
            ).first()
            if membership is None or (roles and membership.role not in roles):
                return HttpResponseForbidden("Your pharmacy role cannot perform this action.")
            request.membership = membership  # type: ignore[attr-defined]
            return view(request, *args, **kwargs)

        return wrapped  # type: ignore[return-value]

    return decorate
