from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

from django.core.cache import cache

from inventory.models import DrugBatch

_LOCAL_CART_LOCKS: dict[str, threading.RLock] = {}
_LOCAL_CART_LOCKS_GUARD = threading.Lock()


class POSCartManager:
    """
    Manages active Point-of-Sale cart sessions in Redis.
    Provides sub-millisecond response times for HTMX item additions, updates, and calculations.
    """
    SESSION_PREFIX = "pharma:pos_cart:"
    CART_TTL = 86400  # 24 hours

    def __init__(self, session_key: str, tenant_id: str):
        self.session_key = session_key
        self.tenant_id = tenant_id
        self.cache_key = f"{self.SESSION_PREFIX}{tenant_id}:{session_key}"

    def _get_raw_cart(self) -> dict[str, Any]:
        data = cache.get(self.cache_key)
        if not data:
            return {
                "items": {},  # key: batch_id
                "customer_id": None,
                "customer_name": "Walk-in Customer",
                "customer_phone": "",
                "discount_percent": "0.00",
                "discount_flat": "0.00",
                "vat_percent": "0.00",
                "doctor_name": "",
            }
        return data

    def _save_raw_cart(self, data: dict[str, Any]) -> None:
        cache.set(self.cache_key, data, timeout=self.CART_TTL)

    def _write_lock(self):
        """Use the cache backend's distributed lock, or a local thread lock."""
        cache_lock = getattr(cache, "lock", None)
        if callable(cache_lock):
            return cache_lock(f"{self.cache_key}:write-lock", timeout=10, blocking_timeout=5)

        # LocMemCache (the development backend) does not implement cache.lock.
        # Keep local multi-threaded requests safe without requiring Redis.
        with _LOCAL_CART_LOCKS_GUARD:
            return _LOCAL_CART_LOCKS.setdefault(self.cache_key, threading.RLock())

    def add_item(self, batch_id: str, quantity: int = 1) -> dict[str, Any]:
        """
        Adds a medicine batch to the cart. If already present, increments the quantity.
        """
        return self.add_items([(batch_id, quantity)])

    def add_items(self, batch_quantities: list[tuple[str, int]]) -> dict[str, Any]:
        """Add one or more batches in one locked read/modify/write cycle."""
        if not batch_quantities:
            return self.get_cart_summary()

        # Resolve all batches in one query before taking the short Redis lock.
        requested = {}
        for batch_id, quantity in batch_quantities:
            requested[str(batch_id)] = requested.get(str(batch_id), 0) + max(0, int(quantity))
        batches = DrugBatch.objects.filter(id__in=requested).select_related(
            "drug", "drug__dosage_form"
        )
        batch_map = {str(batch.id): batch for batch in batches}

        # Concurrent clicks used to race: each request read the same cart and the
        # last Redis write silently discarded the other additions.
        with self._write_lock():
            cart = self._get_raw_cart()
            for batch_key, quantity in requested.items():
                batch = batch_map.get(batch_key)
                if not batch or quantity <= 0:
                    continue
                current = cart["items"].get(batch_key)
                new_qty = min((current["quantity"] if current else 0) + quantity, batch.current_stock)
                if current:
                    current["quantity"] = new_qty
                    current["max_stock"] = batch.current_stock
                elif new_qty > 0:
                    dosage = batch.drug.dosage_form
                    cart["items"][batch_key] = {
                        "batch_id": str(batch.id),
                        "drug_id": str(batch.drug.id),
                        "brand_name": batch.drug.brand_name,
                        "strength": batch.drug.strength,
                        "dosage_form": (dosage.short_name or dosage.name) if dosage else "Tab",
                        "batch_number": batch.batch_number,
                        "expiry_date": batch.expiry_date.strftime("%Y-%m-%d") if batch.expiry_date else "",
                        "unit_mrp": str(batch.unit_mrp),
                        "unit_tp": str(batch.purchase_price),
                        "max_stock": batch.current_stock,
                        "quantity": new_qty,
                    }
            self._save_raw_cart(cart)
        return self.get_cart_summary()

    def update_quantity(self, batch_id: str, quantity: int) -> dict[str, Any]:
        """
        Updates quantity for a specific line item in the cart.
        """
        cart = self._get_raw_cart()
        batch_key = str(batch_id)

        if batch_key in cart["items"]:
            if quantity <= 0:
                del cart["items"][batch_key]
            else:
                max_stock = cart["items"][batch_key]["max_stock"]
                cart["items"][batch_key]["quantity"] = min(quantity, max_stock)
            self._save_raw_cart(cart)

        return self.get_cart_summary()

    def remove_item(self, batch_id: str) -> dict[str, Any]:
        """
        Removes a line item completely from the cart.
        """
        cart = self._get_raw_cart()
        batch_key = str(batch_id)
        if batch_key in cart["items"]:
            del cart["items"][batch_key]
            self._save_raw_cart(cart)
        return self.get_cart_summary()

    def set_discount(self, discount_percent: Decimal = Decimal("0.00"), discount_flat: Decimal = Decimal("0.00")) -> dict[str, Any]:
        """
        Applies a percentage or flat discount (in BDT) to the overall cart.
        """
        cart = self._get_raw_cart()
        cart["discount_percent"] = str(discount_percent)
        cart["discount_flat"] = str(discount_flat)
        self._save_raw_cart(cart)
        return self.get_cart_summary()

    def set_customer(self, customer_id: str | None, name: str, phone: str) -> dict[str, Any]:
        """
        Attaches a customer profile to the current cart.
        """
        cart = self._get_raw_cart()
        cart["customer_id"] = customer_id
        cart["customer_name"] = name
        cart["customer_phone"] = phone
        self._save_raw_cart(cart)
        return self.get_cart_summary()

    def clear(self) -> None:
        """
        Empties the active POS cart in Redis.
        """
        cache.delete(self.cache_key)

    def get_cart_summary(self) -> dict[str, Any]:
        """
        Computes line item totals, subtotal MRP, discount, VAT, and net payable.
        """
        cart = self._get_raw_cart()
        items_list = []
        subtotal_mrp = Decimal("0.00")
        total_items_count = 0

        for batch_key, item in cart["items"].items():
            qty = Decimal(str(item["quantity"]))
            unit_mrp = Decimal(item["unit_mrp"])
            line_total = qty * unit_mrp
            subtotal_mrp += line_total
            total_items_count += item["quantity"]

            items_list.append({
                **item,
                "line_total": f"{line_total:.2f}",
            })

        # Calculate Discounts
        discount_pct = Decimal(cart.get("discount_percent", "0.00"))
        discount_flat = Decimal(cart.get("discount_flat", "0.00"))
        
        calculated_disc = (subtotal_mrp * (discount_pct / Decimal("100.00"))) + discount_flat
        discount_amount = min(calculated_disc, subtotal_mrp)
        
        # Calculate VAT (Bangladesh Drug retail VAT default 0.0%)
        vat_pct = Decimal(cart.get("vat_percent") or "0.00")
        taxable_amount = max(Decimal("0.00"), subtotal_mrp - discount_amount)
        vat_amount = (taxable_amount * (vat_pct / Decimal("100.00"))).quantize(Decimal("0.01"))
        
        # Net Payable
        net_payable = (taxable_amount + vat_amount).quantize(Decimal("0.01"))

        return {
            "items": items_list,
            "total_items_count": total_items_count,
            "subtotal": f"{subtotal_mrp:.2f}",
            "subtotal_mrp": f"{subtotal_mrp:.2f}",
            "discount_percent": f"{discount_pct:.2f}",
            "discount_flat": f"{discount_flat:.2f}",
            "discount_amount": f"{discount_amount:.2f}",
            "total_discount": f"{discount_amount:.2f}",
            "vat_percent": f"{vat_pct:.2f}",
            "vat_amount": f"{vat_amount:.2f}",
            "total_payable": f"{net_payable:.2f}",
            "grand_total": f"{net_payable:.2f}",
            "customer_id": cart.get("customer_id"),
            "customer_name": cart.get("customer_name", "Walk-in Customer"),
            "customer_phone": cart.get("customer_phone", ""),
            "doctor_name": cart.get("doctor_name", ""),
        }
