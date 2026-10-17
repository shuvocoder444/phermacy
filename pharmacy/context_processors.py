from django.http import HttpRequest


def tenant_context(request: HttpRequest) -> dict[str, object]:
    """Expose the resolved pharmacy to templates."""
    return {"tenant": getattr(request, "tenant", None)}
