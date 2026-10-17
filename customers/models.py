import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

# BD Phone number validator (e.g., 01711223344 or +8801711223344)
bd_phone_validator = RegexValidator(
    regex=r'^(?:\+?88)?01[3-9]\d{8}$',
    message=_("Enter a valid 11-digit Bangladesh phone number (e.g. 01712345678).")
)


class Customer(models.Model):
    """
    Retail customer profile with credit tracking for Bangladesh 'Baki Khata' system.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="customers")
    name = models.CharField(max_length=150, db_index=True)
    name_bn = models.CharField(max_length=200, blank=True, null=True, help_text="গ্রাহকের নাম (বাংলা)")
    phone = models.CharField(max_length=20, validators=[bd_phone_validator], db_index=True)
    address = models.TextField(blank=True, null=True)
    
    # Due / Credit Management
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("5000.00"), help_text="Maximum allowed Baki (৳)")
    current_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), db_index=True, help_text="Total outstanding due (৳)")
    
    # Loyalty / Health Profile
    regular_doctor_name = models.CharField(max_length=150, blank=True, null=True)
    chronic_conditions = models.TextField(blank=True, null=True, help_text="e.g. Diabetes, Hypertension, Asthma")
    notes = models.TextField(blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")

    def __str__(self) -> str:
        return f"{self.name} ({self.phone}) - Due: ৳{self.current_due}"


class DueLedger(models.Model):
    """
    Immutable ledger entries tracking customer Baki (due) additions, settlements, and partial payments.
    """
    TRANSACTION_TYPES = (
        ("INVOICE_DUE", "Due from Invoice / Sale"),
        ("PAYMENT_CASH", "Due Repayment (Counter Cash)"),
        ("PAYMENT_BKASH", "Due Repayment (bKash)"),
        ("PAYMENT_NAGAD", "Due Repayment (Nagad)"),
        ("PAYMENT_ROCKET", "Due Repayment (Rocket)"),
        ("PAYMENT_BANK", "Due Repayment (Bank Transfer)"),
        ("ADJUSTMENT_DISCOUNT", "Bad Debt / Due Discount Write-off"),
        ("RETURN_CREDIT", "Credit from Item Return"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="due_entries")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="ledger_entries")
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Transaction amount (৳)")
    balance_before = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    
    invoice_reference = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    gateway_trx_id = models.CharField(max_length=100, blank=True, null=True, help_text="bKash / Nagad TrxID if applicable")
    collected_by = models.CharField(max_length=100, blank=True, null=True)
    notes = models.CharField(max_length=255, blank=True, null=True)
    
    sms_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Due Ledger Entry")
        verbose_name_plural = _("Due Ledger Entries")

    def __str__(self) -> str:
        return f"{self.customer.name} | {self.transaction_type} | ৳{self.amount} | Bal: ৳{self.balance_after}"

