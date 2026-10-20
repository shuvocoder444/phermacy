from django.utils.deprecation import MiddlewareMixin
from core.models import Domain, Tenant, StaffProfile


class TenantMiddleware(MiddlewareMixin):
    """
    Resolves and strictly isolates the active tenant for every request:
    1. If a regular user is authenticated, locks request.tenant to their registered pharmacy (StaffProfile.tenant).
       This guarantees complete multi-tenant data isolation — a user can NEVER access or see another tenant's data.
    2. If a Super Admin is authenticated, allows inspecting specific tenants via session or query param (?switch_tenant=...).
    3. If unauthenticated, resolves by subdomain (e.g. almadina.pos.webkoders.com) or default fallback.
    """
    def process_request(self, request):
        user = getattr(request, "user", None)
        tenant = None

        # 1. Authenticated User Tenant Locking (Strict Multi-Tenant Isolation)
        if user and user.is_authenticated:
            if user.is_superuser:
                # Super Admin can switch tenants or select one via session/GET
                switch_id = request.GET.get("switch_tenant")
                if switch_id:
                    target = Tenant.objects.filter(id=switch_id, is_active=True).first()
                    if target:
                        request.session["active_tenant_id"] = str(target.id)
                        tenant = target

                if not tenant and request.session.get("active_tenant_id"):
                    tenant = Tenant.objects.filter(id=request.session["active_tenant_id"], is_active=True).first()
            else:
                # Regular staff/pharmacist/owner is 100% locked to their assigned pharmacy
                profile = StaffProfile.objects.filter(user=user, is_active=True).select_related("tenant").first()
                if profile and profile.tenant:
                    tenant = profile.tenant

        # 2. Subdomain Resolution (e.g. almadina.pos.webkoders.com)
        if not tenant:
            host = request.get_host().split(":")[0].lower().rstrip(".")
            domain = Domain.objects.filter(domain=host, tenant__is_active=True).select_related("tenant").first()
            if domain:
                tenant = domain.tenant
            subdomain = host.split(".")[0] if "." in host else ""
            if not tenant and subdomain and subdomain not in ("www", "localhost", "127", "pos"):
                tenant = Tenant.objects.filter(slug=subdomain, is_active=True).first()

        # 3. Session Fallback
        if not tenant and request.session.get("active_tenant_id"):
            tenant = Tenant.objects.filter(id=request.session["active_tenant_id"], is_active=True).first()

        # 4. Default Fallback (Only if explicitly authenticated or domain matched)
        if not tenant and user and user.is_authenticated and user.is_superuser:
            tenant = Tenant.objects.filter(is_active=True).first()

        request.tenant = tenant
