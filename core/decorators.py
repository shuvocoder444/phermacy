from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login


def super_admin_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a Super Admin.
    Only the SaaS Platform Super Admin can access these views.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url='login')

        if not request.user.is_superuser:
            messages.error(request, "অননুমোদিত অ্যাক্সেস: শুধুমাত্র SaaS প্ল্যাটফর্ম সুপার এডমিন এই পেজে প্রবেশ করতে পারেন।")
            return redirect("tenant_dashboard:dashboard")

        return view_func(request, *args, **kwargs)
    return _wrapped_view


def tenant_user_required(view_func):
    """
    Decorator for views that checks that the user is logged in and bound to an active Pharmacy Tenant.
    Blocks anonymous visitors and suspended tenants completely.
    Super Admins are always permitted.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url='login')

        # Super Admin is allowed everywhere
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        profile = getattr(request.user, "staff_profile", None)
        if not profile or not profile.tenant:
            messages.error(request, "আপনার অ্যাকাউন্টের সাথে কোনো ফার্মেসি যুক্ত নেই। অনুগ্রহ করে এডমিনের সাথে যোগাযোগ করুন।")
            return redirect("login")

        if not profile.tenant.is_active:
            messages.error(request, f"আপনার ফার্মেসি '{profile.tenant.name}' স্থগিত (Suspended) রয়েছে। সার্ভিস পুনরায় চালু করতে এডমিনের সাথে যোগাযোগ করুন।")
            return redirect("login")

        return view_func(request, *args, **kwargs)
    return _wrapped_view

