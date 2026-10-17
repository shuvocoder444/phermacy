"""Domain models for a Bangladesh retail pharmacy SaaS."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class SubscriptionPlan(models.Model):
    class BillingCycle(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    name = models.CharField(max_length=100, unique=True)
    billing_cycle = models.CharField(max_length=10, choices=BillingCycle.choices)
    price_bdt = models.DecimalField(max_digits=10, decimal_places=2)
    max_staff = models.PositiveSmallIntegerField(default=5)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.billing_cycle})"


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=80, unique=True)
    plan = models.ForeignKey(
        SubscriptionPlan, null=True, blank=True, on_delete=models.SET_NULL
    )
    license_expires_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class TenantDomain(models.Model):
    tenant = models.ForeignKey(Tenant, related_name="domains", on_delete=models.CASCADE)
    domain = models.CharField(max_length=253, unique=True)
    is_primary = models.BooleanField(default=False)

    def save(self, *args: object, **kwargs: object) -> None:
        self.domain = self.domain.strip().rstrip(".").lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.domain


class TenantOwnedModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Membership(TenantOwnedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        PHARMACIST = "pharmacist", "Pharmacist"
        CASHIER = "cashier", "Cashier"
        INVENTORY_MANAGER = "inventory_manager", "Inventory Manager"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=24, choices=Role.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "user"), name="unique_tenant_membership"
            )
        ]


class Manufacturer(TenantOwnedModel):
    name = models.CharField(max_length=160)
    name_bn = models.CharField(max_length=160, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "name"), name="unique_tenant_manufacturer"
            )
        ]
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Generic(TenantOwnedModel):
    name_en = models.CharField(max_length=180)
    name_bn = models.CharField(max_length=180, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "name_en"), name="unique_tenant_generic"
            )
        ]
        ordering = ("name_en",)

    def __str__(self) -> str:
        return self.name_en


class Brand(TenantOwnedModel):
    name_en = models.CharField(max_length=180)
    name_bn = models.CharField(max_length=180, blank=True)
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "name_en", "manufacturer"),
                name="unique_tenant_brand_manufacturer",
            )
        ]
        ordering = ("name_en",)

    def __str__(self) -> str:
        return self.name_en


class Medicine(TenantOwnedModel):
    class Formulation(models.TextChoices):
        TABLET = "tablet", "Tablet"
        CAPSULE = "capsule", "Capsule"
        SYRUP = "syrup", "Syrup"
        SUSPENSION = "suspension", "Suspension"
        INJECTION = "injection", "Injection / IV"
        CREAM = "cream", "Cream"
        DROPS = "drops", "Drops"
        OTHER = "other", "Other"

    name_en = models.CharField(max_length=200, db_index=True)
    name_bn = models.CharField(max_length=200, blank=True, db_index=True)
    generic = models.ForeignKey(Generic, on_delete=models.PROTECT)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, null=True, blank=True)
    strength = models.CharField(max_length=80, blank=True)
    formulation = models.CharField(
        max_length=20, choices=Formulation.choices, default=Formulation.TABLET
    )
    mrp = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    trade_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        default=Decimal("0"),
    )
    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        default=Decimal("2.40"),
        help_text="Configured percentage, e.g. 2.40 for 2.4%.",
    )
    is_active = models.BooleanField(default=True)
    is_common = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ("name_en",)
        indexes = [models.Index(fields=("tenant", "is_active", "is_common"))]

    def __str__(self) -> str:
        return f"{self.name_en} {self.strength}".strip()


class StockBatch(TenantOwnedModel):
    medicine = models.ForeignKey(
        Medicine, related_name="batches", on_delete=models.PROTECT
    )
    batch_number = models.CharField(max_length=80)
    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    quantity_available = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0"))],
        default=Decimal("0"),
    )
    purchase_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    mrp = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    supplier_name = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ("expiry_date", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "medicine", "batch_number"),
                name="unique_medicine_batch_per_tenant",
            )
        ]
        indexes = [
            models.Index(fields=("tenant", "expiry_date")),
            models.Index(fields=("tenant", "medicine", "expiry_date")),
        ]

    def __str__(self) -> str:
        return f"{self.medicine} / {self.batch_number}"


class Customer(TenantOwnedModel):
    name = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=24)
    phone_normalized = models.CharField(max_length=24)
    preferred_language = models.CharField(
        max_length=2, choices=(("en", "English"), ("bn", "বাংলা")), default="bn"
    )
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "phone_normalized"),
                name="unique_customer_phone_per_tenant",
            )
        ]
        ordering = ("phone_normalized",)

    def save(self, *args: object, **kwargs: object) -> None:
        self.phone_normalized = "".join(
            char for char in self.phone.strip() if char.isdigit() or char == "+"
        )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name or self.phone


class Sale(TenantOwnedModel):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Counter cash"
        BKASH = "bkash", "bKash"
        NAGAD = "nagad", "Nagad"
        ROCKET = "rocket", "Rocket"

    class DiscountType(models.TextChoices):
        NONE = "none", "No discount"
        FLAT = "flat", "Flat BDT"
        PERCENT = "percent", "Percentage"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=40)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    customer = models.ForeignKey(
        Customer, related_name="sales", on_delete=models.PROTECT, null=True, blank=True
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_type = models.CharField(
        max_length=10, choices=DiscountType.choices, default=DiscountType.NONE
    )
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0")
    )
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0")
    )
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(
        max_length=12, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    payment_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "invoice_number"), name="unique_tenant_invoice"
            )
        ]
        ordering = ("-created_at",)

    @property
    def amount_due(self) -> Decimal:
        return max(Decimal("0"), self.total - self.amount_paid)

    def __str__(self) -> str:
        return self.invoice_number


class SaleItem(TenantOwnedModel):
    sale = models.ForeignKey(Sale, related_name="items", on_delete=models.PROTECT)
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT)
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT)
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)


class DueLedger(TenantOwnedModel):
    class EntryType(models.TextChoices):
        CHARGE = "charge", "Sale due"
        PAYMENT = "payment", "Due collection"

    customer = models.ForeignKey(
        Customer, related_name="ledger_entries", on_delete=models.PROTECT
    )
    sale = models.ForeignKey(
        Sale, related_name="due_entries", on_delete=models.PROTECT, null=True, blank=True
    )
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    payment_method = models.CharField(
        max_length=12, choices=Sale.PaymentMethod.choices, blank=True
    )
    reference = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("tenant", "customer", "created_at"))]


class StockMovement(TenantOwnedModel):
    class MovementType(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        SALE = "sale", "Sale"
        DAMAGE = "damage", "Damage"
        SHORTAGE = "shortage", "Shortage"
        SUPPLIER_RETURN = "supplier_return", "Return to supplier"
        SALE_RETURN = "sale_return", "Customer return"

    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT)
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity_delta = models.DecimalField(max_digits=12, decimal_places=3)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.CharField(max_length=240, blank=True)


class CashSession(TenantOwnedModel):
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="opened_cash_sessions",
        on_delete=models.PROTECT,
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="closed_cash_sessions",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2)
    closing_balance = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=("tenant", "closed_at"))]


class ExpiryAlert(TenantOwnedModel):
    batch = models.ForeignKey(StockBatch, on_delete=models.CASCADE)
    days_remaining = models.PositiveSmallIntegerField()
    detected_on = models.DateField(default=timezone.localdate)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "batch", "detected_on"),
                name="unique_batch_expiry_alert_per_day",
            )
        ]
