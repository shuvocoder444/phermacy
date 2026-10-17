from django import template
from django.core.cache import cache

from pharmacy.models import Medicine, Tenant

register = template.Library()


@register.filter
def medicine_info(medicine_id: str, tenant: Tenant) -> Medicine | None:
    """Resolve cart lines through tenant scope and cache medicine display data."""
    key = f"tenant:{tenant.pk}:cart-medicine:{medicine_id}"
    medicine = cache.get(key)
    if medicine is None:
        medicine = Medicine.objects.filter(tenant=tenant, pk=medicine_id).first()
        if medicine is not None:
            cache.set(key, medicine, 300)
    return medicine
