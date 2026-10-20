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
    """Public sign-up is closed; pharmacy accounts are provisioned by platform admin."""
    if request.user.is_authenticated:
        return redirect("tenant_dashboard:dashboard")
    messages.info(request, "New pharmacy accounts are created by the platform administrator. Please contact them.")
    return redirect("login")
