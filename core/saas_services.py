from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.contrib.auth.models import User

from core.models import Tenant, SubscriptionPlan, TenantSubscription, StaffProfile, IncomeExpenseEntry
from pos.models import Invoice
from inventory.models import BrandDrug, DrugBatch
from customers.models import Customer, DueLedger


def ensure_default_subscription_plans() -> list[SubscriptionPlan]:
    """
    Seeds and ensures the 3 standard SaaS subscription plans exist.
    """
    plans_config = [
        {
            "name": "Starter (একক কাউন্টার)",
            "tier": "starter",
            "monthly_price_bdt": Decimal("999.00"),
            "yearly_price_bdt": Decimal("9990.00"),
            "max_branches": 1,
            "max_users": 2,
            "sms_bundle_included": 200,
            "features": {
                "pos": True,
                "ledger": True,
                "customers": True,
                "thermal_receipt": True,
                "camera_ocr": False,
                "voice_search": False,
                "sms_alerts": True,
            },
        },
        {
            "name": "Pro (স্মার্ট পিওএস ও এআই ভিশন)",
            "tier": "pro",
            "monthly_price_bdt": Decimal("1999.00"),
            "yearly_price_bdt": Decimal("19990.00"),
            "max_branches": 3,
            "max_users": 6,
            "sms_bundle_included": 600,
            "features": {
                "pos": True,
                "ledger": True,
                "customers": True,
                "thermal_receipt": True,
                "camera_ocr": True,
                "voice_search": True,
                "sms_alerts": True,
                "priority_support": True,
            },
        },
        {
            "name": "Enterprise (মাল্টি-ব্রাঞ্চ চেইন)",
            "tier": "enterprise",
            "monthly_price_bdt": Decimal("4999.00"),
            "yearly_price_bdt": Decimal("49990.00"),
            "max_branches": 10,
            "max_users": 25,
            "sms_bundle_included": 2500,
            "features": {
                "all_features": True,
                "custom_domain": True,
                "dedicated_manager": True,
                "central_warehouse": True,
            },
        },
    ]

    created_or_found = []
    for p in plans_config:
        plan = SubscriptionPlan.objects.filter(tier=p["tier"]).first()
        if not plan:
            plan = SubscriptionPlan.objects.create(
                tier=p["tier"],
                name=p["name"],
                monthly_price_bdt=p["monthly_price_bdt"],
                yearly_price_bdt=p["yearly_price_bdt"],
                max_branches=p["max_branches"],
                max_users=p["max_users"],
                sms_bundle_included=p["sms_bundle_included"],
                features=p["features"],
                is_active=True,
            )
        created_or_found.append(plan)
    return created_or_found


def ensure_tenant_subscription(tenant: Tenant) -> TenantSubscription:
    """
    Ensures that a given pharmacy tenant has an active subscription attached.
    If none exists, provisions a 30-day Pro Trial/Active subscription.
    """
    plans = ensure_default_subscription_plans()
    pro_plan = next((p for p in plans if p.tier == "pro"), plans[0])

    sub = getattr(tenant, "subscription", None)
    if not sub:
        sub = TenantSubscription.objects.create(
            tenant=tenant,
            plan=pro_plan,
            status="active",
            start_date=timezone.now().date(),
            expires_at=timezone.now().date() + timedelta(days=365),
            sms_balance=pro_plan.sms_bundle_included,
            auto_renew=True,
        )
    return sub


def get_platform_metrics() -> dict:
    """
    Computes overarching platform-level metrics for the SaaS Super Admin.
    """
    ensure_default_subscription_plans()
    now_date = timezone.now().date()
    start_of_month = now_date.replace(day=1)

    all_tenants = Tenant.objects.all().select_related("subscription", "subscription__plan")
    total_tenants = all_tenants.count()
    active_tenants = all_tenants.filter(is_active=True).count()
    
    # Subscription status distribution
    subs = TenantSubscription.objects.select_related("plan")
    active_subs = subs.filter(status="active", expires_at__gte=now_date).count()
    trial_subs = subs.filter(status="trial", expires_at__gte=now_date).count()
    expired_subs = subs.filter(Q(status="expired") | Q(expires_at__lt=now_date)).count()

    # MRR calculation
    mrr = Decimal("0.00")
    for s in subs.filter(status__in=["active", "trial"]):
        if s.plan:
            mrr += s.plan.monthly_price_bdt
    arr = mrr * 12

    # Global POS activity across platform
    total_invoices = Invoice.objects.count()
    total_gmv = Invoice.objects.filter(status="COMPLETED").aggregate(s=Sum("total_payable"))["s"] or Decimal("0.00")
    
    month_invoices = Invoice.objects.filter(created_at__date__gte=start_of_month).count()
    month_gmv = Invoice.objects.filter(created_at__date__gte=start_of_month, status="COMPLETED").aggregate(s=Sum("total_payable"))["s"] or Decimal("0.00")

    total_staff = StaffProfile.objects.count()
    total_customers = Customer.objects.count()

    return {
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "active_subs": active_subs,
        "trial_subs": trial_subs,
        "expired_subs": expired_subs,
        "mrr": mrr,
        "arr": arr,
        "total_invoices": total_invoices,
        "total_gmv": total_gmv,
        "month_invoices": month_invoices,
        "month_gmv": month_gmv,
        "total_staff": total_staff,
        "total_customers": total_customers,
    }


def get_tenant_metrics(tenant: Tenant) -> dict:
    """
    Computes business and operational metrics for an individual Pharmacy Tenant.
    Fully optimized with conditional aggregation and tenant-scoped queries.
    """
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    # 1. Sales & Revenue (single consolidated query)
    today_invoices_qs = Invoice.objects.filter(created_at__date=today)
    month_invoices_qs = Invoice.objects.filter(created_at__date__gte=start_of_month)
    if tenant:
        today_invoices_qs = today_invoices_qs.filter(tenant=tenant)
        month_invoices_qs = month_invoices_qs.filter(tenant=tenant)

    today_agg = today_invoices_qs.aggregate(
        count=Count("id"),
        total_sales=Sum("total_payable", filter=Q(status="COMPLETED")),
        cash_sales=Sum("paid_amount", filter=Q(payment_method="CASH", status="COMPLETED")),
        mfs_sales=Sum("paid_amount", filter=Q(payment_method__in=["BKASH", "NAGAD", "ROCKET"], status="COMPLETED")),
        due_sales=Sum("due_amount", filter=Q(status="COMPLETED")),
    )
    def _quantize_money(val):
        if val is None:
            return Decimal("0.00")
        try:
            return Decimal(str(val)).quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0.00")

    today_sales = _quantize_money(today_agg["total_sales"])
    today_invoices_count = today_agg["count"] or 0
    today_cash_sales = _quantize_money(today_agg["cash_sales"])
    today_mfs_sales = _quantize_money(today_agg["mfs_sales"])
    today_due_sales = _quantize_money(today_agg["due_sales"])

    month_agg = month_invoices_qs.aggregate(
        count=Count("id"),
        total_sales=Sum("total_payable", filter=Q(status="COMPLETED")),
    )
    month_sales = _quantize_money(month_agg["total_sales"])
    month_invoices_count = month_agg["count"] or 0

    # 2. Customer Receivables / Dues
    cust_qs = Customer.objects.filter(is_active=True)
    if tenant:
        cust_qs = cust_qs.filter(tenant=tenant)
    cust_agg = cust_qs.aggregate(
        total_dues=Sum("current_due"),
        count=Count("id")
    )
    total_customer_dues = _quantize_money(cust_agg["total_dues"])
    total_customers_count = cust_agg["count"] or 0

    # 3. Monthly Operational Expenses
    exp_qs = IncomeExpenseEntry.objects.filter(
        entry_date__gte=start_of_month,
        entry_type="EXPENSE"
    )
    if tenant:
        exp_qs = exp_qs.filter(tenant=tenant)
    month_expenses = _quantize_money(exp_qs.aggregate(s=Sum("amount"))["s"])

    # Estimated Gross Profit (Sales - Expenses)
    estimated_profit = _quantize_money(max(Decimal("0.00"), month_sales - month_expenses))

    # 4. Inventory Alerts (Direct tenant batch query instead of full catalog table scan)
    low_stock_limit = tenant.low_stock_threshold or 15 if tenant else 15
    batch_qs = DrugBatch.objects.filter(current_stock__gt=0)
    if tenant:
        batch_qs = batch_qs.filter(tenant=tenant)

    low_stock_count = batch_qs.filter(current_stock__lte=low_stock_limit).count()
    low_stock_batches = list(batch_qs.filter(current_stock__lte=low_stock_limit).select_related("drug")[:10])
    low_stock_drugs = [b.drug for b in low_stock_batches]
    out_of_stock_count = 0

    # Expiring batches within 60 days
    sixty_days_future = today + timedelta(days=60)
    expiring_batches_qs = DrugBatch.objects.filter(
        expiry_date__lte=sixty_days_future,
        expiry_date__gte=today,
        current_stock__gt=0
    )
    if tenant:
        expiring_batches_qs = expiring_batches_qs.filter(tenant=tenant)

    expiring_batches = list(expiring_batches_qs.select_related("drug")[:10])
    expiring_count = expiring_batches_qs.count()

    # 5. Active Register Status
    active_register = None
    if tenant:
        from pos.models import CashRegisterSession
        active_register = CashRegisterSession.objects.filter(
            tenant=tenant,
            is_closed=False
        ).order_by("-opened_at").first()

    return {
        "today_sales": today_sales,
        "today_invoices_count": today_invoices_count,
        "today_cash_sales": today_cash_sales,
        "today_mfs_sales": today_mfs_sales,
        "today_due_sales": today_due_sales,
        "month_sales": month_sales,
        "month_invoices_count": month_invoices_count,
        "total_customer_dues": total_customer_dues,
        "total_customers_count": total_customers_count,
        "month_expenses": month_expenses,
        "estimated_profit": estimated_profit,
        "low_stock_drugs": low_stock_drugs,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "expiring_batches": expiring_batches,
        "expiring_count": expiring_count,
        "active_register": active_register,
    }
