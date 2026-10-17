import uuid
from decimal import Decimal
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify

from core.models import Tenant, SubscriptionPlan, TenantSubscription, StaffProfile, PlatformSetting
from core.decorators import super_admin_required
from core.saas_services import (
    ensure_default_subscription_plans,
    ensure_tenant_subscription,
    get_platform_metrics,
)


@super_admin_required
def saas_admin_dashboard(request):
    """
    SaaS Super Admin Platform Dashboard.
    Provides complete oversight over all pharmacy subscribers, MRR, subscriptions, and system health.
    """
    ensure_default_subscription_plans()
    metrics = get_platform_metrics()

    # Search & Filter
    search_q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    plan_filter = request.GET.get("plan", "").strip()

    tenants_qs = Tenant.objects.all().select_related("subscription", "subscription__plan").order_by("-created_on")

    if search_q:
        tenants_qs = tenants_qs.filter(
            name__icontains=search_q
        ) | tenants_qs.filter(
            slug__icontains=search_q
        ) | tenants_qs.filter(
            phone__icontains=search_q
        )

    if status_filter == "active":
        tenants_qs = tenants_qs.filter(is_active=True, subscription__status="active")
    elif status_filter == "trial":
        tenants_qs = tenants_qs.filter(is_active=True, subscription__status="trial")
    elif status_filter == "suspended":
        tenants_qs = tenants_qs.filter(is_active=False)

    if plan_filter:
        tenants_qs = tenants_qs.filter(subscription__plan__tier=plan_filter)

    plans = SubscriptionPlan.objects.all().order_by("monthly_price_bdt")

    context = {
        "metrics": metrics,
        "tenants": tenants_qs,
        "plans": plans,
        "search_q": search_q,
        "status_filter": status_filter,
        "plan_filter": plan_filter,
        "now_date": timezone.now().date(),
    }
    return render(request, "saas_admin/dashboard.html", context)


@super_admin_required
@require_POST
def saas_tenant_create(request):
    """
    Onboards a new pharmacy tenant onto the SaaS platform.
    Automatically provisions Tenant, Subdomain Slug, and TenantSubscription.
    """
    name = request.POST.get("name", "").strip()
    name_bn = request.POST.get("name_bn", "").strip()
    phone = request.POST.get("phone", "").strip()
    email = request.POST.get("email", "").strip()
    address = request.POST.get("address", "").strip()
    raw_slug = request.POST.get("slug", "").strip()
    plan_tier = request.POST.get("plan_tier", "pro").strip()
    duration_days = int(request.POST.get("duration_days", "30"))

    if not name or not phone:
        messages.error(request, "ফার্মেসির নাম ও মোবাইল নম্বর দেওয়া বাধ্যতামূলক।")
        return redirect("saas_admin:dashboard")

    # Generate unique slug
    base_slug = slugify(raw_slug or name) or "pharmacy"
    unique_slug = base_slug
    counter = 1
    while Tenant.objects.filter(slug=unique_slug).exists():
        unique_slug = f"{base_slug}-{counter}"
        counter += 1

    # Create Tenant
    tenant = Tenant.objects.create(
        name=name,
        name_bn=name_bn or name,
        slug=unique_slug,
        phone=phone,
        email=email,
        address=address,
        is_active=True,
    )

    # Attach Subscription Plan
    plan = SubscriptionPlan.objects.filter(tier=plan_tier).first()
    if not plan:
        ensure_default_subscription_plans()
        plan = SubscriptionPlan.objects.filter(tier=plan_tier).first() or SubscriptionPlan.objects.first()

    status = "trial" if duration_days <= 30 else "active"
    TenantSubscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=status,
        start_date=timezone.now().date(),
        expires_at=timezone.now().date() + timedelta(days=duration_days),
        sms_balance=plan.sms_bundle_included if plan else 200,
        auto_renew=True,
    )

    # Optionally create pharmacy owner user account
    owner_username = request.POST.get("owner_username", "").strip()
    owner_password = request.POST.get("owner_password", "").strip()
    if owner_username and owner_password:
        if not User.objects.filter(username=owner_username).exists():
            user = User.objects.create_user(
                username=owner_username,
                password=owner_password,
                email=email,
                first_name=name,
            )
            StaffProfile.objects.create(
                user=user,
                tenant=tenant,
                role="owner",
                phone=phone,
                is_active=True,
            )

    messages.success(request, f"সফলভাবে নতুন ফার্মাসি '{tenant.name}' তৈরি ও সাবস্ক্রিপশন চালু হয়েছে!")
    return redirect("saas_admin:dashboard")


@super_admin_required
@require_POST
def saas_tenant_update_status(request, tenant_id):
    """
    Handles fast actions on a tenant: Activate/Suspend, Extend Validity, Change Plan.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)
    action = request.POST.get("action", "")

    sub = ensure_tenant_subscription(tenant)

    if action == "toggle_active":
        tenant.is_active = not tenant.is_active
        tenant.save()
        messages.success(request, f"ফার্মাসি স্ট্যাটাস {'সক্রিয়' if tenant.is_active else 'স্থগিত'} করা হয়েছে।")

    elif action == "extend_30_days":
        current_exp = max(sub.expires_at, timezone.now().date())
        sub.expires_at = current_exp + timedelta(days=30)
        sub.status = "active"
        sub.save()
        messages.success(request, f"'{tenant.name}'-এর মেয়াদ ৩০ দিন বৃদ্ধি করা হয়েছে (মেয়াদ: {sub.expires_at})।")

    elif action == "extend_365_days":
        current_exp = max(sub.expires_at, timezone.now().date())
        sub.expires_at = current_exp + timedelta(days=365)
        sub.status = "active"
        sub.save()
        messages.success(request, f"'{tenant.name}'-এর মেয়াদ ১ বছর বৃদ্ধি করা হয়েছে (মেয়াদ: {sub.expires_at})।")

    elif action == "change_plan":
        plan_id = request.POST.get("plan_id")
        plan = SubscriptionPlan.objects.filter(id=plan_id).first()
        if plan:
            sub.plan = plan
            sub.save()
            messages.success(request, f"সাবস্ক্রিপশন প্ল্যান পরিবর্তন করে '{plan.name}' করা হয়েছে।")

    return redirect("saas_admin:dashboard")


@super_admin_required
@require_POST
def saas_plan_save(request):
    """
    Creates or updates a SaaS subscription plan's pricing and quotas.
    """
    plan_id = request.POST.get("plan_id")
    monthly_price = Decimal(request.POST.get("monthly_price", "999"))
    yearly_price = Decimal(request.POST.get("yearly_price", "9990"))
    sms_quota = int(request.POST.get("sms_quota", "200"))

    if plan_id:
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        plan.monthly_price_bdt = monthly_price
        plan.yearly_price_bdt = yearly_price
        plan.sms_bundle_included = sms_quota
        plan.save()
        messages.success(request, f"'{plan.name}' প্ল্যানের প্রাইসিং আপডেট হয়েছে।")

    return redirect("saas_admin:dashboard")


@super_admin_required
def saas_tenant_detail(request, tenant_id):
    """
    Comprehensive drill-down view of a single tenant.
    """
    tenant = get_object_or_404(Tenant, id=tenant_id)
    sub = ensure_tenant_subscription(tenant)
    staff_members = StaffProfile.objects.filter(tenant=tenant).select_related("user")
    plans = SubscriptionPlan.objects.all().order_by("monthly_price_bdt")

    context = {
        "tenant": tenant,
        "subscription": sub,
        "staff_members": staff_members,
        "plans": plans,
        "now_date": timezone.now().date(),
    }
    return render(request, "saas_admin/tenant_detail.html", context)


@super_admin_required
@require_POST
def saas_platform_branding_save(request):
    """
    SaaS Super Admin: Update platform logo, branding, title, and contact details.
    Accepts uploaded file or direct logo URL, or clears custom logo to restore default.
    """
    settings_obj = PlatformSetting.get_settings()
    
    platform_name = request.POST.get("platform_name", "").strip()
    platform_tagline = request.POST.get("platform_tagline", "").strip()
    support_phone = request.POST.get("support_phone", "").strip()
    support_email = request.POST.get("support_email", "").strip()
    logo_url = request.POST.get("logo_url", "").strip()
    clear_logo = request.POST.get("clear_logo") == "1"

    if platform_name:
        settings_obj.platform_name = platform_name
    if platform_tagline:
        settings_obj.platform_tagline = platform_tagline
    if support_phone:
        settings_obj.support_phone = support_phone
    if support_email:
        settings_obj.support_email = support_email

    if clear_logo:
        if settings_obj.logo:
            try:
                settings_obj.logo.delete(save=False)
            except Exception:
                pass
        settings_obj.logo = None
        settings_obj.logo_url = ""
    elif "logo" in request.FILES:
        logo_file = request.FILES["logo"]
        settings_obj.logo = logo_file
        settings_obj.logo_url = ""
    elif logo_url:
        settings_obj.logo_url = logo_url

    settings_obj.save()
    messages.success(request, "প্ল্যাটফর্ম লোগো ও ব্র্যান্ডিং সেটিংস সফলভাবে আপডেট করা হয়েছে।")
    return redirect("saas_admin:dashboard")

