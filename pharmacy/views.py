"""POS, due collection, and receipt endpoints."""

from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from .cache import clear_cart, get_cart, medicine_search, mutate_cart
from .decorators import tenant_role_required
from .forms import CheckoutForm, DueCollectionForm
from .models import Customer, DueLedger, Sale, Tenant
from .services import checkout, collect_due


def _tenant(request: HttpRequest) -> Tenant:
    return request.tenant  # type: ignore[attr-defined,no-any-return]


def _session_key(request: HttpRequest) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ""


@login_required
@tenant_role_required()
def pos(request: HttpRequest) -> HttpResponse:
    """Render the single-screen point-of-sale interface."""
    cart = get_cart(_tenant(request), _session_key(request))
    results = medicine_search(_tenant(request), "")
    return render(request, "pharmacy/pos.html", {"cart": cart, "results": results})


@login_required
@tenant_role_required()
def pos_search(request: HttpRequest) -> HttpResponse:
    """Return the reactive medicine list for the POS."""
    query = request.GET.get("q", "")[:100]
    results = medicine_search(_tenant(request), query)
    return render(request, "pharmacy/partials/search_results.html", {"results": results})


@login_required
@tenant_role_required()
@require_POST
def cart_add(request: HttpRequest) -> HttpResponse:
    """Add a medicine quantity to the current Redis-backed cart."""
    medicine_id = request.POST.get("medicine_id", "")
    try:
        quantity = Decimal(request.POST.get("quantity", "1"))
        if quantity <= 0 or quantity > Decimal("10000"):
            raise InvalidOperation
        cart = mutate_cart(
            _tenant(request),
            _session_key(request),
            medicine_id=medicine_id,
            quantity=quantity,
        )
    except (InvalidOperation, ValueError):
        return HttpResponseBadRequest("Enter a valid positive quantity.")
    return render(
        request,
        "pharmacy/partials/cart.html",
        {"cart": cart, "tenant": _tenant(request)},
    )


@login_required
@tenant_role_required()
@require_POST
def cart_discount(request: HttpRequest) -> HttpResponse:
    """Apply a flat or percentage discount to the invoice."""
    discount_type = request.POST.get("discount_type", "")
    try:
        value = Decimal(request.POST.get("discount_value", "0"))
        if value < 0 or discount_type not in Sale.DiscountType.values:
            raise InvalidOperation
        cart = mutate_cart(
            _tenant(request),
            _session_key(request),
            discount_type=discount_type,
            discount_value=value,
        )
    except (InvalidOperation, ValueError):
        return HttpResponseBadRequest("Enter a valid discount.")
    return render(
        request, "pharmacy/partials/cart.html", {"cart": cart, "tenant": _tenant(request)}
    )


@login_required
@tenant_role_required()
@require_POST
def cart_remove(request: HttpRequest, medicine_id: str) -> HttpResponse:
    """Remove a line by applying its negative cart quantity."""
    cart = get_cart(_tenant(request), _session_key(request))
    quantity = Decimal(str(cart.get("items", {}).get(medicine_id, "0")))
    cart = mutate_cart(
        _tenant(request),
        _session_key(request),
        medicine_id=medicine_id,
        quantity=-quantity,
    )
    return render(
        request, "pharmacy/partials/cart.html", {"cart": cart, "tenant": _tenant(request)}
    )


@login_required
@tenant_role_required()
@require_POST
def checkout_view(request: HttpRequest) -> HttpResponse:
    """Validate tender and atomically create an invoice, ledger entry, and stock movements."""
    form = CheckoutForm(request.POST)
    cart = get_cart(_tenant(request), _session_key(request))
    if not form.is_valid():
        return render(
            request,
            "pharmacy/partials/cart.html",
            {"cart": cart, "tenant": _tenant(request), "errors": form.errors},
            status=400,
        )
    cart["discount_type"] = form.cleaned_data["discount_type"]
    cart["discount_value"] = str(form.cleaned_data.get("discount_value") or 0)
    try:
        sale = checkout(
            tenant=_tenant(request),
            cashier=request.user,
            cart=cart,
            customer_phone=form.cleaned_data["customer_phone"],
            paid_amount=form.cleaned_data["paid_amount"],
            payment_method=form.cleaned_data["payment_method"],
            payment_reference=form.cleaned_data["payment_reference"],
        )
    except ValidationError as exc:
        return render(
            request,
            "pharmacy/partials/cart.html",
            {
                "cart": cart,
                "tenant": _tenant(request),
                "errors": exc.messages,
            },
            status=400,
        )
    clear_cart(_tenant(request), _session_key(request))
    return render(
        request,
        "pharmacy/partials/checkout_success.html",
        {"sale": sale, "tenant": _tenant(request)},
    )


@login_required
@tenant_role_required()
def receipt(request: HttpRequest, sale_id: str) -> HttpResponse:
    """Render a printer-friendly thermal receipt scoped to the current tenant."""
    sale = get_object_or_404(
        Sale.objects.prefetch_related("items__medicine", "items__batch", "customer"),
        tenant=_tenant(request),
        pk=sale_id,
    )
    return render(request, "pharmacy/receipt.html", {"sale": sale})


@login_required
@tenant_role_required()
@require_POST
def due_collect(request: HttpRequest) -> HttpResponse:
    """Collect a customer due partially or in full."""
    form = DueCollectionForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("Enter a valid customer and collection amount.")
    try:
        entry = collect_due(
            tenant=_tenant(request),
            customer_id=form.cleaned_data["customer_id"],
            amount=form.cleaned_data["amount"],
            payment_method=form.cleaned_data["payment_method"],
            reference=form.cleaned_data["reference"],
        )
    except ValidationError as exc:
        return HttpResponseBadRequest("; ".join(exc.messages))
    return render(request, "pharmacy/partials/due_collected.html", {"entry": entry})


@login_required
@tenant_role_required()
def customer_due(request: HttpRequest, phone: str) -> HttpResponse:
    """Return the current ledger balance for a phone number."""
    normalized = "".join(char for char in phone if char.isdigit() or char == "+")
    customer = Customer.objects.filter(
        tenant=_tenant(request), phone_normalized=normalized
    ).first()
    if customer is None:
        return HttpResponseNotFound("Customer not found.")
    entries = DueLedger.objects.filter(tenant=_tenant(request), customer=customer)
    charges = sum(
        (entry.amount for entry in entries if entry.entry_type == DueLedger.EntryType.CHARGE),
        Decimal("0"),
    )
    payments = sum(
        (entry.amount for entry in entries if entry.entry_type == DueLedger.EntryType.PAYMENT),
        Decimal("0"),
    )
    return render(
        request,
        "pharmacy/partials/customer_due.html",
        {"customer": customer, "balance": charges - payments},
    )
