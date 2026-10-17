from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_protect

from core.models import Tenant, StaffProfile


@csrf_protect
def login_view(request):
    """
    Central login handler for PharmaFlow SaaS:
    - Super Admins are routed to the SaaS Super Admin Dashboard.
    - Pharmacy Owners & Staff are strictly bound to their Tenant and routed to the Pharmacy Dashboard.
    - Suspended or inactive tenants are blocked from accessing the system.
    """
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect("saas_admin:dashboard")
        return redirect("tenant_dashboard:dashboard")

    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        if not username or not password:
            messages.error(request, "ইউজারনেম এবং পাসওয়ার্ড প্রদান করুন।")
            return render(request, "auth/login.html", {"username": username, "next": next_url})

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "আপনার অ্যাকাউন্টটি নিষ্ক্রিয় করা রয়েছে। এডমিনের সাথে যোগাযোগ করুন।")
                return render(request, "auth/login.html", {"username": username, "next": next_url})

            # Check Tenant status for non-superusers
            if not user.is_superuser:
                profile = StaffProfile.objects.filter(user=user).select_related("tenant").first()
                if not profile or not profile.tenant:
                    messages.error(request, "আপনার কোনো ফার্মেসি প্রোফাইল পাওয়া যায়নি।")
                    return render(request, "auth/login.html", {"username": username, "next": next_url})

                if not profile.tenant.is_active:
                    messages.error(request, f"আপনার ফার্মেসি '{profile.tenant.name}' স্থগিত (Suspended) রয়েছে। সাবস্ক্রিপশন রিনিউ করতে এডমিনের সাথে যোগাযোগ করুন।")
                    return render(request, "auth/login.html", {"username": username, "next": next_url})

                # Check subscription expiration
                try:
                    sub = profile.tenant.subscription
                except Exception:
                    sub = None
                if sub and not sub.is_valid:
                    messages.warning(request, f"সতর্কতা: আপনার সাবস্ক্রিপশনের মেয়াদ শেষ হয়েছে ({sub.expires_at})। অনুগ্রহ করে দ্রুত রিনিউ করুন।")

                # Lock session to this tenant
                request.session["active_tenant_id"] = str(profile.tenant.id)

            login(request, user)
            messages.success(request, f"স্বাগতম, {user.get_full_name() or user.username}!")

            if next_url:
                return redirect(next_url)

            if user.is_superuser:
                return redirect("saas_admin:dashboard")
            return redirect("tenant_dashboard:dashboard")
        else:
            messages.error(request, "ভুল ইউজারনেম অথবা পাসওয়ার্ড। অনুগ্রহ করে আবার চেষ্টা করুন।")

    return render(request, "auth/login.html", {"next": next_url})


def logout_view(request):
    """
    Logs out the user and safely clears tenant session bindings.
    """
    logout(request)
    if "active_tenant_id" in request.session:
        del request.session["active_tenant_id"]
    messages.success(request, "সফলভাবে লগআউট করা হয়েছে।")
    return redirect("login")


def switch_tenant_view(request, tenant_id):
    """
    Allows Super Admins to switch their active viewing tenant context.
    """
    if not request.user.is_superuser:
        messages.error(request, "অননুমোদিত অ্যাক্সেস।")
        return redirect("tenant_dashboard:dashboard")

    tenant = get_object_or_404(Tenant, id=tenant_id)
    request.session["active_tenant_id"] = str(tenant.id)
    messages.success(request, f"সফলভাবে '{tenant.name}' ফার্মেসি সিলেক্ট করা হয়েছে।")
    return redirect("tenant_dashboard:dashboard")


@csrf_protect
def register_view(request):
    """
    Self-service registration portal for new pharmacy owners:
    - Automatically sets up a dedicated Tenant
    - Creates the Owner User and StaffProfile
    - Seeds default Subscription Plans & assigns a 14-day Free Trial
    - Logs the user in and redirects directly to their new Pharmacy Dashboard
    """
    if request.user.is_authenticated:
        return redirect("tenant_dashboard:dashboard")

    if request.method == "POST":
        pharmacy_name = request.POST.get("pharmacy_name", "").strip()
        pharmacy_name_bn = request.POST.get("pharmacy_name_bn", "").strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        drug_license = request.POST.get("drug_license", "").strip()
        owner_name = request.POST.get("owner_name", "").strip()
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        password_confirm = request.POST.get("password_confirm", "").strip()

        # Validation
        if not pharmacy_name or not phone or not username or not password:
            messages.error(request, "ফার্মেসির নাম, মোবাইল নম্বর, ইউজারনেম ও পাসওয়ার্ড পূরণ করা আবশ্যক!")
            return render(request, "auth/register.html", request.POST)

        if password != password_confirm:
            messages.error(request, "পাসওয়ার্ড দুটি মিলছে না! পুনরায় টাইপ করুন।")
            return render(request, "auth/register.html", request.POST)

        if len(password) < 6:
            messages.error(request, "পাসওয়ার্ড অন্তত ৬ অক্ষরের হতে হবে।")
            return render(request, "auth/register.html", request.POST)

        from django.contrib.auth.models import User
        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, f"'{username}' ইউজারনেমটি ইতিমধ্যে ব্যবহৃত হয়েছে। অন্য একটি ইউজারনেম বেছে নিন।")
            return render(request, "auth/register.html", request.POST)

        from django.utils.text import slugify
        import random
        base_slug = slugify(pharmacy_name) or f"rx-{random.randint(1000, 9999)}"
        slug = base_slug
        counter = 1
        while Tenant.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        try:
            # 1. Create Tenant
            tenant = Tenant.objects.create(
                name=pharmacy_name,
                name_bn=pharmacy_name_bn or pharmacy_name,
                slug=slug,
                phone=phone,
                address=address or "বাংলাদেশ",
                drug_license_number=drug_license,
                is_active=True
            )

            # 2. Create User
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=owner_name or pharmacy_name,
            )

            # 3. Create StaffProfile (Role: OWNER)
            StaffProfile.objects.create(
                user=user,
                tenant=tenant,
                role="OWNER",
                is_active=True
            )

            # 4. Assign 14-day Free Trial Subscription
            from core.saas_services import ensure_default_subscription_plans, ensure_tenant_subscription
            ensure_default_subscription_plans()
            ensure_tenant_subscription(tenant)

            # 5. Log in automatically
            login(request, user)
            request.session["active_tenant_id"] = str(tenant.id)

            messages.success(request, f"অভিনন্দন! আপনার ফার্মেসি '{tenant.name}' সফলভাবে নিবন্ধিত হয়েছে এবং ১৪ দিনের ফ্রি ট্রায়াল সক্রিয় হয়েছে!")
            return redirect("tenant_dashboard:dashboard")

        except Exception as e:
            messages.error(request, f"নিবন্ধন সম্পন্ন করতে সমস্যা হয়েছে: {str(e)}")
            return render(request, "auth/register.html", request.POST)

    return render(request, "auth/register.html")


