from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q

from core.models import Tenant, SubscriptionPlan, TenantSubscription
from core.decorators import tenant_user_required
from core.saas_services import (
    ensure_tenant_subscription,
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

    subscription = ensure_tenant_subscription(tenant)
    metrics = get_tenant_metrics(tenant)
    now_date = timezone.now().date()

    from pos.models import Invoice
    recent_invoices = (
        Invoice.objects.filter(tenant=tenant)
        .select_related("customer")
        .order_by("-created_at")[:10]
    )

    context = {
        **metrics,
        "now_date": now_date,
        "subscription": subscription,
        "days_remaining": max(0, (subscription.expires_at - now_date).days),
        "is_expiring_soon": 0 <= (subscription.expires_at - now_date).days <= 7,
        "tenant": tenant,
        "recent_invoices": recent_invoices,
    }
    return render(request, "tenant/dashboard.html", context)


@tenant_user_required
def recent_pos_sales_view(request):
    """Show the tenant's complete POS invoice history, newest first."""
    tenant = getattr(request, "tenant", None)
    if not tenant and hasattr(request.user, "staff_profile") and request.user.staff_profile:
        tenant = request.user.staff_profile.tenant
    if not tenant and request.user.is_superuser:
        tenant = Tenant.objects.first()
    if not tenant:
        messages.error(request, "ফার্মেসি প্রোফাইল পাওয়া যায়নি।")
        return redirect("login")

    from pos.models import Invoice
    query = request.GET.get("q", "").strip()
    invoices = Invoice.objects.filter(tenant=tenant).select_related("customer", "cashier").order_by("-created_at")
    if query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(customer__phone__icontains=query)
            | Q(customer_name_walkin__icontains=query)
            | Q(customer_phone_walkin__icontains=query)
        )

    page_obj = Paginator(invoices, 50).get_page(request.GET.get("page"))
    return render(request, "tenant/recent_pos_sales.html", {
        "tenant": tenant,
        "invoices": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
    })


@tenant_user_required
def tenant_settings_page(request):
    tenant = getattr(request, "tenant", None)
    if not tenant and hasattr(request.user, "staff_profile") and request.user.staff_profile:
        tenant = request.user.staff_profile.tenant
    if not tenant and request.user.is_superuser:
        tenant = Tenant.objects.first()
    if not tenant:
        messages.error(request, "ফার্মেসি প্রোফাইল পাওয়া যায়নি।")
        return redirect("login")
    return render(request, "tenant/settings.html", {"tenant": tenant})


@tenant_user_required
def tenant_subscription_page(request):
    tenant = getattr(request, "tenant", None)
    if not tenant and hasattr(request.user, "staff_profile") and request.user.staff_profile:
        tenant = request.user.staff_profile.tenant
    if not tenant and request.user.is_superuser:
        tenant = Tenant.objects.first()
    if not tenant:
        messages.error(request, "ফার্মেসি প্রোফাইল পাওয়া যায়নি।")
        return redirect("login")

    subscription = ensure_tenant_subscription(tenant)
    now_date = timezone.now().date()
    context = {
        "tenant": tenant,
        "subscription": subscription,
        "days_remaining": max(0, (subscription.expires_at - now_date).days),
        "available_plans": SubscriptionPlan.objects.filter(is_active=True).order_by("monthly_price_bdt"),
    }
    return render(request, "tenant/subscription.html", context)


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

    profile = getattr(request.user, "staff_profile", None)
    if not request.user.is_superuser and (not profile or profile.role.lower() != "owner"):
        return HttpResponse("Only the pharmacy owner can update pharmacy settings.", status=403)

    def posted_text(field, current):
        return (request.POST.get(field, current) or "").strip()

    tenant.name = posted_text("name", tenant.name)
    tenant.name_bn = posted_text("name_bn", tenant.name_bn)
    tenant.phone = posted_text("phone", tenant.phone)
    tenant.email = posted_text("email", tenant.email)
    tenant.address = posted_text("address", tenant.address)
    tenant.drug_license_number = posted_text("drug_license_number", tenant.drug_license_number)
    tenant.trade_license_number = posted_text("trade_license_number", tenant.trade_license_number)
    tenant.vat_reg_number = posted_text("vat_reg_number", tenant.vat_reg_number)
    
    try:
        tenant.default_vat_rate = Decimal(request.POST.get("default_vat_rate", str(tenant.default_vat_rate)))
        tenant.low_stock_threshold = int(request.POST.get("low_stock_threshold", str(tenant.low_stock_threshold)))
    except Exception:
        pass

    uploaded_logo = request.FILES.get("logo")
    if uploaded_logo:
        try:
            from PIL import Image
            image = Image.open(uploaded_logo)
            image.verify()
            valid_logo = image.format in {"JPEG", "PNG", "WEBP"}
        except Exception:
            valid_logo = False
        if not valid_logo or uploaded_logo.size > 2 * 1024 * 1024:
            messages.error(request, "লোগো JPG/PNG/WebP হতে হবে এবং ২ MB-এর মধ্যে হতে হবে।")
            return redirect("tenant_dashboard:settings")
        uploaded_logo.seek(0)
        tenant.logo = uploaded_logo

    tenant.save()
    messages.success(request, "ফার্মেসির প্রোফাইল ও সেটিংস সফলভাবে সংরক্ষিত হয়েছে!")
    return redirect("tenant_dashboard:settings")

