"""Inventory-safe checkout and customer due collection workflows."""

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Customer,
    DueLedger,
    Medicine,
    Sale,
    SaleItem,
    StockBatch,
    StockMovement,
    Tenant,
)

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round a monetary value using the conventional half-up rule."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def checkout(
    *,
    tenant: Tenant,
    cashier: Any,
    cart: dict[str, Any],
    customer_phone: str,
    paid_amount: Decimal,
    payment_method: str,
    payment_reference: str = "",
) -> Sale:
    """Create an invoice and consume FEFO stock in one database transaction."""
    if not cart.get("items"):
        raise ValidationError("The cart is empty.")
    if payment_method not in Sale.PaymentMethod.values:
        raise ValidationError("Select a valid payment method.")
    if paid_amount < 0:
        raise ValidationError("Paid amount cannot be negative.")

    with transaction.atomic():
        sale_lines: list[dict[str, Any]] = []
        subtotal = Decimal("0")
        vat_total = Decimal("0")
        for medicine_id, raw_quantity in cart["items"].items():
            try:
                quantity = Decimal(str(raw_quantity))
                if quantity <= 0:
                    raise ValueError
            except (ValueError, ArithmeticError):
                raise ValidationError("Cart contains an invalid quantity.") from None

            medicine = Medicine.objects.filter(
                tenant=tenant, pk=medicine_id, is_active=True
            ).first()
            if medicine is None:
                raise ValidationError("A medicine in the cart is no longer available.")

            batches = list(
                StockBatch.objects.select_for_update()
                .filter(
                    tenant=tenant,
                    medicine=medicine,
                    expiry_date__gte=timezone.localdate(),
                    quantity_available__gt=0,
                )
                .order_by("expiry_date", "id")
            )
            remaining = quantity
            for batch in batches:
                picked = min(remaining, batch.quantity_available)
                if picked <= 0:
                    continue
                line_base = money(picked * batch.mrp)
                line_vat = money(line_base * medicine.vat_rate / Decimal("100"))
                sale_lines.append(
                    {
                        "medicine": medicine,
                        "batch": batch,
                        "quantity": picked,
                        "price": batch.mrp,
                        "purchase_price": batch.purchase_price,
                        "vat_rate": medicine.vat_rate,
                        "line_total": line_base,
                        "vat": line_vat,
                    }
                )
                subtotal += line_base
                vat_total += line_vat
                remaining -= picked
                if remaining == 0:
                    break
            if remaining > 0:
                raise ValidationError(
                    f"Insufficient unexpired stock for {medicine.name_en}."
                )

        discount_type = cart.get("discount_type", Sale.DiscountType.NONE)
        discount_value = Decimal(str(cart.get("discount_value", "0")))
        if discount_value < 0:
            raise ValidationError("Discount cannot be negative.")
        if discount_type == Sale.DiscountType.PERCENT:
            if discount_value > 100:
                raise ValidationError("Percentage discount cannot exceed 100%.")
            discount = money(subtotal * discount_value / Decimal("100"))
        elif discount_type == Sale.DiscountType.FLAT:
            discount = money(min(discount_value, subtotal))
        elif discount_type == Sale.DiscountType.NONE:
            discount = Decimal("0.00")
            discount_value = Decimal("0")
        else:
            raise ValidationError("Select a valid discount type.")

        # Allocate invoice discount proportionally so item totals remain auditable.
        undiscounted = subtotal + vat_total
        total_discount = money(discount + vat_total * discount / subtotal) if subtotal else discount
        total = money(max(Decimal("0"), undiscounted - total_discount))
        if paid_amount > total:
            raise ValidationError("Paid amount cannot exceed the invoice total.")
        paid_amount = money(paid_amount)
        customer = None
        if customer_phone.strip():
            normalized = "".join(
                char for char in customer_phone.strip() if char.isdigit() or char == "+"
            )
            customer, _ = Customer.objects.get_or_create(
                tenant=tenant,
                phone_normalized=normalized,
                defaults={"phone": customer_phone.strip()},
            )
        if paid_amount < total and customer is None:
            raise ValidationError("A customer phone number is required for a due balance.")

        invoice_number = (
            f"{timezone.localdate():%y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        )
        sale = Sale.objects.create(
            tenant=tenant,
            cashier=cashier,
            customer=customer,
            invoice_number=invoice_number,
            subtotal=money(subtotal),
            discount_type=discount_type,
            discount_value=discount_value,
            discount_amount=money(discount),
            vat_amount=money(vat_total),
            total=total,
            amount_paid=paid_amount,
            payment_method=payment_method,
            payment_reference=payment_reference,
        )

        for line in sale_lines:
            batch = line["batch"]
            batch.quantity_available -= line["quantity"]
            batch.save(update_fields=("quantity_available", "updated_at"))
            SaleItem.objects.create(
                tenant=tenant,
                sale=sale,
                medicine=line["medicine"],
                batch=batch,
                quantity=line["quantity"],
                unit_price=line["price"],
                purchase_price=line["purchase_price"],
                vat_rate=line["vat_rate"],
                line_total=money(line["line_total"] + line["vat"]),
            )
            StockMovement.objects.create(
                tenant=tenant,
                batch=batch,
                movement_type=StockMovement.MovementType.SALE,
                quantity_delta=-line["quantity"],
                reference=invoice_number,
            )
        if customer and paid_amount < total:
            DueLedger.objects.create(
                tenant=tenant,
                customer=customer,
                sale=sale,
                entry_type=DueLedger.EntryType.CHARGE,
                amount=money(total - paid_amount),
                note=f"Due from invoice {invoice_number}",
            )
        return sale


def collect_due(
    *,
    tenant: Tenant,
    customer_id: int,
    amount: Decimal,
    payment_method: str,
    reference: str = "",
) -> DueLedger:
    """Record a partial or full customer repayment without allowing overpayment."""
    if amount <= 0:
        raise ValidationError("Collection amount must be greater than zero.")
    with transaction.atomic():
        customer = Customer.objects.select_for_update().filter(
            tenant=tenant, pk=customer_id
        ).first()
        if customer is None:
            raise ValidationError("Customer was not found.")
        totals = DueLedger.objects.filter(tenant=tenant, customer=customer).aggregate(
            charges=Sum(
                "amount", filter=models.Q(entry_type=DueLedger.EntryType.CHARGE)
            ),
            payments=Sum(
                "amount", filter=models.Q(entry_type=DueLedger.EntryType.PAYMENT)
            ),
        )
        balance = (totals["charges"] or Decimal("0")) - (
            totals["payments"] or Decimal("0")
        )
        if amount > balance:
            raise ValidationError("Collection cannot exceed the customer's due balance.")
        return DueLedger.objects.create(
            tenant=tenant,
            customer=customer,
            entry_type=DueLedger.EntryType.PAYMENT,
            amount=money(amount),
            payment_method=payment_method,
            reference=reference,
        )


from django.db import models
