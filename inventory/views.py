from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.decorators import tenant_user_required

from .models import (
    BrandDrug,
    DosageForm,
    DrugBatch,
    GenericDrug,
    Manufacturer,
    StockMovement,
)


@tenant_user_required
def stock_dashboard(request):
    """
    Main Pharmacy Inventory & FEFO Batch Management Dashboard.
    Strictly isolated to the current tenant.
    """
    tenant = getattr(request, "tenant", None)
    today = timezone.now().date()
    expiry_60_days = today + timedelta(days=60)

    # Base batch queryset for tenant
    batch_qs = DrugBatch.objects.select_related("drug", "drug__manufacturer", "drug__generic", "drug__dosage_form")
    if tenant:
        batch_qs = batch_qs.filter(tenant=tenant)
    else:
        batch_qs = batch_qs.all()

    # Metrics calculation
    total_batches = batch_qs.filter(current_stock__gt=0).count()
    total_units = batch_qs.aggregate(t=Sum("current_stock"))["t"] or 0
    
    # Valuation
    total_tp_value = sum(b.current_stock * b.purchase_price for b in batch_qs.filter(current_stock__gt=0))
    total_mrp_value = sum(b.current_stock * b.unit_mrp for b in batch_qs.filter(current_stock__gt=0))

    # Alerts count
    low_stock_count = batch_qs.filter(current_stock__gt=0, current_stock__lte=15).count()
    expiring_soon_count = batch_qs.filter(current_stock__gt=0, expiry_date__gt=today, expiry_date__lte=expiry_60_days).count()
    expired_count = batch_qs.filter(current_stock__gt=0, expiry_date__lte=today).count()

    # Search & Filter
    query = request.GET.get("q", "").strip()
    filter_type = request.GET.get("filter", "all")

    if query:
        batch_qs = batch_qs.filter(
            Q(drug__brand_name__icontains=query) |
            Q(drug__brand_name_bn__icontains=query) |
            Q(drug__generic__name__icontains=query) |
            Q(drug__manufacturer__name__icontains=query) |
            Q(batch_number__icontains=query)
        )

    if filter_type == "low_stock":
        batch_qs = batch_qs.filter(current_stock__gt=0, current_stock__lte=15)
    elif filter_type == "expiring_60":
        batch_qs = batch_qs.filter(current_stock__gt=0, expiry_date__gt=today, expiry_date__lte=expiry_60_days)
    elif filter_type == "expired":
        batch_qs = batch_qs.filter(current_stock__gt=0, expiry_date__lte=today)
    elif filter_type == "out_of_stock":
        batch_qs = batch_qs.filter(current_stock=0)

    # Ordering FEFO
    batches = batch_qs.order_by("expiry_date", "drug__brand_name")

    paginator = Paginator(batches, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "total_batches": total_batches,
        "total_units": total_units,
        "total_tp_value": total_tp_value,
        "total_mrp_value": total_mrp_value,
        "low_stock_count": low_stock_count,
        "expiring_soon_count": expiring_soon_count,
        "expired_count": expired_count,
        "query": query,
        "filter_type": filter_type,
        "today": today,
        "expiry_60_days": expiry_60_days,
        "tenant": tenant,
    }

    if request.headers.get("HX-Request"):
        return render(request, "inventory/partials/stock_table.html", context)

    return render(request, "inventory/stock_dashboard.html", context)


@tenant_user_required
@require_POST
def add_batch_view(request):
    """
    Adds a new inventory batch for a brand drug with FEFO tracking.
    Supports both traditional POST redirect and high-speed JSON/HTMX response.
    """
    tenant = getattr(request, "tenant", None)
    
    brand_name = request.POST.get("brand_name", "").strip()
    batch_number = request.POST.get("batch_number", "").strip()
    expiry_date_str = request.POST.get("expiry_date", "").strip()
    quantity_str = request.POST.get("quantity", "100").strip()
    tp_str = request.POST.get("purchase_price", "").strip()
    mrp_str = request.POST.get("unit_mrp", "").strip()
    challan_no = request.POST.get("challan_no", "").strip()
    drug_id = request.POST.get("drug_id", "").strip()

    is_ajax = request.headers.get("HX-Request") or request.headers.get("accept") == "application/json" or request.POST.get("is_ajax") == "1"

    if not brand_name or not batch_number or not expiry_date_str:
        err_msg = "ঔষধের নাম, ব্যাচ নম্বর এবং মেয়াদোত্তীর্ণের তারিখ আবশ্যক!"
        if is_ajax:
            return JsonResponse({"status": "error", "message": err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect("inventory:dashboard")

    try:
        from datetime import datetime
        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        qty = int(quantity_str)
        
        # Drug lookup
        drug = None
        if drug_id:
            try:
                drug = BrandDrug.objects.filter(id=drug_id, is_active=True).first()
            except Exception:
                pass
        
        if not drug:
            drug = BrandDrug.objects.filter(brand_name__iexact=brand_name, is_active=True).first()

        if not drug:
            # Create a quick brand product in catalog if not found
            mfg, _ = Manufacturer.objects.get_or_create(name="General Pharma", defaults={"short_code": "GEN"})
            generic, _ = GenericDrug.objects.get_or_create(name="Standard Therapeutic Generic")
            dosage, _ = DosageForm.objects.get_or_create(name="Tablet", defaults={"short_name": "Tab"})
            
            unit_mrp = Decimal(mrp_str) if mrp_str else Decimal("10.00")
            unit_tp = Decimal(tp_str) if tp_str else (unit_mrp * Decimal("0.82")).quantize(Decimal("0.01"))
            
            drug = BrandDrug.objects.create(
                brand_name=brand_name,
                dosage_form=dosage,
                manufacturer=mfg,
                generic=generic,
                strength="Standard", 
                unit_mrp=unit_mrp,
                unit_tp=unit_tp,
                is_active=True
            )
        else:
            unit_mrp = Decimal(mrp_str) if mrp_str else drug.unit_mrp
            unit_tp = Decimal(tp_str) if tp_str else drug.unit_tp

        batch, created = DrugBatch.objects.get_or_create(
            drug=drug,
            batch_number=batch_number,
            tenant=tenant,
            defaults={
                "expiry_date": expiry_date,
                "purchase_price": unit_tp,
                "unit_mrp": unit_mrp,
                "initial_stock": qty,
                "current_stock": qty,
                "supplier_challan_no": challan_no,
            }
        )

        if not created:
            # Add to existing batch stock
            batch.current_stock += qty
            batch.save(update_fields=["current_stock", "updated_at"])

        # Audit movement
        StockMovement.objects.create(
            batch=batch,
            movement_type="PURCHASE",
            quantity=qty,
            balance_after=batch.current_stock,
            reference_id=challan_no or f"INWARD-{batch.id.hex[:6].upper()}",
            created_by=request.user.username if request.user.is_authenticated else "Pharmacist",
            notes=f"স্টক ইনওয়ার্ড (Supplier Challan: {challan_no})"
        )

        success_msg = f"'{drug.brand_name}' ব্যাচ {batch.batch_number} সফলভাবে {qty} পিস স্টক যুক্ত হয়েছে!"
        if is_ajax:
            return JsonResponse({
                "status": "success",
                "message": success_msg,
                "batch_id": str(batch.id),
                "brand_name": drug.brand_name,
                "current_stock": batch.current_stock,
            })

        messages.success(request, success_msg)
    except Exception as e:
        err_msg = f"স্টক যোগ করতে ত্রুটি: {e!s}"
        if is_ajax:
            return JsonResponse({"status": "error", "message": err_msg}, status=400)
        messages.error(request, err_msg)

    return redirect("inventory:dashboard")


@tenant_user_required
@require_GET
def drug_autocomplete_view(request):
    """
    High-speed JSON autocomplete endpoint for medicine catalog search during Stock In.
    """
    query = request.GET.get("q", "").strip()
    if not query:
        drugs = (
            BrandDrug.objects.filter(is_active=True)
            .select_related("generic", "manufacturer", "dosage_form")
            .order_by("brand_name")[:12]
        )
    else:
        drugs = (
            BrandDrug.objects.filter(
                Q(brand_name__icontains=query) |
                Q(generic__name__icontains=query) |
                Q(manufacturer__name__icontains=query),
                is_active=True
            )
            .select_related("generic", "manufacturer", "dosage_form")[:15]
        )

    results = []
    for d in drugs:
        dosage = d.dosage_form.short_name if d.dosage_form and d.dosage_form.short_name else (d.dosage_form.name if d.dosage_form else "")
        results.append({
            "id": str(d.id),
            "brand_name": d.brand_name,
            "strength": d.strength or "",
            "dosage_form": dosage,
            "manufacturer": d.manufacturer.name if d.manufacturer else "",
            "generic": d.generic.name if d.generic else "",
            "unit_mrp": str(d.unit_mrp),
            "unit_tp": str(d.unit_tp or (d.unit_mrp * Decimal("0.82")).quantize(Decimal("0.01"))),
        })

    return JsonResponse({"results": results})


@tenant_user_required
@require_GET
def stock_movement_history(request, batch_id):
    """
    Renders audit movements (Inward purchases, Outward POS sales, Adjustments) for a specific batch.
    """
    tenant = getattr(request, "tenant", None)
    qs = DrugBatch.objects.select_related("drug")
    if tenant:
        qs = qs.filter(tenant=tenant)
    batch = get_object_or_404(qs, id=batch_id)
    movements = batch.movements.all().order_by("-created_at")

    context = {
        "batch": batch,
        "movements": movements,
    }
    return render(request, "inventory/partials/movements_modal.html", context)
