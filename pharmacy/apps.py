from django.apps import AppConfig
from django.db.models.signals import post_migrate


class PharmacyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pharmacy"

    def ready(self) -> None:
        from .rls import install_postgres_tenant_policies

        post_migrate.connect(
            install_postgres_tenant_policies,
            sender=self,
            dispatch_uid="pharmacy.install_postgres_tenant_policies",
        )
