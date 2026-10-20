from django.urls import path
from . import tenant_dashboard_views

app_name = "tenant_dashboard"

urlpatterns = [
    path("", tenant_dashboard_views.tenant_dashboard_view, name="dashboard"),
    path("sales/", tenant_dashboard_views.recent_pos_sales_view, name="sales"),
    path("settings/", tenant_dashboard_views.tenant_settings_page, name="settings"),
    path("subscription/", tenant_dashboard_views.tenant_subscription_page, name="subscription"),
    path("settings/update/", tenant_dashboard_views.tenant_settings_update, name="settings_update"),
]

