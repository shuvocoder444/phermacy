import uuid
from decimal import Decimal
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db.models import F, Q, Sum


class Manufacturer(models.Model):
    """
    Pharmaceutical Manufacturers in Bangladesh (e.g. Square, Incepta, Beximco, Renata, Acme).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True, db_index=True)
    name_bn = models.CharField(max_length=250, blank=True, null=True, help_text="বাংলা নাম")
    short_code = models.CharField(max_length=30, blank=True, null=True)
    dgda_license_no = models.CharField(max_length=100, blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Manufacturer")
        verbose_name_plural = _("Manufacturers")

    def __str__(self) -> str:
        return self.name


class DosageForm(models.Model):
    """
    Formulation type (Tablet, Capsule, Syrup, Suspension, IV Infusion, Eye Drop, Cream, etc.).
    """
    name = models.CharField(max_length=100, unique=True)
    name_bn = models.CharField(max_length=150, blank=True, null=True)
    short_name = models.CharField(max_length=20, blank=True, null=True, help_text="e.g. Tab, Cap, Syr, Susp, Inj")
    is_liquid = models.BooleanField(default=False)
    requires_cold_chain = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.short_name})" if self.short_name else self.name


class GenericDrug(models.Model):
    """
    DGDA standardized chemical generic entities (e.g. Paracetamol, Esomeprazole, Montelukast).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    name_bn = models.CharField(max_length=300, blank=True, null=True, help_text="জেনেরিক নাম বাংলায়")
    therapeutic_class = models.CharField(max_length=200, blank=True, null=True, help_text="e.g., NSAID, PPI, Antibiotic")
    pregnancy_category = models.CharField(max_length=10, blank=True, null=True, help_text="A, B, C, D, X")
    side_effects = models.TextField(blank=True, null=True)
    is_narcotic_or_sedative = models.BooleanField(default=False, help_text="Requires strict prescription audit")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Generic Drug")
        verbose_name_plural = _("Generic Drugs")

    def __str__(self) -> str:
        return self.name


class BrandDrug(models.Model):
    """
    Commercial finished drug product sold in Bangladesh retail pharmacies (e.g. Napa Extra 500mg+65mg).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generic = models.ForeignKey(GenericDrug, on_delete=models.PROTECT, related_name="brands")
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.PROTECT, related_name="brand_products")
    dosage_form = models.ForeignKey(DosageForm, on_delete=models.PROTECT, related_name="brand_products")
    
    brand_name = models.CharField(max_length=200, db_index=True)
    brand_name_bn = models.CharField(max_length=250, blank=True, null=True, help_text="ব্র্যান্ডের নাম বাংলায়")
    strength = models.CharField(max_length=100, help_text="e.g. 500 mg, 20 mg, 10 mg/5ml")
    dar_number = models.CharField(max_length=100, blank=True, null=True, help_text="DGDA Drug Administration Reg No.")
    barcode = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    
    # Packaging details
    pack_size = models.PositiveIntegerField(default=1, help_text="Units per box/strip (e.g. 10 tablets/strip, 100/box)")
    strip_size = models.PositiveIntegerField(default=10, help_text="Tablets/capsules per strip")
    
    # Financials (Per Unit Base)
    unit_mrp = models.DecimalField(max_digits=10, decimal_places=2, help_text="Retail Selling Price (MRP) per individual unit (৳)")
    unit_tp = models.DecimalField(max_digits=10, decimal_places=2, help_text="Trade Price (TP) per individual unit (৳)")
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("2.40"), help_text="Standard 2.4% VAT")
    
    # Storage and Alerts
    rack_location = models.CharField(max_length=50, blank=True, null=True, help_text="Shelf/Rack ID e.g. A1-R3")
    reorder_level = models.PositiveIntegerField(default=20, help_text="Alert when aggregate stock falls below this")
    is_prescription_required = models.BooleanField(default=False)
    is_antibiotic = models.BooleanField(default=False, help_text="DGDA antibiotic dispensation guidelines")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["brand_name"]
        indexes = [
            models.Index(fields=["brand_name", "generic"]),
            models.Index(fields=["barcode"]),
        ]
        verbose_name = _("Brand Drug")
        verbose_name_plural = _("Brand Drugs")

    def __str__(self) -> str:
        return f"{self.brand_name} {self.strength} ({self.dosage_form.short_name or self.dosage_form.name})"

    @property
    def total_stock(self) -> int:
        """Returns non-expired available stock across all active batches."""
        total = self.batches.filter(
            current_stock__gt=0,
            expiry_date__gt=timezone.now().date()
        ).aggregate(total=Sum("current_stock"))["total"]
        return total or 0


class BatchQuerySet(models.QuerySet):
    """
    Custom QuerySet offering FEFO (First Expire, First Out) ordering and expiry filters.
    """
    def fefo(self):
        """Orders batches strictly by earliest expiring first."""
        return self.filter(current_stock__gt=0, expiry_date__gt=timezone.now().date()).order_by("expiry_date", "created_at")

    def expiring_within(self, days: int = 30):
        """Finds batches expiring in the next N days."""
        today = timezone.now().date()
        cutoff = today + timedelta(days=days)
        return self.filter(current_stock__gt=0, expiry_date__gte=today, expiry_date__lte=cutoff).order_by("expiry_date")

    def expired(self):
        """Batches that have passed their expiration date."""
        today = timezone.now().date()
        return self.filter(current_stock__gt=0, expiry_date__lt=today).order_by("expiry_date")


class DrugBatch(models.Model):
    """
    Batch-level inventory tracker enabling FEFO dispensing and strict audit trails.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="inventory_batches")
    drug = models.ForeignKey(BrandDrug, on_delete=models.CASCADE, related_name="batches")
    batch_number = models.CharField(max_length=100, db_index=True)
    
    manufacturing_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(db_index=True)
    
    # Financial metrics per unit for this specific batch
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Actual purchase cost per unit (৳)")
    unit_mrp = models.DecimalField(max_digits=10, decimal_places=2, help_text="Batch MRP per unit (৳)")
    
    initial_stock = models.PositiveIntegerField(help_text="Stock received in this batch")
    current_stock = models.PositiveIntegerField(default=0, db_index=True, help_text="Remaining sellable units")
    
    supplier_challan_no = models.CharField(max_length=100, blank=True, null=True)
    received_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BatchQuerySet.as_manager()

    class Meta:
        ordering = ["expiry_date"]
        unique_together = ("drug", "batch_number")
        indexes = [
            models.Index(fields=["drug", "expiry_date", "current_stock"]),
        ]
        verbose_name = _("Drug Batch")
        verbose_name_plural = _("Drug Batches")

    def __str__(self) -> str:
        return f"{self.drug.brand_name} - Batch: {self.batch_number} (Exp: {self.expiry_date}) [Stock: {self.current_stock}]"

    @property
    def is_expired(self) -> bool:
        return self.expiry_date < timezone.now().date()

    @property
    def days_until_expiry(self) -> int:
        return (self.expiry_date - timezone.now().date()).days


class StockMovement(models.Model):
    """
    Audit log for any inventory movement (Sale, Purchase, Return, Damage, Shortage, FEFO deduction).
    """
    MOVEMENT_TYPES = (
        ("PURCHASE_RECEIPT", "Purchase Receipt (Challan In)"),
        ("SALE", "Point of Sale (Deduction)"),
        ("SALE_RETURN", "Customer Sale Return"),
        ("SUPPLIER_RETURN", "Return to Manufacturer / Supplier"),
        ("DAMAGE_EXPIRED", "Damage or Expired Write-off"),
        ("AUDIT_ADJUSTMENT", "Physical Inventory Audit Adjustment"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(DrugBatch, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=30, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text="Positive for addition, negative for deduction")
    balance_after = models.PositiveIntegerField(help_text="Stock count after movement")
    reference_id = models.CharField(max_length=100, blank=True, null=True, help_text="Invoice #, Challan #, or Audit #")
    notes = models.TextField(blank=True, null=True)
    created_by = models.CharField(max_length=100, default="system")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.movement_type}: {self.quantity} on {self.batch.batch_number} (Bal: {self.balance_after})"

