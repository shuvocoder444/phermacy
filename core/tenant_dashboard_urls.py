from django.urls import path
from . import tenant_dashboard_views

app_name = "tenant_dashboard"

urlpatterns = [
    path("", tenant_dashboard_views.tenant_dashboard_view, name="dashboard"),
    path("settings/", tenant_dashboard_views.tenant_settings_update, name="settings_update"),
]

