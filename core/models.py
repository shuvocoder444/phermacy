import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Tenant(models.Model):
    """
    Tenant model for Independent Pharmacy Business (SQLite & Multi-tenant compatible).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, help_text="Pharmacy Name in English")
    name_bn = models.CharField(max_length=200, blank=True, null=True, help_text="নাম বাংলায় (Bangla Name)")
    slug = models.SlugField(max_length=100, unique=True, default="default-pharmacy")
     
    trade_license_number = models.CharField(max_length=100, blank=True, null=True)
    drug_license_number = models.CharField(max_length=100, blank=True, null=True, help_text="DGDA Drug License No.")
    vat_reg_number = models.CharField(max_length=50, blank=True, null=True, help_text="BIN / VAT Reg. No.")
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to="tenant_logos/", blank=True, null=True)
    division = models.CharField(max_length=50, blank=True, null=True)
    district = models.CharField(max_length=50, blank=True, null=True)
    thana = models.CharField(max_length=50, blank=True, null=True)
    
    # Store Configuration & Defaults
    default_vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("2.40"), help_text="Standard BD Retail Medicine VAT % (2.4% standard)")
    enable_sms_alerts = models.BooleanField(default=True)
    sms_sender_id = models.CharField(max_length=50, blank=True, null=True, help_text="Approved Masking / Non-masking sender ID")
    sms_api_key = models.CharField(max_length=255, blank=True, null=True)
    low_stock_threshold = models.PositiveIntegerField(default=15, help_text="Global threshold for low stock alert")
    
    created_on = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Pharmacy Tenant")
        verbose_name_plural = _("Pharmacy Tenants")

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"


class Domain(models.Model):
    domain = models.CharField(max_length=255, unique=True, db_index=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="domains")
    is_primary = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.domain


class SubscriptionPlan(models.Model):
    PLAN_TIERS = (
        ("starter", "Starter (Single Pharmacy)"),
        ("pro", "Pro (Pharmacy & SMS)"),
        ("enterprise", "Enterprise (Advanced Pharmacy)"),
    )
    name = models.CharField(max_length=100)
    tier = models.CharField(max_length=30, choices=PLAN_TIERS, default="starter")
    monthly_price_bdt = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("999.00"))
    yearly_price_bdt = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("9990.00"))
    max_users = models.PositiveIntegerField(default=3)
    sms_bundle_included = models.PositiveIntegerField(default=200, help_text="Monthly free SMS quota")
    features = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} - ৳{self.monthly_price_bdt}/mo"


class TenantSubscription(models.Model):
    STATUS_CHOICES = (
        ("trial", "Trial"),
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    )
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="trial")
    start_date = models.DateField(default=timezone.now)
    expires_at = models.DateField()
    sms_balance = models.PositiveIntegerField(default=100)
    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_valid(self) -> bool:
        return self.status in ("trial", "active") and self.expires_at >= timezone.now().date()

    def __str__(self) -> str:
        return f"{self.tenant.name} - {self.plan.name} ({self.status})"


class StaffProfile(models.Model):
    ROLE_CHOICES = (
        ("owner", "Owner / Admin"),
        ("pharmacist", "Registered Pharmacist (Grade A/B/C)"),
        ("cashier", "Cashier / POS Operator"),
        ("inventory_manager", "Inventory Manager"),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="staff_members")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default="cashier")
    bmdc_or_pcb_reg_no = models.CharField(
        max_length=50, blank=True, null=True, 
        help_text="Pharmacy Council of Bangladesh (PCB) Registration No for Pharmacists"
    )
    phone = models.CharField(max_length=20, db_index=True)
    nid_number = models.CharField(max_length=30, blank=True, null=True, help_text="National ID (Bangladesh)")
    is_active = models.BooleanField(default=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.user.get_full_name() or self.user.username} - {self.get_role_display()} ({self.tenant.name})"


class LedgerCategory(models.Model):
    """
    Categories for income and expenses (e.g. Shop Rent, Salary, Supplier Payment, Utilities, Sales).
    """
    CATEGORY_TYPES = (
        ("INCOME", "Income (আয়)"),
        ("EXPENSE", "Expense (ব্যয়)"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    name_bn = models.CharField(max_length=150, blank=True, null=True, help_text="বাংলা নাম")
    category_type = models.CharField(max_length=10, choices=CATEGORY_TYPES, default="EXPENSE")
    is_system_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category_type", "name"]
        verbose_name = _("Ledger Category")
        verbose_name_plural = _("Ledger Categories")

    def __str__(self) -> str:
        return f"[{self.get_category_type_display()}] {self.name} ({self.name_bn or ''})"


class IncomeExpenseEntry(models.Model):
    """
    Pharmacy cash book ledger tracking daily income and operational expenses.
    """
    ENTRY_TYPES = (
        ("INCOME", "Income (আয়)"),
        ("EXPENSE", "Expense (ব্যয়)"),
    )
    PAYMENT_METHODS = (
        ("CASH", "Cash Drawer (ক্যাশ ড্রয়ার)"),
        ("BKASH", "bKash Merchant"),
        ("NAGAD", "Nagad"),
        ("ROCKET", "Rocket"),
        ("BANK", "Bank Account (ব্যাংক)"),
        ("CHEQUE", "Cheque (চেক)"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="ledger_entries")
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES, db_index=True)
    category = models.ForeignKey(LedgerCategory, on_delete=models.PROTECT, related_name="entries")
    
    title = models.CharField(max_length=200, help_text="Short description of income/expense")
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount in BDT (৳)")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="CASH")
    
    voucher_number = models.CharField(max_length=100, blank=True, null=True, help_text="Voucher / Bill No.")
    recipient_or_payer = models.CharField(max_length=150, blank=True, null=True, help_text="Paid to / Received from")
    
    entry_date = models.DateField(default=timezone.now, db_index=True)
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="recorded_ledger_entries")
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        verbose_name = _("Income & Expense Entry")
        verbose_name_plural = _("Income & Expense Entries")

    def __str__(self) -> str:
        return f"{self.get_entry_type_display()}: {self.title} - ৳{self.amount} ({self.entry_date})"


class PlatformSetting(models.Model):
    """
    Global SaaS Platform Configuration & Branding.
    Controls the main landing page logo, platform title, and contact info.
    """
    platform_name = models.CharField(max_length=150, default="PharmaFlow BD")
    platform_tagline = models.CharField(max_length=255, default="ফার্মা ফ্লো • আধুনিক ফার্মেসি সফটওয়্যার", blank=True)
    logo = models.ImageField(upload_to="branding/", blank=True, null=True, help_text="SaaS Main Platform Header Logo")
    logo_url = models.CharField(max_length=500, blank=True, null=True, help_text="Direct Logo URL or uploaded path")
    support_phone = models.CharField(max_length=50, blank=True, null=True, default="01700-000000")
    support_email = models.EmailField(blank=True, null=True, default="support@webkoders.com")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Platform Setting")
        verbose_name_plural = _("Platform Settings")

    def __str__(self) -> str:
        return f"{self.platform_name} Settings"

    @classmethod
    def get_settings(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create(
                platform_name="PharmaFlow BD",
                platform_tagline="ফার্মা ফ্লো • আধুনিক ফার্মেসি সফটওয়্যার"
            )
        return obj

    @property
    def get_logo_url(self):
        if self.logo:
            try:
                return self.logo.url
            except Exception:
                pass
        return None
