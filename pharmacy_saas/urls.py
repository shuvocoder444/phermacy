from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.conf import settings
from django.conf.urls.static import static

def landing_view(request):
    """Renders the SaaS marketing landing page."""
    return render(request, "landing.html")

from core import auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.login_view, name="login"),
    path("register/", auth_views.register_view, name="register"),
    path("signup/", auth_views.register_view, name="signup"),
    path("logout/", auth_views.logout_view, name="logout"),
    path("switch-tenant/<uuid:tenant_id>/", auth_views.switch_tenant_view, name="switch_tenant"),
    path("saas-admin/", include("core.saas_admin_urls", namespace="saas_admin")),
    path("dashboard/", include("core.tenant_dashboard_urls", namespace="tenant_dashboard")),
    path("tenant/", include("core.tenant_dashboard_urls", namespace="tenant")),
    path("pos/", include("pos.urls", namespace="pos")),
    path("inventory/", include("inventory.urls", namespace="inventory")),
    path("stock/", include("inventory.urls", namespace="stock")),
    path("ledger/", include("core.ledger_urls", namespace="ledger")),
    path("customers/", include("customers.urls", namespace="customers")),
    path("", landing_view, name="landing"),
]

if settings.MEDIA_URL:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

