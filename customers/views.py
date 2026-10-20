from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.models import IncomeExpenseEntry, LedgerCategory
from core.decorators import tenant_user_required

from .models import Customer, DueLedger


def get_or_create_due_collection_category():
    cat, _ = LedgerCategory.objects.get_or_create(
        name="কাস্টমার বাকি আদায় (Due Collection)",
        defaults={
            "type": "INCOME",
            "code": "CUST-DUE-INCOME",
            "is_system_default": True
        }
    )
    return cat

@tenant_user_required
def customer_dashboard(request):
    """
    Main Customer & Baki Khata management dashboard.
    """
    query = request.GET.get("q", "").strip()
    filter_due = request.GET.get("filter", "all")

    tenant = getattr(request, "tenant", None)
    customers = Customer.objects.filter(is_active=True)
    if tenant:
        customers = customers.filter(tenant=tenant)

    if query:
        customers = customers.filter(
            Q(name__icontains=query) |
            Q(phone__icontains=query) |
            Q(name_bn__icontains=query)
        )

    if filter_due == "due_only":
        customers = customers.filter(current_due__gt=0)

    customers = customers.order_by("-current_due", "name")

    base_customers = Customer.objects.filter(is_active=True)
    if tenant:
        base_customers = base_customers.filter(tenant=tenant)
    cust_agg = base_customers.aggregate(
        total_customers=Count("id"),
        total_due=Sum("current_due")
    )
    total_customers = cust_agg["total_customers"] or 0
    total_due = cust_agg["total_due"] or Decimal("0.00")
    
    # Due collected today
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    due_qs = DueLedger.objects.filter(
        created_at__gte=today_start,
        transaction_type__startswith="PAYMENT_"
    )
    if tenant:
        due_qs = due_qs.filter(tenant=tenant)
    collected_today = due_qs.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")

    context = {
        "customers": customers,
        "total_customers": total_customers,
        "total_due": total_due,
        "collected_today": collected_today,
        "query": query,
        "filter_due": filter_due,
    }

    if request.headers.get("HX-Request"):
        return render(request, "customers/partials/customer_table.html", context)

    return render(request, "customers/dashboard.html", context)

@tenant_user_required
@require_POST
def add_customer(request):
    """
    Creates a new customer.
    """
    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()
    name_bn = request.POST.get("name_bn", "").strip()
    address = request.POST.get("address", "").strip()
    credit_limit = request.POST.get("credit_limit", "5000.00").strip() or "5000.00"
    opening_due = request.POST.get("opening_due", "0.00").strip() or "0.00"

    if not name or not phone:
        return HttpResponse("<div class='p-3 bg-rose-50 text-rose-700 text-xs font-bold rounded'>নাম এবং মোবাইল নম্বর আবশ্যক!</div>", status=400)

    tenant = getattr(request, "tenant", None)
    try:
        cust, created = Customer.objects.get_or_create(
            phone=phone,
            tenant=tenant,
            defaults={
                "name": name,
                "name_bn": name_bn,
                "address": address,
                "credit_limit": Decimal(credit_limit),
                "current_due": Decimal(opening_due),
            }
        )
        if not created:
            cust.name = name
            if name_bn:
                cust.name_bn = name_bn
            if address:
                cust.address = address
            cust.save()
        elif Decimal(opening_due) > 0:
            DueLedger.objects.create(
                tenant=tenant,
                customer=cust,
                transaction_type="INVOICE_DUE",
                amount=Decimal(opening_due),
                balance_before=Decimal("0.00"),
                balance_after=Decimal(opening_due),
                notes="প্রারম্ভিক বাকি (Opening Due Balance)"
            )
    except Exception as e:
        return HttpResponse(f"<div class='p-3 bg-rose-50 text-rose-700 text-xs font-bold rounded'>ত্রুটি: {e!s}</div>", status=400)

    return redirect("customers:dashboard")

@tenant_user_required
@require_POST
def collect_due(request, customer_id):
    """
    Collects due payment from a customer, updates Baki balance, creates ledger entry,
    and logs income in Cash Book.
    """
    tenant = getattr(request, "tenant", None)
    cust_qs = Customer.objects.filter(id=customer_id)
    if tenant:
        cust_qs = cust_qs.filter(tenant=tenant)
    customer = get_object_or_404(cust_qs)
    
    amount_str = request.POST.get("amount", "0").strip()
    payment_method = request.POST.get("payment_method", "CASH").upper()
    trx_id = request.POST.get("trx_id", "").strip()
    notes = request.POST.get("notes", "").strip()
    collected_by = request.POST.get("collected_by", "Counter Staff").strip()

    try:
        amount = Decimal(amount_str)
    except Exception:
        amount = Decimal("0.00")

    if amount <= 0:
        return HttpResponse("<div class='p-2 bg-rose-50 text-rose-700 text-xs font-bold rounded'>সঠিক টাকার পরিমাণ দিন!</div>", status=400)

    # Calculate balances
    bal_before = customer.current_due
    bal_after = max(Decimal("0.00"), bal_before - amount)
    customer.current_due = bal_after
    customer.save(update_fields=["current_due", "updated_at"])

    # Determine ledger type
    trx_type_map = {
        "CASH": "PAYMENT_CASH",
        "BKASH": "PAYMENT_BKASH",
        "NAGAD": "PAYMENT_NAGAD",
        "ROCKET": "PAYMENT_ROCKET",
        "BANK": "PAYMENT_BANK",
    }
    trx_type = trx_type_map.get(payment_method, "PAYMENT_CASH")

    # Create Due Ledger Entry
    ledger_entry = DueLedger.objects.create(
        tenant=tenant,
        customer=customer,
        transaction_type=trx_type,
        amount=amount,
        balance_before=bal_before,
        balance_after=bal_after,
        gateway_trx_id=trx_id if trx_id else None,
        collected_by=collected_by,
        notes=notes or f"বাকি আদায় ({payment_method})"
    )

    # Sync to Cash Book / Income Ledger
    due_category = get_or_create_due_collection_category()
    IncomeExpenseEntry.objects.create(
        tenant=tenant,
        type="INCOME",
        category=due_category,
        amount=amount,
        payment_method=payment_method if payment_method in ["CASH", "BKASH", "NAGAD", "ROCKET", "BANK"] else "CASH",
        reference_no=f"DUE-COLLECT-{ledger_entry.id.hex[:6].upper()}",
        note=f"বাকি আদায়: {customer.name} ({customer.phone}) | পূর্বের বাকি: ৳{bal_before} | বর্তমান বাকি: ৳{bal_after}",
        collected_by=collected_by
    )

    if request.headers.get("HX-Request"):
        return HttpResponse(f"""
        <div class="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center justify-between">
            <div>
                <p class="font-bold">৳{amount} টাকা সফলভাবে আদায় হয়েছে!</p>
                <p class="text-[11px] text-emerald-600">বর্তমান বাকি: ৳{bal_after}</p>
            </div>
            <button onclick="window.location.reload()" class="px-2 py-1 bg-emerald-600 text-white rounded font-bold hover:bg-emerald-700">রিলোড</button>
        </div>
        """)

    return redirect("customers:statement", customer_id=customer.id)

@tenant_user_required
def customer_statement(request, customer_id):
    """
    Detailed statement / transaction history of a specific customer.
    """
    tenant = getattr(request, "tenant", None)
    cust_qs = Customer.objects.filter(id=customer_id)
    if tenant:
        cust_qs = cust_qs.filter(tenant=tenant)
    customer = get_object_or_404(cust_qs)
    ledger_entries = customer.ledger_entries.all().order_by("-created_at")

    context = {
        "customer": customer,
        "ledger_entries": ledger_entries,
    }
    return render(request, "customers/statement.html", context)

@tenant_user_required
@require_GET
def search_customers_api(request):
    """
    Fast JSON API to search customers for POS screen dropdown/auto-fill.
    """
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})

    tenant = getattr(request, "tenant", None)
    customers = Customer.objects.filter(
        Q(phone__icontains=query) | Q(name__icontains=query) | Q(name_bn__icontains=query),
        is_active=True
    )
    if tenant:
        customers = customers.filter(tenant=tenant)
    customers = customers[:10]

    results = []
    for c in customers:
        results.append({
            "id": str(c.id),
            "name": c.name,
            "name_bn": c.name_bn or "",
            "phone": c.phone,
            "current_due": float(c.current_due),
            "credit_limit": float(c.credit_limit),
            "address": c.address or ""
        })

    return JsonResponse({"results": results})
