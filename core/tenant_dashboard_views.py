from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages
from django.utils import timezone

from core.models import Tenant, SubscriptionPlan, TenantSubscription
from core.decorators import tenant_user_required
from core.saas_services import (
    ensure_tenant_subscription,
    ensure_default_subscription_plans,
    get_tenant_metrics,
)


@tenant_user_required
def tenant_dashboard_view(request):
    """
    Main Tenant / Pharmacy Subscriber Dashboard.
    Provides pharmacy owners and pharmacists with real-time operational metrics,
    financial performance, inventory health, and subscription status.
    Protected: Only authenticated users belonging to an active pharmacy can access.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant and hasattr(request.user, "staff_profile") and request.user.staff_profile:
        tenant = request.user.staff_profile.tenant
    if not tenant and request.user.is_superuser:
        tenant = Tenant.objects.first()

    if not tenant:
        messages.error(request, "কোনো ফার্মেসি প্রোফাইল পাওয়া যায়নি।")
        return redirect("login")

    ensure_default_subscription_plans()
    metrics = get_tenant_metrics(tenant)
    available_plans = SubscriptionPlan.objects.filter(is_active=True).order_by("monthly_price_bdt")

    context = {
        **metrics,
        "available_plans": available_plans,
        "now_date": timezone.now().date(),
        "tenant": tenant,
    }
    return render(request, "tenant/dashboard.html", context)


@tenant_user_required
@require_POST
def tenant_settings_update(request):
    """
    Updates the pharmacy store profile, licensing, and receipt defaults.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant and hasattr(request.user, "staff_profile") and request.user.staff_profile:
        tenant = request.user.staff_profile.tenant
    if not tenant and request.user.is_superuser:
        tenant = Tenant.objects.first()

    if not tenant:
        messages.error(request, "ফার্মেসি পাওয়া যায়নি।")
        return redirect("login")

    tenant.name = request.POST.get("name", tenant.name).strip()
    tenant.name_bn = request.POST.get("name_bn", tenant.name_bn).strip()
    tenant.phone = request.POST.get("phone", tenant.phone).strip()
    tenant.email = request.POST.get("email", tenant.email).strip()
    tenant.address = request.POST.get("address", tenant.address).strip()
    tenant.drug_license_number = request.POST.get("drug_license_number", tenant.drug_license_number).strip()
    tenant.trade_license_number = request.POST.get("trade_license_number", tenant.trade_license_number).strip()
    tenant.vat_reg_number = request.POST.get("vat_reg_number", tenant.vat_reg_number).strip()
    
    try:
        tenant.default_vat_rate = Decimal(request.POST.get("default_vat_rate", str(tenant.default_vat_rate)))
        tenant.low_stock_threshold = int(request.POST.get("low_stock_threshold", str(tenant.low_stock_threshold)))
    except Exception:
        pass

    tenant.save()
    messages.success(request, "ফার্মেসির প্রোফাইল ও সেটিংস সফলভাবে সংরক্ষিত হয়েছে!")
    return redirect("tenant_dashboard:dashboard")

