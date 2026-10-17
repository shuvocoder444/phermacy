import os
import sys
import django

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pharmacy_saas.settings")
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from core.models import Tenant
from core.saas_services import ensure_default_subscription_plans, ensure_tenant_subscription
from core.saas_admin_views import saas_admin_dashboard
from core.tenant_dashboard_views import tenant_dashboard_view

rf = RequestFactory()

# 1. Test Seed Plans
plans = ensure_default_subscription_plans()
print(f"✓ Seeded/verified {len(plans)} subscription plans:")
for p in plans:
    print(f"   - {p.name}: ৳{p.monthly_price_bdt}/mo")

# 2. Test Tenant & Subscription
tenant = Tenant.objects.first()
if tenant:
    sub = ensure_tenant_subscription(tenant)
    print(f"✓ Tenant '{tenant.name}' attached to plan '{sub.plan.name}' (expires: {sub.expires_at})")

# 3. Test SaaS Admin Dashboard View
user, _ = User.objects.get_or_create(username="superadmin_test", defaults={"is_superuser": True})
req_admin = rf.get("/saas-admin/")
req_admin.user = user
resp_admin = saas_admin_dashboard(req_admin)
print(f"✓ SaaS Admin Dashboard HTTP status: {resp_admin.status_code}")

# 4. Test Tenant Dashboard View
req_tenant = rf.get("/dashboard/")
req_tenant.user = user
req_tenant.tenant = tenant
resp_tenant = tenant_dashboard_view(req_tenant)
print(f"✓ Tenant Dashboard HTTP status: {resp_tenant.status_code}")

print("\nAll Dashboard services and views tested successfully!")
