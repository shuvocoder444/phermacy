from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.db.models import Sum, Q

from core.models import LedgerCategory, IncomeExpenseEntry
from core.decorators import tenant_user_required


_LEDGER_SEEDED = False

def ensure_default_ledger_categories():
    """Initializes standard retail pharmacy income and expense categories."""
    global _LEDGER_SEEDED
    if _LEDGER_SEEDED:
        return
    if LedgerCategory.objects.exists():
        _LEDGER_SEEDED = True
        return
    _LEDGER_SEEDED = True
    default_expenses = [
        ("Shop Rent", "দোকান ভাড়া"),
        ("Staff Salary & Daily Wage", "কর্মচারীর বেতন ও মজুরি"),
        ("Electricity & Utility Bill", "বিদ্যুৎ ও ইউটিলিটি বিল"),
        ("Pharmaceutical Supplier Payment", "ঔষধ কোম্পানি / সাপ্লায়ার পেমেন্ট"),
        ("Daily Snacks & Refreshment", "দৈনিক চা-নাস্তা ও আপ্যায়ন"),
        ("Packaging & Polythene Bags", "পলিথিন ও প্যাকেজিং খরচ"),
        ("Trade & Drug License Renew", "ড্রাগ ও ট্রেড লাইসেন্স নবায়ন"),
        ("Software & Internet Bill", "ইন্টারনেট ও সফটওয়্যার বিল"),
        ("Shop Maintenance & Cleaning", "দোকান মেরামত ও পরিষ্কার পরিচ্ছন্নতা"),
        ("Transportation & Delivery", "যাতায়াত ও ডেলিভারি খরচ"),
        ("Damaged / Expired Drug Loss", "মেয়াদোত্তীর্ণ ঔষধের ক্ষতি"),
        ("Miscellaneous Expense", "অন্যান্য খরচ"),
    ]
    for name, bn in default_expenses:
        LedgerCategory.objects.get_or_create(
            name=name,
            category_type="EXPENSE",
            defaults={"name_bn": bn, "is_system_default": True}
        )

    default_incomes = [
        ("Daily OTC & Prescription Sales", "দৈনিক ঔষধ বিক্রয়"),
        ("Customer Due Collection (Baki)", "বকেয়া আদায় (বাকি খাতা)"),
        ("Supplier Return Refund", "কোম্পানি রিটার্ন রিফান্ড"),
        ("Delivery & Service Charge", "ডেলিভারি ও সার্ভিস চার্জ"),
        ("Owner Capital Investment", "মালিকের মূলধন বিনিয়োগ"),
        ("Other Income", "অন্যান্য আয়"),
    ]
    for name, bn in default_incomes:
        LedgerCategory.objects.get_or_create(
            name=name,
            category_type="INCOME",
            defaults={"name_bn": bn, "is_system_default": True}
        )


@tenant_user_required
def ledger_dashboard_view(request):
    """
    Main Income & Expense Cash Book Ledger dashboard with tenant isolation.
    """
    ensure_default_ledger_categories()
    tenant = getattr(request, "tenant", None)
    
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    base_qs = IncomeExpenseEntry.objects.all()
    if tenant:
        base_qs = base_qs.filter(tenant=tenant)

    # Consolidated single query for Today's and Month's financial totals
    metrics = base_qs.aggregate(
        today_income=Sum("amount", filter=Q(entry_date=today, entry_type="INCOME")),
        today_expense=Sum("amount", filter=Q(entry_date=today, entry_type="EXPENSE")),
        month_income=Sum("amount", filter=Q(entry_date__gte=start_of_month, entry_type="INCOME")),
        month_expense=Sum("amount", filter=Q(entry_date__gte=start_of_month, entry_type="EXPENSE")),
    )
    today_income = metrics["today_income"] or Decimal("0.00")
    today_expense = metrics["today_expense"] or Decimal("0.00")
    today_net = today_income - today_expense

    month_income = metrics["month_income"] or Decimal("0.00")
    month_expense = metrics["month_expense"] or Decimal("0.00")
    month_net = month_income - month_expense

    entries = base_qs.select_related("category", "recorded_by").all()[:50]
    categories = LedgerCategory.objects.filter(is_active=True)

    context = {
        "tenant": tenant,
        "entries": entries,
        "categories": categories,
        "today_income": today_income,
        "today_expense": today_expense,
        "today_net": today_net,
        "month_income": month_income,
        "month_expense": month_expense,
        "month_net": month_net,
        "today": today,
    }
    return render(request, "ledger/dashboard.html", context)


@tenant_user_required
@require_POST
def ledger_add_entry_htmx(request):
    """
    HTMX endpoint to quickly add an income or expense entry with tenant scoping.
    """
    tenant = getattr(request, "tenant", None)
    entry_type = request.POST.get("entry_type", "EXPENSE")
    category_id = request.POST.get("category_id")
    title = request.POST.get("title", "").strip()
    amount = Decimal(request.POST.get("amount", "0.00") or "0.00")
    payment_method = request.POST.get("payment_method", "CASH")
    recipient_or_payer = request.POST.get("recipient_or_payer", "").strip()
    voucher_number = request.POST.get("voucher_number", "").strip()
    entry_date = request.POST.get("entry_date") or timezone.now().date()
    notes = request.POST.get("notes", "").strip()

    if not title or amount <= 0 or not category_id:
        return HttpResponse("<div class='text-rose-500 text-xs p-2'>সব তথ্য সঠিকভাবে পূরণ করুন।</div>", status=400)

    category = get_object_or_404(LedgerCategory, id=category_id)
    recorded_by = request.user if request.user.is_authenticated else None
    if not recorded_by:
        from django.contrib.auth.models import User
        recorded_by, _ = User.objects.get_or_create(username="pharmacist_admin")

    entry = IncomeExpenseEntry.objects.create(
        tenant=tenant,
        entry_type=entry_type,
        category=category,
        title=title,
        amount=amount,
        payment_method=payment_method,
        recipient_or_payer=recipient_or_payer,
        voucher_number=voucher_number,
        entry_date=entry_date,
        recorded_by=recorded_by,
        notes=notes,
    )

    today = timezone.now().date()
    base_qs = IncomeExpenseEntry.objects.all()
    if tenant:
        base_qs = base_qs.filter(tenant=tenant)

    entries = base_qs.select_related("category", "recorded_by").all()[:50]
    
    today_income = base_qs.filter(entry_date=today, entry_type="INCOME").aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    today_expense = base_qs.filter(entry_date=today, entry_type="EXPENSE").aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    today_net = today_income - today_expense

    context = {
        "tenant": tenant,
        "entries": entries,
        "today_income": today_income,
        "today_expense": today_expense,
        "today_net": today_net,
    }
    return render(request, "ledger/partials/ledger_table.html", context)


@tenant_user_required
@require_POST
def ledger_delete_entry_htmx(request, entry_id):
    """
    Deletes a ledger entry ensuring tenant boundary.
    """
    tenant = getattr(request, "tenant", None)
    if tenant and not request.user.is_superuser:
        entry = get_object_or_404(IncomeExpenseEntry, id=entry_id, tenant=tenant)
    else:
        entry = get_object_or_404(IncomeExpenseEntry, id=entry_id)
    entry.delete()

    today = timezone.now().date()
    entries = IncomeExpenseEntry.objects.select_related("category", "recorded_by").all()[:50]
    
    today_income = IncomeExpenseEntry.objects.filter(entry_date=today, entry_type="INCOME").aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    today_expense = IncomeExpenseEntry.objects.filter(entry_date=today, entry_type="EXPENSE").aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    today_net = today_income - today_expense

    context = {
        "entries": entries,
        "today_income": today_income,
        "today_expense": today_expense,
        "today_net": today_net,
    }
    return render(request, "ledger/partials/ledger_table.html", context)
