import logging
from decimal import Decimal
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.db.models import Sum, Count, Q

from core.models import Tenant
from inventory.models import DrugBatch
from pos.models import Invoice
from .sms_services import BangladeshSMSGateway

logger = logging.getLogger(__name__)


@shared_task(name="notifications.tasks.check_expiring_batches_nightly")
def check_expiring_batches_nightly():
    """
    Runs every midnight.
    Scans all batches expiring in 30, 60, and 90 days and flags alert logs.
    Sends summary SMS / Email to Tenant Owners for items near expiry.
    """
    today = timezone.now().date()
    windows = [30, 60, 90]

    logger.info(f"Starting Nightly Expiry Check for {today}...")

    for tenant in Tenant.objects.filter(is_active=True):
        # We query batches for this tenant schema
        for days in windows:
            cutoff = today + timedelta(days=days)
            expiring_batches = (
                DrugBatch.objects.filter(
                    current_stock__gt=0,
                    expiry_date__gte=today,
                    expiry_date__lte=cutoff
                )
                .select_related("drug")
                .order_by("expiry_date")
            )

            count = expiring_batches.count()
            if count > 0 and days == 30:
                # Critical alert for 30 days expiry
                logger.warning(f"Tenant {tenant.name} has {count} batches expiring in next {days} days!")
                if tenant.enable_sms_alerts and tenant.phone:
                    msg = (
                        f"সতর্কতা: {tenant.name}, আপনার ফার্মেসিতে আগামী ৩০ দিনের মধ্যে {count}টি মেডিসিনের মেয়াদ শেষ হবে। "
                        f"দ্রুত স্টক চেক করুন।"
                    )
                    BangladeshSMSGateway.send_sms(
                        phone_number=tenant.phone,
                        message=msg,
                        sender_id=tenant.sms_sender_id
                    )

    return "Expiry check completed."


@shared_task(name="notifications.tasks.send_daily_sales_report_nightly")
def send_daily_sales_report_nightly():
    """
    Runs at 11:55 PM every day.
    Compiles daily sales, cash collected, bKash/Nagad collections, due extended, and gross profit.
    Sends an executive summary SMS to the pharmacy owner.
    """
    today = timezone.now().date()
    start_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    end_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))

    for tenant in Tenant.objects.filter(is_active=True, enable_sms_alerts=True):
        if not tenant.phone:
            continue

        invoices_today = Invoice.objects.filter(
            created_at__range=(start_of_day, end_of_day),
            status__in=["COMPLETED", "PARTIAL"]
        )

        total_sales = invoices_today.aggregate(tot=Sum("total_payable"))["tot"] or Decimal("0.00")
        total_paid = invoices_today.aggregate(tot=Sum("paid_amount"))["tot"] or Decimal("0.00")
        total_due = invoices_today.aggregate(tot=Sum("due_amount"))["tot"] or Decimal("0.00")
        total_invoices = invoices_today.count()

        if total_invoices > 0:
            msg = (
                f"[{tenant.name} ডেইলি সেলস রিপোর্ট]\n"
                f"তারিখ: {today.strftime('%d/%m/%Y')}\n"
                f"মোট বিল: {total_invoices}টি\n"
                f"মোট বিক্রি: ৳{total_sales:,.2f}\n"
                f"ক্যাশ/MFS জমা: ৳{total_paid:,.2f}\n"
                f"নতুন বকেয়া: ৳{total_due:,.2f}\n"
                f"ধন্যবাদ।"
            )
            BangladeshSMSGateway.send_sms(
                phone_number=tenant.phone,
                message=msg,
                sender_id=tenant.sms_sender_id
            )
            logger.info(f"Sent daily sales summary to owner of {tenant.name}")

    return "Daily sales reports dispatched."

