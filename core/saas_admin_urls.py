from django.urls import path
from . import saas_admin_views

app_name = "saas_admin"

urlpatterns = [
    path("", saas_admin_views.saas_admin_dashboard, name="dashboard"),
    path("tenants/create/", saas_admin_views.saas_tenant_create, name="tenant_create"),
    path("tenants/<uuid:tenant_id>/", saas_admin_views.saas_tenant_detail, name="tenant_detail"),
    path("tenants/<uuid:tenant_id>/status/", saas_admin_views.saas_tenant_update_status, name="tenant_update_status"),
    path("plans/save/", saas_admin_views.saas_plan_save, name="plan_save"),
    path("settings/branding/", saas_admin_views.saas_platform_branding_save, name="branding_save"),
]

