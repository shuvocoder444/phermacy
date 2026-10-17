"""Redis-backed medicine search and POS cart helpers."""

from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.cache import cache
from django.db.models import Q

from .models import Medicine, Tenant

TOP_MEDICINES_TTL = 60 * 60 * 6
CART_TTL = 60 * 60 * 12


def medicine_search(tenant: Tenant, query: str, limit: int = 12) -> list[dict[str, Any]]:
    """Search tenant catalog entries and cache the common-medicine hot set."""
    term = query.strip()
    if not term:
        ids = cache.get_or_set(
            f"tenant:{tenant.pk}:top-medicines",
            lambda: list(
                Medicine.objects.filter(tenant=tenant, is_active=True, is_common=True)
                .order_by("name_en")
                .values_list("pk", flat=True)[:1000]
            ),
            TOP_MEDICINES_TTL,
        )
        medicines = Medicine.objects.filter(
            tenant=tenant, is_active=True, pk__in=ids
        ).select_related("generic", "brand")[:limit]
    else:
        medicines = (
            Medicine.objects.filter(tenant=tenant, is_active=True)
            .filter(
                Q(name_en__icontains=term)
                | Q(name_bn__icontains=term)
                | Q(generic__name_en__icontains=term)
                | Q(generic__name_bn__icontains=term)
                | Q(brand__name_en__icontains=term)
                | Q(brand__name_bn__icontains=term)
            )
            .select_related("generic", "brand")
            .order_by("name_en")[:limit]
        )
    return [
        {
            "id": str(medicine.pk),
            "name": medicine.name_en,
            "name_bn": medicine.name_bn,
            "generic": medicine.generic.name_en,
            "brand": medicine.brand.name_en if medicine.brand else "",
            "strength": medicine.strength,
            "mrp": str(medicine.mrp),
            "stock": str(
                sum(
                    medicine.batches.filter(
                        tenant=tenant,
                        expiry_date__gte=__import__("django").utils.timezone.localdate(),
                    ).values_list("quantity_available", flat=True),
                    Decimal("0"),
                )
            ),
        }
        for medicine in medicines
    ]


def _cart_key(tenant: Tenant, session_key: str) -> str:
    return f"tenant:{tenant.pk}:cart:{session_key}"


def get_cart(tenant: Tenant, session_key: str) -> dict[str, Any]:
    """Return the current cart, creating a session key only when the caller asks."""
    return cache.get(
        _cart_key(tenant, session_key),
        {"items": {}, "discount_type": "none", "discount_value": "0"},
    )


def mutate_cart(
    tenant: Tenant,
    session_key: str,
    *,
    medicine_id: str | None = None,
    quantity: Decimal | None = None,
    discount_type: str | None = None,
    discount_value: Decimal | None = None,
    clear: bool = False,
) -> dict[str, Any]:
    """Serialize cart mutations with Redis locking to avoid lost concurrent updates."""
    key = _cart_key(tenant, session_key)
    lock = cache.lock(f"{key}:lock", timeout=10, blocking_timeout=5)
    with lock:
        cart = get_cart(tenant, session_key)
        if clear:
            cart = {"items": {}, "discount_type": "none", "discount_value": "0"}
        if medicine_id is not None and quantity is not None:
            try:
                new_quantity = Decimal(str(cart["items"].get(medicine_id, "0"))) + quantity
            except (InvalidOperation, KeyError) as exc:
                raise ValueError("Cart quantity is invalid.") from exc
            if new_quantity <= 0:
                cart["items"].pop(medicine_id, None)
            else:
                cart["items"][medicine_id] = str(new_quantity)
        if discount_type is not None:
            cart["discount_type"] = discount_type
        if discount_value is not None:
            cart["discount_value"] = str(discount_value)
        cache.set(key, cart, timeout=CART_TTL)
        return cart


def clear_cart(tenant: Tenant, session_key: str) -> None:
    mutate_cart(tenant, session_key, clear=True)
