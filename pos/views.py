import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from inventory.models import BrandDrug, DrugBatch
from inventory.services import DrugSearchAndCacheService
from customers.models import Customer, DueLedger
from .models import Invoice, CashRegisterSession
from .cart import POSCartManager
from .services import POSCheckoutService, ThermalReceiptGenerator
from notifications.sms_services import BangladeshSMSGateway
from core.decorators import tenant_user_required


def get_cart_manager(request) -> POSCartManager:
    """Helper to retrieve or initialize tenant-scoped Redis cart."""
    if not request.session.session_key:
        request.session.create()
        request.session['cart_initialized'] = True  # Force session save to set cookie
    tenant_id = getattr(request, "tenant", None)
    tenant_key = str(tenant_id.id) if tenant_id and hasattr(tenant_id, "id") else "default_tenant"
    return POSCartManager(session_key=request.session.session_key, tenant_id=tenant_key)


@tenant_user_required
def pos_screen_view(request):
    """
    Main Point-of-Sale terminal view.
    Renders the lightning-fast single screen layout with Alpine.js keyboard listeners.
    """
    cart_manager = get_cart_manager(request)
    cart = cart_manager.get_cart_summary()
    
    tenant_id = getattr(request, "tenant", None)
    tenant_key = str(tenant_id.id) if tenant_id and hasattr(tenant_id, "id") else "default_tenant"
    
    # Pre-prime top drugs in background/cache if empty
    DrugSearchAndCacheService.prime_top_drugs_cache(tenant_id=tenant_key, limit=100)
    
    context = {
        "cart": cart,
        "today": timezone.now().date(),
        "store_name": getattr(tenant_id, "name", "Popular Pharmacy & Care"),
        "store_phone": getattr(tenant_id, "phone", "01711-000000"),
        "tenant": tenant_id,
        "subscription": getattr(tenant_id, "subscription", None) if tenant_id else None,
    }
    return render(request, "pos/pos.html", context)


@require_GET
def drug_search_htmx(request):
    """
    HTMX live search endpoint returning matched generic and brand products with FEFO batch stock.
    Triggered instantly on keyup (F2 / search box).
    """
    query = request.GET.get("q", "").strip()
    tenant_id = getattr(request, "tenant", None)
    tenant_key = str(tenant_id.id) if tenant_id and hasattr(tenant_id, "id") else "default_tenant"

    results = DrugSearchAndCacheService.search_drugs(query=query, tenant_id=tenant_key, limit=12)
    
    context = {
        "results": results,
        "query": query,
    }
    return render(request, "pos/partials/search_results.html", context)


@require_POST
def cart_add_htmx(request):
    """
    HTMX endpoint to add a medicine batch to the Redis cart.
    """
    batch_id = request.POST.get("batch_id")
    quantity = int(request.POST.get("quantity", 1))
    
    cart_manager = get_cart_manager(request)
    try:
        cart = cart_manager.add_item(batch_id=batch_id, quantity=quantity)
    except Exception as e:
        return HttpResponse(f"<div class='p-2 text-red-600 font-semibold'>Error: {str(e)}</div>", status=400)

    context = {"cart": cart, "is_htmx": True}
    return render(request, "pos/partials/cart_table.html", context)


@require_POST
def cart_update_quantity_htmx(request):
    """
    HTMX endpoint to increment/decrement/set quantity for a specific batch in cart.
    """
    batch_id = request.POST.get("batch_id")
    quantity = int(request.POST.get("quantity", 1))
    
    cart_manager = get_cart_manager(request)
    cart = cart_manager.update_quantity(batch_id=batch_id, quantity=quantity)
    
    context = {"cart": cart, "is_htmx": True}
    return render(request, "pos/partials/cart_table.html", context)


@require_POST
def cart_remove_item_htmx(request):
    """
    HTMX endpoint to delete an item row from the cart.
    """
    batch_id = request.POST.get("batch_id")
    cart_manager = get_cart_manager(request)
    cart = cart_manager.remove_item(batch_id=batch_id)
    
    context = {"cart": cart, "is_htmx": True}
    return render(request, "pos/partials/cart_table.html", context)


@require_POST
def cart_apply_discount_htmx(request):
    """
    HTMX endpoint to apply percentage or flat discount (F4 shortcut).
    """
    cart_manager = get_cart_manager(request)
    raw_percent = request.POST.get("discount_percent", "").strip() or "0.00"
    raw_flat = (request.POST.get("discount_flat", "") or request.POST.get("discount_amount", "")).strip() or "0.00"
    try:
        disc_percent = max(Decimal("0.00"), min(Decimal("100.00"), Decimal(raw_percent)))
    except Exception:
        disc_percent = Decimal("0.00")
    try:
        disc_flat = max(Decimal("0.00"), Decimal(raw_flat))
    except Exception:
        disc_flat = Decimal("0.00")
    
    cart = cart_manager.set_discount(discount_percent=disc_percent, discount_flat=disc_flat)
    context = {"cart": cart, "is_htmx": True}
    return render(request, "pos/partials/cart_table.html", context)


@require_POST
def cart_clear_htmx(request):
    """
    Clears the current active cart.
    """
    cart_manager = get_cart_manager(request)
    cart_manager.clear()
    cart = cart_manager.get_cart_summary()
    return render(request, "pos/partials/cart_table.html", {"cart": cart, "is_htmx": True})


@require_POST
def hold_cart_htmx(request):
    """
    Holds the current active cart in session and resets terminal for next customer.
    """
    import uuid
    cart_manager = get_cart_manager(request)
    cart = cart_manager.get_cart_summary()
    
    if cart["items"]:
        held_carts = request.session.get("held_carts", [])
        held_id = uuid.uuid4().hex[:6].upper()
        total_items = sum(int(it["quantity"]) for it in cart["items"])
        first_drug = cart["items"][0]["brand_name"]
        
        held_carts.append({
            "id": held_id,
            "title": f"{first_drug} + {total_items} টি",
            "time": timezone.now().strftime("%I:%M %p"),
            "total": cart["total_payable"],
            "items_count": total_items,
            "raw_data": cart_manager._get_raw_cart()
        })
        request.session["held_carts"] = held_carts
        request.session.modified = True
        cart_manager.clear()

    cart = cart_manager.get_cart_summary()
    return render(request, "pos/partials/cart_table.html", {"cart": cart, "is_htmx": True})


@require_GET
def held_carts_modal(request):
    """
    Displays list of suspended/held carts for instant resumption.
    """
    held_carts = request.session.get("held_carts", [])
    return render(request, "pos/partials/held_carts_modal.html", {"held_carts": held_carts})


@require_POST
def resume_cart_htmx(request, hold_id):
    """
    Resumes a specific held cart into the active POS cart.
    """
    held_carts = request.session.get("held_carts", [])
    target = None
    remaining = []
    for h in held_carts:
        if h["id"] == hold_id:
            target = h
        else:
            remaining.append(h)

    cart_manager = get_cart_manager(request)
    if target:
        request.session["held_carts"] = remaining
        request.session.modified = True
        cart_manager._save_raw_cart(target["raw_data"])

    cart = cart_manager.get_cart_summary()
    return render(request, "pos/partials/cart_table.html", {"cart": cart, "is_htmx": True})


@require_GET
def checkout_modal_htmx(request):
    """
    Renders the checkout tender modal with payment methods (Cash, bKash, Nagad, Rocket, Due).
    """
    cart_manager = get_cart_manager(request)
    cart = cart_manager.get_cart_summary()
    tenant = getattr(request, "tenant", None)
    
    # Search or pass customer
    customer_phone = request.GET.get("phone", "").strip()
    customer = None
    if customer_phone:
        cust_qs = Customer.objects.filter(phone=customer_phone)
        if tenant:
            cust_qs = cust_qs.filter(tenant=tenant)
        customer = cust_qs.first()

    context = {
        "cart": cart,
        "customer": customer,
        "total_payable": cart["total_payable"],
    }
    return render(request, "pos/partials/checkout_modal.html", context)


@tenant_user_required
@require_POST
def checkout_submit_htmx(request):
    """
    Executes the final sale checkout, writes invoice, deducts FEFO stock,
    and returns receipt modal with auto-print script.
    """
    cart_manager = get_cart_manager(request)
    tenant = getattr(request, "tenant", None)
    
    payment_method = request.POST.get("payment_method", "CASH")
    paid_amount = Decimal(request.POST.get("paid_amount", "0.00") or "0.00")
    customer_id = request.POST.get("customer_id") or None
    customer_name = request.POST.get("customer_name", "Walk-in Customer")
    customer_phone = request.POST.get("customer_phone", "").strip()
    gateway_trx_id = request.POST.get("gateway_trx_id", "").strip()
    doctor_name = request.POST.get("doctor_name", "").strip()

    # Cashier
    cashier = request.user if request.user.is_authenticated else None
    if not cashier:
        from django.contrib.auth.models import User
        cashier, _ = User.objects.get_or_create(username="cashier_demo", defaults={"first_name": "Demo Cashier"})

    try:
        invoice, summary = POSCheckoutService.process_checkout(
            cart_manager=cart_manager,
            cashier=cashier,
            payment_method=payment_method,
            paid_amount=paid_amount,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            gateway_trx_id=gateway_trx_id,
            doctor_name=doctor_name,
            tenant=tenant,
        )

        # Dispatch optional SMS confirmation
        if customer_phone:
            tenant_name = getattr(tenant, "name", "Pharmacy Care") if tenant else "Pharmacy Care"
            BangladeshSMSGateway.send_invoice_sms(
                customer_phone=customer_phone,
                invoice_number=invoice.invoice_number,
                total_payable=str(invoice.total_payable),
                due_amount=str(invoice.due_amount),
                pharmacy_name=tenant_name,
            )

        context = {
            "invoice": invoice,
            "items": invoice.items.select_related("drug", "batch").all(),
            "summary": summary,
        }
        return render(request, "pos/partials/receipt_modal.html", context)

    except Exception as e:
        return HttpResponse(
            f"""<div class="p-4 bg-red-100 border-l-4 border-red-500 text-red-700">
                <p class="font-bold">Checkout Error</p>
                <p>{str(e)}</p>
            </div>""",
            status=400
        )


@tenant_user_required
@require_GET
def print_thermal_receipt(request, invoice_id):
    """
    Renders the dedicated 80mm/58mm thermal receipt page for browser or ESC/POS print dialog.
    """
    tenant = getattr(request, "tenant", None)
    invoice_qs = Invoice.objects.select_related("cashier", "customer")
    if tenant and not (request.user.is_authenticated and request.user.is_superuser):
        invoice_qs = invoice_qs.filter(tenant=tenant)
    invoice = get_object_or_404(invoice_qs, id=invoice_id)
    items = invoice.items.select_related("drug", "batch").all()
    
    store_name = getattr(tenant, "name", "Popular Pharmacy & Health Care")
    store_phone = getattr(tenant, "phone", "01712-345678")
    store_address = getattr(tenant, "address", "Dhanmondi, Dhaka-1209")
    vat_reg = getattr(tenant, "vat_reg_number", "BIN-123456789")

    context = {
        "invoice": invoice,
        "items": items,
        "store_name": store_name,
        "store_phone": store_phone,
        "store_address": store_address,
        "vat_reg": vat_reg,
    }
    return render(request, "pos/thermal_receipt_80mm.html", context)


@tenant_user_required
@require_GET
def recent_invoices_modal(request):
    """
    Renders recent invoices modal for 1-click reprint, view, and audit on the POS terminal.
    """
    tenant = getattr(request, "tenant", None)
    invoices = Invoice.objects.select_related("customer", "cashier")
    if tenant:
        invoices = invoices.filter(tenant=tenant)
    invoices = invoices.order_by("-created_at")[:20]
    
    context = {"invoices": invoices}
    return render(request, "pos/partials/recent_invoices_modal.html", context)


@require_POST
def add_custom_drug_and_batch_htmx(request):
    """
    Instantly registers a newly typed medicine and its FEFO batch, 
    and automatically adds it to the active POS cart.
    """
    import random
    from datetime import timedelta
    from inventory.models import DosageForm, Manufacturer, GenericDrug

    brand_name = request.POST.get("brand_name", "").strip()
    brand_name_bn = request.POST.get("brand_name_bn", "").strip()
    dosage_form_name = request.POST.get("dosage_form", "Tablet").strip() or "Tablet"
    generic_name = request.POST.get("generic_name", "Standard Generic").strip() or "Standard Generic"
    mfg_name = request.POST.get("manufacturer", "Square Pharmaceuticals PLC").strip() or "Square Pharmaceuticals PLC"
    strength = request.POST.get("strength", "500 mg").strip() or "500 mg"
    
    mrp_str = request.POST.get("unit_mrp", "10.00").strip() or "10.00"
    tp_str = request.POST.get("purchase_price", "").strip()
    stock_qty_str = request.POST.get("initial_stock", "100").strip() or "100"
    rack_location = request.POST.get("rack_location", "A1-01").strip() or "A1-01"
    exp_date_str = request.POST.get("expiry_date", "").strip()

    if not brand_name:
        return HttpResponse("<div class='p-3 bg-rose-50 text-rose-700 text-xs font-bold rounded-xl'>ঔষধের নাম প্রদান আবশ্যক!</div>", status=400)

    try:
        unit_mrp = Decimal(mrp_str)
        unit_tp = Decimal(tp_str) if tp_str else (unit_mrp * Decimal("0.82")).quantize(Decimal("0.01"))
        stock_qty = int(stock_qty_str)
    except Exception:
        unit_mrp = Decimal("10.00")
        unit_tp = Decimal("8.20")
        stock_qty = 100

    today = timezone.now().date()
    if exp_date_str:
        try:
            from datetime import datetime
            expiry_date = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
        except Exception:
            expiry_date = today + timedelta(days=500)
    else:
        expiry_date = today + timedelta(days=500)

    # 1. DosageForm
    dosage_form, _ = DosageForm.objects.get_or_create(
        name=dosage_form_name,
        defaults={"name_bn": dosage_form_name, "short_name": dosage_form_name[:4]}
    )

    # 2. Manufacturer
    manufacturer, _ = Manufacturer.objects.get_or_create(
        name=mfg_name,
        defaults={"name_bn": mfg_name, "short_code": mfg_name[:3].upper()}
    )

    # 3. GenericDrug
    generic, _ = GenericDrug.objects.get_or_create(
        name=generic_name,
        defaults={"name_bn": generic_name, "therapeutic_class": "General Therapeutics"}
    )

    # 4. BrandDrug
    drug, _ = BrandDrug.objects.get_or_create(
        brand_name=brand_name,
        strength=strength,
        defaults={
            "brand_name_bn": brand_name_bn or brand_name,
            "dosage_form": dosage_form,
            "manufacturer": manufacturer,
            "generic": generic,
            "unit_mrp": unit_mrp,
            "unit_tp": unit_tp,
            "rack_location": rack_location,
            "is_active": True,
        }
    )

    # 5. Create FEFO DrugBatch
    tenant = getattr(request, "tenant", None)
    batch_num = f"B26-{drug.brand_name[:3].upper()}-{random.randint(1000, 9999)}"
    batch, _ = DrugBatch.objects.get_or_create(
        drug=drug,
        batch_number=batch_num,
        tenant=tenant,
        defaults={
            "manufacturing_date": today - timedelta(days=30),
            "expiry_date": expiry_date,
            "purchase_price": unit_tp,
            "unit_mrp": unit_mrp,
            "initial_stock": stock_qty,
            "current_stock": stock_qty,
        }
    )

    # 6. Automatically add 1 unit to POS cart
    cart_manager = get_cart_manager(request)
    cart = cart_manager.add_item(batch_id=str(batch.id), quantity=1)

    context = {
        "cart": cart,
        "is_htmx": True,
        "voice_success": {
            "medicine": drug.brand_name,
            "quantity": 1
        }
    }
    return render(request, "pos/partials/cart_table.html", context)


# Backward compatibility exports
from .ocr_service import scan_medicine_ocr, process_camera_scan_htmx
from .voice_service import voice_medicine_search, voice_add_to_cart_htmx


@csrf_exempt
@require_POST
def train_medicine_alias_view(request):
    """
    Endpoint allowing users to train custom voice pronunciations and OCR nicknames.
    """
    alias = request.POST.get("alias", "").strip()
    brand_name = request.POST.get("brand_name", "").strip()

    if not alias or not brand_name:
        return JsonResponse({"status": "failed", "message": "উচ্চারণ/নাম এবং ওষুধের নাম উভয়ই আবশ্যক।"}, status=400)

    from pos.training_service import DrugTrainingService
    success = DrugTrainingService.save_trained_alias(alias_phrase=alias, brand_name=brand_name)
    if success:
        return JsonResponse({
            "status": "success",
            "message": f"'{alias}' সফলভাবে '{brand_name}' হিসেবে সফটওয়্যারকে শেখানো হয়েছে!",
            "alias": alias,
            "brand_name": brand_name
        })
    return JsonResponse({"status": "failed", "message": "সংরক্ষণ করা যায়নি।"}, status=500)


@csrf_exempt
def ai_config_view(request):
    """
    GET: Returns current AI engine status and masked API key.
    POST: Saves new Gemini API key and preferred engine.
    """
    from pos.gemini_service import GeminiAIService
    
    if request.method == "POST":
        api_key = request.POST.get("gemini_api_key", "").strip()
        enabled = request.POST.get("enabled", "true").lower() in ("true", "1", "yes")
        preferred_engine = request.POST.get("preferred_engine", "gemini").strip()

        success = GeminiAIService.save_config(api_key=api_key, enabled=enabled, preferred_engine=preferred_engine)
        if success:
            return JsonResponse({
                "status": "success",
                "message": "AI সেটিংস সফলভাবে সংরক্ষণ করা হয়েছে!",
                "is_active": GeminiAIService.is_gemini_active(),
            })
        return JsonResponse({"status": "failed", "message": "সংরক্ষণ ব্যর্থ হয়েছে।"}, status=500)

    # GET
    config = GeminiAIService.get_config()
    key = config.get("gemini_api_key", "")
    masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else ("সংযুক্ত" if key else "নেই")
    
    return JsonResponse({
        "status": "success",
        "has_key": bool(key),
        "masked_key": masked_key,
        "is_active": GeminiAIService.is_gemini_active(),
        "preferred_engine": config.get("preferred_engine", "gemini"),
    })


@csrf_exempt
@require_POST
def test_gemini_connection_view(request):
    """
    Tests Gemini API connection with provided key or saved key.
    """
    from pos.gemini_service import GeminiAIService
    api_key = request.POST.get("gemini_api_key", "").strip()
    success, msg = GeminiAIService.test_gemini_connection(api_key=api_key)
    return JsonResponse({
        "status": "success" if success else "failed",
        "message": msg,
    })
