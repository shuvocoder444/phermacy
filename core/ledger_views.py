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
    """ডিফল্ট ফার্মেসি আয় ও ব্যয়ের ক্যাটাগরি নিশ্চিত করে।"""
    global _LEDGER_SEEDED
    if _LEDGER_SEEDED:
        return
    if LedgerCategory.objects.filter(is_system_default=True).exists():
        _LEDGER_SEEDED = True
        return
    _LEDGER_SEEDED = True
    default_expenses = [
        "দোকান ভাড়া",
        "কর্মচারীর বেতন ও মজুরি",
        "বিদ্যুৎ ও ইউটিলিটি বিল",
        "ওষুধ কোম্পানি / সাপ্লায়ার পেমেন্ট",
        "দৈনিক চা-নাস্তা ও আপ্যায়ন",
        "পলিথিন ও প্যাকেজিং খরচ",
        "ড্রাগ ও ট্রেড লাইসেন্স নবায়ন",
        "ইন্টারনেট ও সফটওয়্যার বিল",
        "দোকান মেরামত ও পরিচ্ছন্নতা",
        "যাতায়াত ও ডেলিভারি খরচ",
        "মেয়াদোত্তীর্ণ ওষুধের ক্ষতি",
        "অন্যান্য খরচ",
    ]
    for bn in default_expenses:
        LedgerCategory.objects.get_or_create(
            name=bn,
            category_type="EXPENSE",
            is_system_default=True,
            defaults={"name_bn": bn, "is_active": True}
        )

    default_incomes = [
        "দৈনিক ওষুধ বিক্রয়",
        "বকেয়া আদায় (বাকি খাতা)",
        "কোম্পানি রিটার্ন রিফান্ড",
        "ডেলিভারি ও সার্ভিস চার্জ",
        "মালিকের মূলধন বিনিয়োগ",
        "অন্যান্য আয়",
    ]
    for bn in default_incomes:
        LedgerCategory.objects.get_or_create(
            name=bn,
            category_type="INCOME",
            is_system_default=True,
            defaults={"name_bn": bn, "is_active": True}
        )


@tenant_user_required
def ledger_dashboard_view(request):
    """
    আয় ও ব্যয় লেজার খাতা ড্যাশবোর্ড (সম্পূর্ণ বাংলায় ও টেন্যান্ট আইসোলেশন সহ)।
    """
    ensure_default_ledger_categories()
    tenant = getattr(request, "tenant", None)
    
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    base_qs = IncomeExpenseEntry.objects.all()
    if tenant:
        base_qs = base_qs.filter(tenant=tenant)

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

    entries = base_qs.select_related("category", "recorded_by").all().order_by("-entry_date", "-created_at")[:60]
    
    # টেন্যান্টের নিজস্ব ক্যাটাগরি এবং সিস্টেম ডিফল্ট ক্যাটাগরি
    cat_filter = Q(tenant__isnull=True)
    if tenant:
        cat_filter |= Q(tenant=tenant)
    categories = LedgerCategory.objects.filter(cat_filter, is_active=True).order_by("category_type", "name")

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
    দ্রুত আয় বা ব্যয় এন্ট্রি যোগ করার ব্যাকএন্ড।
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

    entries = base_qs.select_related("category", "recorded_by").all().order_by("-entry_date", "-created_at")[:60]
    
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
    লেজার এন্ট্রি মুছে ফেলার ব্যাকএন্ড।
    """
    tenant = getattr(request, "tenant", None)
    if tenant and not request.user.is_superuser:
        entry = get_object_or_404(IncomeExpenseEntry, id=entry_id, tenant=tenant)
    else:
        entry = get_object_or_404(IncomeExpenseEntry, id=entry_id)
    entry.delete()

    today = timezone.now().date()
    base_qs = IncomeExpenseEntry.objects.all()
    if tenant:
        base_qs = base_qs.filter(tenant=tenant)

    entries = base_qs.select_related("category", "recorded_by").all().order_by("-entry_date", "-created_at")[:60]
    
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
def ledger_create_category_view(request):
    """
    টেন্যান্টের নিজের কাস্টম আয় বা ব্যয়ের ক্যাটাগরি তৈরি করার অপশন।
    """
    tenant = getattr(request, "tenant", None)
    name = request.POST.get("category_name", "").strip()
    cat_type = request.POST.get("category_type", "EXPENSE")

    if not name:
        return JsonResponse({"status": "error", "message": "ক্যাটাগরির নাম দেওয়া আবশ্যক।"}, status=400)

    # Check if duplicate for this tenant
    existing = LedgerCategory.objects.filter(
        Q(tenant=tenant) | Q(is_system_default=True),
        name__iexact=name,
        category_type=cat_type
    ).first()
    if existing:
        return JsonResponse({"status": "error", "message": "এই নামের ক্যাটাগরি ইতিমধ্যেই বিদ্যমান রয়েছে।"}, status=400)

    category = LedgerCategory.objects.create(
        tenant=tenant,
        name=name,
        name_bn=name,
        category_type=cat_type,
        is_system_default=False,
        is_active=True
    )

    return JsonResponse({
        "status": "success",
        "message": f"'{name}' ক্যাটাগরি সফলভাবে তৈরি হয়েছে!",
        "category": {
            "id": str(category.id),
            "name": category.name,
            "type": category.category_type,
        }
    })


@tenant_user_required
@require_POST
def ledger_delete_category_view(request, category_id):
    """
    টেন্যান্টের নিজস্ব কাস্টম ক্যাটাগরি মুছে ফেলার অপশন।
    """
    tenant = getattr(request, "tenant", None)
    cat = get_object_or_404(LedgerCategory, id=category_id, tenant=tenant)
    if cat.is_system_default:
        return JsonResponse({"status": "error", "message": "সিস্টেম ডিফল্ট ক্যাটাগরি মুছে ফেলা যাবে না।"}, status=403)

    cat_name = cat.name
    cat.delete()
    return JsonResponse({
        "status": "success",
        "message": f"'{cat_name}' ক্যাটাগরি সফলভাবে মুছে ফেলা হয়েছে!"
    })
