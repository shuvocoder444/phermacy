from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, F
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

    # Optimized single-query metrics calculation via SQL aggregation
    metrics = batch_qs.aggregate(
        total_batches=Count("id", filter=Q(current_stock__gt=0)),
        total_units=Sum("current_stock"),
        total_tp_value=Sum(F("current_stock") * F("purchase_price"), filter=Q(current_stock__gt=0)),
        total_mrp_value=Sum(F("current_stock") * F("unit_mrp"), filter=Q(current_stock__gt=0)),
        low_stock_count=Count("id", filter=Q(current_stock__gt=0, current_stock__lte=15)),
        expiring_soon_count=Count("id", filter=Q(current_stock__gt=0, expiry_date__gt=today, expiry_date__lte=expiry_60_days)),
        expired_count=Count("id", filter=Q(current_stock__gt=0, expiry_date__lte=today)),
    )
    total_batches = metrics["total_batches"] or 0
    total_units = metrics["total_units"] or 0
    total_tp_value = metrics["total_tp_value"] or Decimal("0.00")
    total_mrp_value = metrics["total_mrp_value"] or Decimal("0.00")
    low_stock_count = metrics["low_stock_count"] or 0
    expiring_soon_count = metrics["expiring_soon_count"] or 0
    expired_count = metrics["expired_count"] or 0

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
    batches = batch_qs.annotate(
        stock_value=F("current_stock") * F("unit_mrp")
    ).order_by("expiry_date")

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

    # Boosted link navigation also sends HX-Request, but needs the full page
    # so the sidebar and dashboard layout remain present after navigation.
    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
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
    catalog_scope = Q(tenant__isnull=True) | Q(tenant=tenant)
    
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
                drug = BrandDrug.objects.filter(catalog_scope, id=drug_id, is_active=True).first()
            except Exception:
                pass
        
        if not drug:
            drug = BrandDrug.objects.filter(catalog_scope, brand_name__iexact=brand_name, is_active=True).first()

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
                tenant=tenant,
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
    tenant = getattr(request, "tenant", None)
    catalog_scope = Q(tenant__isnull=True) | Q(tenant=tenant)
    if not query:
        drugs = (
            BrandDrug.objects.filter(catalog_scope, is_active=True)
            .select_related("generic", "manufacturer", "dosage_form")
            .order_by("brand_name")[:12]
        )
    else:
        drugs = (
            BrandDrug.objects.filter(
                catalog_scope,
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


import csv
import io
from django.http import HttpResponse


@tenant_user_required
def edit_batch_view(request, batch_id):
    """
    ব্যাচের তথ্য (স্টক সংখ্যা, ব্যাচ নম্বর, ক্রয়মূল্য, বিক্রয়মূল্য, মেয়াদ) এডিট করার অপশন।
    """
    tenant = getattr(request, "tenant", None)
    qs = DrugBatch.objects.select_related("drug", "drug__dosage_form", "drug__generic", "drug__manufacturer")
    if tenant:
        qs = qs.filter(tenant=tenant)
    batch = get_object_or_404(qs, id=batch_id)

    if request.method == "POST":
        try:
            batch_number = request.POST.get("batch_number", "").strip() or batch.batch_number
            stock_qty_str = request.POST.get("current_stock", "").strip()
            purchase_price_str = request.POST.get("purchase_price", "").strip()
            unit_mrp_str = request.POST.get("unit_mrp", "").strip()
            expiry_date_str = request.POST.get("expiry_date", "").strip()
            supplier_challan = request.POST.get("supplier_challan_no", "").strip()

            old_stock = batch.current_stock
            new_stock = int(stock_qty_str) if stock_qty_str else old_stock
            purchase_price = Decimal(purchase_price_str) if purchase_price_str else batch.purchase_price
            unit_mrp = Decimal(unit_mrp_str) if unit_mrp_str else batch.unit_mrp

            if expiry_date_str:
                from datetime import datetime
                try:
                    expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
                except ValueError:
                    expiry_date = batch.expiry_date
            else:
                expiry_date = batch.expiry_date

            batch.batch_number = batch_number
            batch.current_stock = max(0, new_stock)
            batch.purchase_price = purchase_price
            batch.unit_mrp = unit_mrp
            batch.expiry_date = expiry_date
            batch.supplier_challan_no = supplier_challan
            batch.save()

            if new_stock != old_stock:
                diff = new_stock - old_stock
                StockMovement.objects.create(
                    batch=batch,
                    movement_type="ADJUSTMENT",
                    quantity=abs(diff),
                    balance_after=batch.current_stock,
                    reference_id=f"ADJ-{batch.id.hex[:6].upper()}",
                    created_by=request.user.username if request.user.is_authenticated else "Pharmacist",
                    notes=f"স্টক সমন্বয়: পূর্ববর্তী স্টক ছিল {old_stock}, নতুন স্টক {new_stock} (পার্থক্য: {diff:+d})"
                )

            try:
                from django.core.cache import cache
                tenant_key = str(tenant.id) if tenant else "default_tenant"
                cache.delete(f"pos:all_active_drugs_ocr_cache:{tenant_key}")
            except Exception:
                pass

            messages.success(request, f"'{batch.drug.brand_name}' ব্যাচের তথ্য সফলভাবে আপডেট করা হয়েছে!")
            return redirect("inventory:dashboard")

        except Exception as e:
            messages.error(request, f"আপডেট করতে সমস্যা হয়েছে: {e!s}")
            return redirect("inventory:dashboard")

    context = {
        "batch": batch,
    }
    return render(request, "inventory/partials/edit_batch_modal.html", context)


@tenant_user_required
@require_POST
def delete_batch_view(request, batch_id):
    """
    স্টক থেকে একটি ব্যাচ ডিলিট বা নিরাপদভাবে নিষ্ক্রিয় করার ব্যাকএন্ড।
    """
    tenant = getattr(request, "tenant", None)
    qs = DrugBatch.objects.select_related("drug")
    if tenant:
        qs = qs.filter(tenant=tenant)
    batch = get_object_or_404(qs, id=batch_id)

    drug_name = batch.drug.brand_name
    batch_num = batch.batch_number

    try:
        if batch.sale_items.exists():
            batch.current_stock = 0
            batch.save(update_fields=["current_stock", "updated_at"])
            StockMovement.objects.create(
                batch=batch,
                movement_type="DAMAGE",
                quantity=0,
                balance_after=0,
                reference_id=f"DEL-{batch.id.hex[:6].upper()}",
                created_by=request.user.username if request.user.is_authenticated else "Pharmacist",
                notes="ব্যাচ ডিলিট: অতীত বিক্রয় রেকর্ড থাকায় স্টক শূন্য (০) করা হয়েছে।"
            )
            msg = f"'{drug_name}' (ব্যাচ: {batch_num}) অতীত বিক্রয় রেকর্ডের সাথে যুক্ত থাকায় স্টক শূন্য (০) করে নিষ্ক্রিয় করা হয়েছে।"
        else:
            batch.movements.all().delete()
            batch.delete()
            msg = f"'{drug_name}' (ব্যাচ: {batch_num}) সফলভাবে ডিলিট করা হয়েছে!"

        try:
            from django.core.cache import cache
            tenant_key = str(tenant.id) if tenant else "default_tenant"
            cache.delete(f"pos:all_active_drugs_ocr_cache:{tenant_key}")
        except Exception:
            pass

        messages.success(request, msg)
        return redirect("inventory:dashboard")

    except Exception as e:
        messages.error(request, f"ডিলিট করতে সমস্যা হয়েছে: {e!s}")
        return redirect("inventory:dashboard")


@tenant_user_required
def export_stock_csv_view(request):
    """
    সম্পূর্ণ ফার্মেসি স্টক এক্সেল / CSV ফরম্যাটে এক্সপোর্ট করে।
    """
    tenant = getattr(request, "tenant", None)
    today = timezone.now().date()

    batch_qs = DrugBatch.objects.select_related(
        "drug", "drug__manufacturer", "drug__generic", "drug__dosage_form"
    ).filter(current_stock__gt=0).order_by("drug__brand_name", "expiry_date")

    if tenant:
        batch_qs = batch_qs.filter(tenant=tenant)

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    filename = f"pharmacy_stock_{today.strftime('%Y%m%d')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "ক্রমিক",
        "ওষুধের নাম",
        "ডোজের ধরন",
        "পাওয়ার / শক্তি",
        "জেনেরিক নাম",
        "কোম্পানির নাম",
        "ব্যাচ নম্বর",
        "ক্রয়মূল্য (টাকা)",
        "বিক্রয়মূল্য (টাকা)",
        "মজুদ স্টক (পিস)",
        "মেয়াদের তারিখ (YYYY-MM-DD)",
        "চালান নম্বর",
    ])

    for idx, b in enumerate(batch_qs, start=1):
        d = b.drug
        form_name = d.dosage_form.name if d.dosage_form else "ট্যাবলেট"
        gen_name = d.generic.name if d.generic else "N/A"
        mfg_name = d.manufacturer.name if d.manufacturer else "N/A"
        writer.writerow([
            idx,
            d.brand_name,
            form_name,
            d.strength or "",
            gen_name,
            mfg_name,
            b.batch_number,
            f"{b.purchase_price:.2f}",
            f"{b.unit_mrp:.2f}",
            b.current_stock,
            b.expiry_date.strftime("%Y-%m-%d") if b.expiry_date else "",
            b.supplier_challan_no or "",
        ])

    return response


@tenant_user_required
def download_sample_stock_csv_view(request):
    """
    স্টক ইমপোর্টের জন্য স্যাম্পল ডেমো CSV ফাইল ডাউনলোড করার অপশন।
    """
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="sample_stock_import_template.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "ওষুধের নাম",
        "ডোজের ধরন",
        "পাওয়ার / শক্তি",
        "জেনেরিক নাম",
        "কোম্পানির নাম",
        "ব্যাচ নম্বর",
        "ক্রয়মূল্য",
        "বিক্রয়মূল্য",
        "মজুদ স্টক",
        "মেয়াদের তারিখ (YYYY-MM-DD)",
    ])
    writer.writerow([
        "Napa Extra", "ট্যাবলেট", "500 mg + 65 mg", "Paracetamol + Caffeine", "Beximco Pharmaceuticals Ltd.", "B26-001", "2.40", "3.00", "200", "2028-12-31"
    ])
    writer.writerow([
        "Seclo 20", "ক্যাপসুল", "20 mg", "Omeprazole", "Square Pharmaceuticals PLC", "B26-002", "5.60", "7.00", "150", "2028-06-30"
    ])
    writer.writerow([
        "Tusca", "সিরাপ", "100 ml", "Dextromethorphan + Guaifenesin", "Square Pharmaceuticals PLC", "B26-003", "75.00", "90.00", "30", "2027-10-15"
    ])
    return response


@tenant_user_required
@require_POST
def import_stock_csv_view(request):
    """
    CSV ফাইল থেকে একসাথে শত শত ওষুধের স্টক আপলোড / ইমপোর্ট করার প্রসেসর।
    """
    tenant = getattr(request, "tenant", None)
    csv_file = request.FILES.get("stock_file")

    if not csv_file:
        messages.error(request, "অনুগ্রহ করে একটি CSV ফাইল নির্বাচন করুন।")
        return redirect("inventory:dashboard")

    if not csv_file.name.endswith(".csv"):
        messages.error(request, "শুধুমাত্র .csv ফরম্যাটের ফাইল গ্রহণযোগ্য।")
        return redirect("inventory:dashboard")

    try:
        raw_data = csv_file.read()
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                decoded_file = raw_data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            decoded_file = raw_data.decode("utf-8", errors="replace")

        from datetime import datetime, date
        reader = csv.reader(io.StringIO(decoded_file))
        rows = list(reader)

        if not rows:
            messages.error(request, "CSV ফাইলটি খালি।")
            return redirect("inventory:dashboard")

        header = [h.strip().lower() for h in rows[0]]
        start_idx = 1 if any(w in "".join(header) for w in ["নাম", "name", "ব্যাচ", "batch", "মজুদ", "stock"]) else 0

        success_count = 0
        updated_count = 0
        errors_count = 0
        today = timezone.now().date()
        default_exp = today + timedelta(days=500)

        for row_idx, row in enumerate(rows[start_idx:], start=start_idx + 1):
            if not row or not any(cell.strip() for cell in row):
                continue

            try:
                b_name = row[0].strip() if len(row) > 0 else ""
                if not b_name:
                    continue

                form_val = row[1].strip() if len(row) > 1 and row[1].strip() else "ট্যাবলেট"
                strength_val = row[2].strip() if len(row) > 2 and row[2].strip() else "স্ট্যান্ডার্ড"
                generic_val = row[3].strip() if len(row) > 3 and row[3].strip() else "জেনেরিক"
                mfg_val = row[4].strip() if len(row) > 4 and row[4].strip() else "ফার্মা কোম্পানি"
                batch_val = row[5].strip() if len(row) > 5 and row[5].strip() else f"B26-{today.strftime('%y%m%d')}-{row_idx}"
                
                tp_val = Decimal(row[6].strip()) if len(row) > 6 and row[6].strip() else Decimal("0.00")
                mrp_val = Decimal(row[7].strip()) if len(row) > 7 and row[7].strip() else (tp_val * Decimal("1.20")).quantize(Decimal("0.01"))
                if mrp_val <= 0 and tp_val > 0:
                    mrp_val = (tp_val * Decimal("1.20")).quantize(Decimal("0.01"))
                if tp_val <= 0 and mrp_val > 0:
                    tp_val = (mrp_val * Decimal("0.82")).quantize(Decimal("0.01"))

                stock_val = int(Decimal(row[8].strip())) if len(row) > 8 and row[8].strip() else 0

                exp_str = row[9].strip() if len(row) > 9 and row[9].strip() else ""
                if exp_str:
                    try:
                        exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                    except ValueError:
                        try:
                            exp_date = datetime.strptime(exp_str, "%d/%m/%Y").date()
                        except ValueError:
                            exp_date = default_exp
                else:
                    exp_date = default_exp

                dosage, _ = DosageForm.objects.get_or_create(
                    name=form_val,
                    defaults={"short_name": form_val[:4]}
                )

                mfg, _ = Manufacturer.objects.get_or_create(
                    name=mfg_val,
                    defaults={"name_bn": mfg_val}
                )

                generic, _ = GenericDrug.objects.get_or_create(
                    name=generic_val,
                    defaults={"name_bn": generic_val}
                )

                drug = BrandDrug.objects.filter(
                    Q(tenant=tenant) | Q(tenant__isnull=True),
                    brand_name__iexact=b_name
                ).first()

                if not drug:
                    drug = BrandDrug.objects.create(
                        tenant=tenant,
                        brand_name=b_name,
                        brand_name_bn=b_name,
                        dosage_form=dosage,
                        manufacturer=mfg,
                        generic=generic,
                        strength=strength_val,
                        unit_mrp=mrp_val or Decimal("10.00"),
                        unit_tp=tp_val or Decimal("8.20"),
                        is_active=True
                    )

                batch, created = DrugBatch.objects.get_or_create(
                    drug=drug,
                    tenant=tenant,
                    batch_number=batch_val,
                    defaults={
                        "purchase_price": tp_val,
                        "unit_mrp": mrp_val,
                        "expiry_date": exp_date,
                        "initial_stock": stock_val,
                        "current_stock": stock_val,
                        "supplier_challan_no": f"IMPORT-{today.strftime('%y%m%d')}",
                    }
                )

                if created:
                    success_count += 1
                else:
                    batch.current_stock += stock_val
                    batch.purchase_price = tp_val
                    batch.unit_mrp = mrp_val
                    batch.expiry_date = exp_date
                    batch.save()
                    updated_count += 1

                StockMovement.objects.create(
                    batch=batch,
                    movement_type="PURCHASE",
                    quantity=stock_val,
                    balance_after=batch.current_stock,
                    reference_id=f"CSV-IMP-{row_idx}",
                    created_by=request.user.username if request.user.is_authenticated else "Pharmacist",
                    notes=f"CSV ফাইল থেকে স্টক ইমপোর্ট ({b_name}, ব্যাচ: {batch_val})"
                )

            except Exception as row_err:
                errors_count += 1
                continue

        try:
            from django.core.cache import cache
            tenant_key = str(tenant.id) if tenant else "default_tenant"
            cache.delete(f"pos:all_active_drugs_ocr_cache:{tenant_key}")
        except Exception:
            pass

        messages.success(request, f"স্টক ইমপোর্ট সফলভাবে সম্পন্ন হয়েছে! {success_count}টি নতুন ব্যাচ তৈরি হয়েছে, {updated_count}টি ব্যাচ আপডেট হয়েছে।")

    except Exception as e:
        messages.error(request, f"ফাইল প্রসেস করতে ত্রুটি: {e!s}")

    return redirect("inventory:dashboard")
