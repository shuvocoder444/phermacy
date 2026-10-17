from django.contrib import admin

from .models import (
    Brand,
    CashSession,
    Customer,
    DueLedger,
    ExpiryAlert,
    Generic,
    Manufacturer,
    Membership,
    Medicine,
    Sale,
    SaleItem,
    StockBatch,
    StockMovement,
    SubscriptionPlan,
    Tenant,
    TenantDomain,
)

admin.site.register(
    (
        SubscriptionPlan,
        Tenant,
        TenantDomain,
        Membership,
        Manufacturer,
        Generic,
        Brand,
        Medicine,
        StockBatch,
        Customer,
        Sale,
        SaleItem,
        DueLedger,
        StockMovement,
        CashSession,
        ExpiryAlert,
    )
)
