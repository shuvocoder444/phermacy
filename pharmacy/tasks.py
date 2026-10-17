"""Scheduled tenant expiry notifications."""

from celery import shared_task
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from .models import ExpiryAlert, StockBatch, Tenant


@shared_task
def notify_expiring_stock() -> dict[str, int]:
    """Record batches due to expire in 30, 60, or 90 days for each tenant."""
    today = timezone.localdate()
    created = 0
    tenants = Tenant.objects.filter(is_active=True).only("id")
    for tenant in tenants.iterator():
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.tenant_id', %s, true)", [str(tenant.pk)]
                )
            batches = StockBatch.objects.filter(
                tenant=tenant,
                quantity_available__gt=0,
                expiry_date__gt=today,
                expiry_date__lte=today + timezone.timedelta(days=90),
            ).annotate(days_remaining=F("expiry_date") - today)
            for batch in batches.iterator():
                days_remaining = batch.expiry_date.toordinal() - today.toordinal()
                if days_remaining not in {30, 60, 90}:
                    continue
                _, was_created = ExpiryAlert.objects.get_or_create(
                    tenant=tenant,
                    batch=batch,
                    detected_on=today,
                    defaults={"days_remaining": days_remaining},
                )
                created += int(was_created)
    return {"alerts_created": created}
