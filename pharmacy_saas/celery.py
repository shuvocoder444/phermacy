import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pharmacy_saas.settings")

app = Celery("pharmacy_saas")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Celery Beat Schedule Configuration
app.conf.beat_schedule = {
    # Scan for batches expiring in 30, 60, 90 days every night at 00:05 AM BD time
    "check-batch-expiry-nightly": {
        "task": "notifications.tasks.check_expiring_batches_nightly",
        "schedule": crontab(hour=0, minute=5),
    },
    # Compile and send daily sales summary SMS to pharmacy owners at 11:55 PM BD time
    "send-daily-sales-report-nightly": {
        "task": "notifications.tasks.send_daily_sales_report_nightly",
        "schedule": crontab(hour=23, minute=55),
    },
}

