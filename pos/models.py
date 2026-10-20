import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from inventory.models import BrandDrug, DrugBatch
from customers.models import Customer


class CashRegisterSession(models.Model):
    """
    Tracks daily cash drawer opening and closing balance reconciliation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="register_sessions")
    counter_name = models.CharField(max_length=50, default="Counter 1")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="register_sessions")
    
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="Cash in drawer at start (৳)")
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Actual cash counted at close (৳)")
    
    total_cash_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_mfs_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), help_text="bKash/Nagad/Rocket")
    total_due_collected = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_due_given = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    
    is_closed = models.BooleanField(default=False)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)
    closing_notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self) -> str:
        status = "Closed" if self.is_closed else "Open"
        return f"{self.counter_name} by {self.user.username} ({status}) - {self.opened_at.strftime('%Y-%m-%d %H:%M')}"


class Invoice(models.Model):
    """
    Main Point-of-Sale sales transaction invoice record.
    """
    PAYMENT_METHOD_CHOICES = (
        ("CASH", "Cash at Counter"),
        ("BKASH", "bKash Merchant"),
        ("NAGAD", "Nagad"),
        ("ROCKET", "DBBL Rocket"),
        ("CARD", "Debit/Credit Card (POS Machine)"),
        ("DUE", "Full Baki / Due"),
        ("SPLIT", "Split Payment (Cash + MFS / Due)"),
    )
    STATUS_CHOICES = (
        ("COMPLETED", "Completed / Paid"),
        ("PARTIAL", "Partially Paid / Due"),
        ("RETURNED", "Returned / Refunded"),
        ("CANCELLED", "Cancelled"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="invoices")
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    register_session = models.ForeignKey(CashRegisterSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    customer_name_walkin = models.CharField(max_length=150, default="Walk-in Customer")
    customer_phone_walkin = models.CharField(max_length=20, blank=True, null=True)
    
    # Financial breakdown (in BDT ৳)
    subtotal_mrp = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total calculated from MRP")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("2.40"))
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, help_text="Final payable amount (subtotal - disc + vat)")
    
    # Settlement
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    change_returned = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="CASH")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="COMPLETED")
    
    cashier = models.ForeignKey(User, on_delete=models.PROTECT, related_name="invoices_processed")
    doctor_name = models.CharField(max_length=150, blank=True, null=True)
    prescription_notes = models.TextField(blank=True, null=True)
    
    is_printed = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["invoice_number", "created_at"]),
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["tenant", "created_at", "status"]),
        ]
        verbose_name = _("Sale Invoice")
        verbose_name_plural = _("Sale Invoices")

    def __str__(self) -> str:
        return f"{self.invoice_number} - ৳{self.total_payable} ({self.status})"

    @property
    def total_profit(self) -> Decimal:
        """Calculates total gross profit for this invoice."""
        profit = sum((item.gross_profit for item in self.items.all()), Decimal("0.00"))
        return profit - self.discount_amount


class InvoiceItem(models.Model):
    """
    Line item for an invoice tied to a specific FEFO batch for exact cost/profit auditing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    drug = models.ForeignKey(BrandDrug, on_delete=models.PROTECT, related_name="sale_items")
    batch = models.ForeignKey(DrugBatch, on_delete=models.PROTECT, related_name="sale_items")
    
    quantity = models.PositiveIntegerField(help_text="Units sold")
    unit_mrp = models.DecimalField(max_digits=10, decimal_places=2, help_text="Unit MRP at time of sale (৳)")
    unit_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Unit Cost Price (TP) from batch (৳)")
    
    line_total = models.DecimalField(max_digits=12, decimal_places=2, help_text="quantity * unit_mrp")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Invoice Item")
        verbose_name_plural = _("Invoice Items")

    def __str__(self) -> str:
        return f"{self.drug.brand_name} x {self.quantity} (Batch: {self.batch.batch_number})"

    @property
    def gross_profit(self) -> Decimal:
        """Profit calculated from (Unit MRP - Unit Purchase Price) * Quantity."""
        return (self.unit_mrp - self.unit_purchase_price) * Decimal(str(self.quantity))


class PaymentTransaction(models.Model):
    """
    Records payment gateway details (e.g. bKash, Nagad, Cash splits) for an invoice.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    payment_method = models.CharField(max_length=30)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_reference = models.CharField(max_length=100, blank=True, null=True, help_text="Gateway TrxID / MFS Sender Number")
    received_by = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.payment_method} ৳{self.amount} for {self.invoice.invoice_number}"

