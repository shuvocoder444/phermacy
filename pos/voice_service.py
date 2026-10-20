from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import logging
import re

from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from inventory.models import BrandDrug
from inventory.services import DrugSearchAndCacheService
from pos.cart import POSCartManager
from pos.utils import (
    rank_phonetic_matches,
    transliterate_bangla_to_phonetic,
)


def _get_cart_manager(request) -> POSCartManager:
    if not request.session.session_key:
        request.session.create()
        request.session['cart_initialized'] = True
    tenant_id = getattr(request, "tenant", None)
    tenant_key = str(tenant_id.id) if tenant_id and hasattr(tenant_id, "id") else "default_tenant"
    return POSCartManager(session_key=request.session.session_key, tenant_id=tenant_key)

logger = logging.getLogger(__name__)

BANGLA_DIGITS_TRANS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

QUANTITY_WORDS_BN = {
    "এক": 1, "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5, "ছয়": 6, "সাত": 7, "আট": 8, "নয়": 9, "দশ": 10,
    "এগারো": 11, "বারো": 12, "তেরো": 13, "চৌদ্দ": 14, "পনেরো": 15, "বিশ": 20, "ত্রিশ": 30, "চল্লিশ": 40, "পঞ্চাশ": 50,
    "একশ": 100, "একশো": 100,
}


DOSAGE_FORM_MAP = {
    "সিরাপ": "Syrup", "syrup": "Syrup", "সাপ": "Syrup", "sirap": "Syrup",
    "সাসপেনশন": "Suspension", "suspension": "Suspension", "susp": "Suspension",
    "ট্যাবলেট": "Tablet", "ট্যাব": "Tablet", "tablet": "Tablet", "tab": "Tablet", "tabs": "Tablet",
    "ক্যাপসুল": "Capsule", "ক্যাপ": "Capsule", "capsule": "Capsule", "cap": "Capsule", "caps": "Capsule",
    "ড্রপ": "Drops", "ড্রপস": "Drops", "drop": "Drops", "drops": "Drops", "pediatric drops": "Pediatric Drops",
    "সাপোজিটরি": "Suppository", "সাফোজিটরি": "Suppository", "suppository": "Suppository",
    "ইনজেকশন": "Injection", "injection": "Injection", "inj": "Injection",
    "ইনফিউশন": "Infusion", "infusion": "Infusion",
    "মলম": "Ointment", "ক্রিম": "Cream", "cream": "Cream", "ointment": "Ointment", "জেল": "Gel", "gel": "Gel",
}


def parse_voice_command(text: str) -> tuple[str, Optional[str], int]:
    """
    Intelligently extracts (medicine_query, requested_dosage_form, quantity) from spoken Bangla / English.
    Example: 'নাপা সিরাপ ১০টা' -> ('নাপা', 'Syrup', 10)
             'napa 10' -> ('napa', None, 10)
    """
    raw = text.strip()
    if not raw:
        return "", None, 1

    # Convert Bangla digits to standard digits
    text_normalized = raw.translate(BANGLA_DIGITS_TRANS)
    extracted_qty = 1

    # 1. Look for explicit quantity patterns with suffix
    qty_suffix_match = re.search(
        r'(\d+)\s*(টা|টি|পিস|পাতা|স্ট্রিপ|বক্স|বটম|ফাইল|ta|ti|pcs|pc|piece|pieces|strip|strips|pata|box|boxes)(?!\w)',
        text_normalized,
        re.IGNORECASE
    )
    if qty_suffix_match:
        qty_num = int(qty_suffix_match.group(1))
        unit = qty_suffix_match.group(2).lower()
        multiplier = 10 if unit in ("পাতা", "স্ট্রিপ", "strip", "strips", "pata") else (100 if unit in ("বক্স", "box", "boxes") else 1)
        extracted_qty = max(1, qty_num * multiplier)
        query_text = text_normalized[:qty_suffix_match.start()] + " " + text_normalized[qty_suffix_match.end():]
    else:
        # 2. Look for word quantity
        word_found = False
        query_text = text_normalized
        for w_bn, val in QUANTITY_WORDS_BN.items():
            pattern = rf'{w_bn}\s*(টা|টি|পিস|পাতা|স্ট্রিপ|বক্স)?(?!\w)'
            if re.search(pattern, query_text):
                multiplier = 10 if ("পাতা" in query_text or "স্ট্রিপ" in query_text) else 1
                extracted_qty = max(1, val * multiplier)
                query_text = re.sub(pattern, '', query_text).strip()
                word_found = True
                break

        # 3. Standalone trailing count
        if not word_found:
            end_num_match = re.search(r'\s+(\d{1,3})$', text_normalized)
            if end_num_match:
                cand_qty = int(end_num_match.group(1))
                cand_query = text_normalized[:end_num_match.start()].strip()
                if cand_qty in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 15, 20, 24, 28, 30, 50, 100) and len(cand_query) >= 3:
                    extracted_qty = cand_qty
                    query_text = cand_query

    # 4. Detect and Extract Requested Dosage Form (e.g. সিরাপ, ট্যাবলেট, ড্রপ)
    requested_dosage_form = None
    query_words = query_text.lower().split()
    remaining_words = []
    for w in query_words:
        w_clean = re.sub(r'[^\w\u0980-\u09FF]', '', w)
        if w_clean in DOSAGE_FORM_MAP and not requested_dosage_form:
            requested_dosage_form = DOSAGE_FORM_MAP[w_clean]
        else:
            remaining_words.append(w)

    query_text = " ".join(remaining_words)

    # 5. Clean common conversational filler words
    cleaned_query = re.sub(
        r'\b(দাও|এড কর|এড করুন|এড করো|এড|যোগ কর|দিয়ে দেন|লাগবে|দেখা|give|add|please|take|cart)\b',
        '',
        query_text,
        flags=re.IGNORECASE
    ).strip()
    cleaned_query = re.sub(r'[^\w\s\-\+\.\u0980-\u09FF]', '', cleaned_query).strip()

    return cleaned_query or text_normalized, requested_dosage_form, max(1, extracted_qty)


def get_all_active_brands_cached() -> list[str]:
    """Fetches list of active brand names cached in memory."""
    cache_key = "pos:all_active_brand_names"
    brands = cache.get(cache_key)
    if not brands:
        brands = list(
            BrandDrug.objects.filter(is_active=True)
            .values_list("brand_name", flat=True)
        )
        cache.set(cache_key, brands, 3600)
    return brands


def _find_best_variant_for_form(brand_name: str, requested_form: Optional[str]) -> Optional[BrandDrug]:
    """
    Finds the exact matching drug variant for a brand by requested dosage form (e.g. Syrup vs Tablet).
    """
    candidates = list(BrandDrug.objects.filter(brand_name__iexact=brand_name, is_active=True))
    if not candidates:
        candidates = list(BrandDrug.objects.filter(brand_name__icontains=brand_name, is_active=True))
    if not candidates:
        return None

    if requested_form:
        for c in candidates:
            f_name = ((c.dosage_form.name if c.dosage_form else "") or "").lower()
            f_short = ((c.dosage_form.short_name if c.dosage_form else "") or "").lower()
            if requested_form.lower() in f_name or requested_form.lower() in f_short:
                return c

    # Fallback to candidate with stock or first candidate
    for c in candidates:
        if c.total_stock > 0:
            return c
    return candidates[0]


@csrf_exempt
@require_POST
def voice_medicine_search(request):
    """
    Processes spoken medicine commands with intelligent dosage form disambiguation:
    - Distinguishes 'নাপা সিরাপ' (Napa Syrup) from 'নাপা' (Napa Tablet).
    - Checks User-Taught Aliases -> Gemini Multimodal AI -> Indexed Search -> Phonetic Ranking.
    - Adds matched batch to Redis cart automatically.
    """
    transcript = request.POST.get("transcript", "").strip()
    if not transcript:
        if request.POST.get("format") == "json" or "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({"status": "error", "message": "Empty voice transcript"}, status=400)
        return HttpResponse("<div class='p-2 text-amber-400'>কোন ভয়েস ইনপুট পাওয়া যায়নি।</div>", status=400)

    drug_query, requested_form, quantity = parse_voice_command(transcript)
    if not drug_query:
        drug_query = transcript

    tenant_id = getattr(request, "tenant", None)
    tenant_key = str(tenant_id.id) if tenant_id and hasattr(tenant_id, "id") else "default_tenant"

    matched_drug = None
    batch_id = None
    matched_brand_name = ""

    # ==============================================================
    # STEP 1: Ultra-Fast O(1) Trained Aliases & Built-in Dictionary (<1ms)
    # ==============================================================
    from pos.gemini_service import GeminiAIService
    from pos.training_service import DrugTrainingService

    trained_brand = DrugTrainingService.find_match(drug_query)
    if trained_brand:
        trained_drug = _find_best_variant_for_form(trained_brand, requested_form)
        if trained_drug:
            matched_drug = trained_drug
            matched_brand_name = trained_drug.brand_name
            fefo_b = trained_drug.batches.fefo().first() or trained_drug.batches.order_by("-expiry_date").first()
            if fefo_b:
                batch_id = str(fefo_b.id)

    # ==============================================================
    # STEP 2: Instant Transliteration Match (e.g. 'সারজেল' -> 'Sergel') (<2ms)
    # ==============================================================
    if not matched_drug:
        trans_query = transliterate_bangla_to_phonetic(drug_query).strip()
        if trans_query and len(trans_query) >= 2:
            trans_drug = _find_best_variant_for_form(trans_query, requested_form)
            if trans_drug:
                matched_drug = trans_drug
                matched_brand_name = trans_drug.brand_name
                fefo_t = trans_drug.batches.fefo().first() or trans_drug.batches.order_by("-expiry_date").first()
                if fefo_t:
                    batch_id = str(fefo_t.id)

    # ==============================================================
    # STEP 3: Cached / Indexed Drug Search (<5ms)
    # ==============================================================
    if not matched_drug:
        search_query = trans_query if (trans_query and len(trans_query) >= 3) else drug_query
        search_results = DrugSearchAndCacheService.search_drugs(query=search_query, tenant_id=tenant_key, limit=6)
        if search_results:
            target_dict = search_results[0]
            if requested_form:
                for res in search_results:
                    res_form = (res.get("dosage_form") or res.get("dosage_form_full") or "").lower()
                    if requested_form.lower() in res_form:
                        target_dict = res
                        break
            if target_dict.get("fefo_batch"):
                batch_id = target_dict["fefo_batch"]["id"]
                matched_brand_name = target_dict["brand_name"]
                matched_drug = BrandDrug.objects.filter(id=target_dict["id"]).first()

    # ==============================================================
    # STEP 4: Direct DB Prefix & Contains Query with Batch Prefetch
    # ==============================================================
    if not matched_drug:
        cand_qs = BrandDrug.objects.filter(
            Q(brand_name__istartswith=drug_query)
            | Q(brand_name__istartswith=trans_query)
            | Q(brand_name__icontains=drug_query)
            | Q(brand_name__icontains=trans_query),
            is_active=True
        ).prefetch_related('batches')
        if cand_qs.exists():
            matched_drug = _find_best_variant_for_form(cand_qs.first().brand_name, requested_form)
            if matched_drug:
                matched_brand_name = matched_drug.brand_name
                fefo_b = matched_drug.batches.fefo().first() or matched_drug.batches.order_by("-expiry_date").first()
                if fefo_b:
                    batch_id = str(fefo_b.id)

    # ==============================================================
    # STEP 5: Gemini AI Multimodal Voice Parser (Advanced Fallback Only)
    # ==============================================================
    if not matched_drug and GeminiAIService.is_gemini_active():
        try:
            gemini_voice_items = GeminiAIService.parse_voice_transcript(transcript)
            if gemini_voice_items and isinstance(gemini_voice_items, list):
                first_item = gemini_voice_items[0]
                g_brand = (first_item.get("brand_name") or "").strip()
                g_qty = int(first_item.get("quantity") or quantity)
                g_form = (first_item.get("dosage_form") or requested_form or "").strip()

                if g_brand:
                    best_g = _find_best_variant_for_form(g_brand, g_form)
                    if best_g:
                        fefo_g = best_g.batches.fefo().first() or best_g.batches.order_by("-expiry_date").first()
                        if fefo_g:
                            matched_drug = best_g
                            matched_brand_name = best_g.brand_name
                            batch_id = str(fefo_g.id)
                            quantity = g_qty
        except Exception as g_err:
            logger.warning("Gemini voice parse error: %s", g_err)

    # JSON response mode
    if request.POST.get("format") == "json" or "application/json" in request.headers.get("Accept", ""):
        if matched_drug:
            fefo = matched_drug.batches.fefo().first()
            return JsonResponse({
                "status": "success",
                "matched_medicine": matched_drug.brand_name,
                "generic": matched_drug.generic.name if matched_drug.generic else "N/A",
                "strength": matched_drug.strength or "",
                "quantity": quantity,
                "batch_id": batch_id,
                "stock": fefo.current_stock if fefo else 0,
                "unit_mrp": str(matched_drug.unit_mrp),
            })
        return JsonResponse({"status": "not_found", "query": drug_query}, status=404)

    # Cart HTML partial mode
    if not batch_id:
        return HttpResponse(
            f"""<div class="p-3 bg-rose-900/60 border border-rose-500 rounded-xl text-rose-200 text-xs flex items-center justify-between">
                <span>❌ "{drug_query}" ঔষধটি ডাটাবেসে পাওয়া যায়নি বা পর্যাপ্ত স্টক নেই।</span>
            </div>""",
            status=404
        )

    # Add to Cart
    cart_manager = _get_cart_manager(request)
    cart = cart_manager.add_item(batch_id=batch_id, quantity=quantity)

    # Return updated cart table HTML partial
    disp_name = matched_brand_name
    if matched_drug and matched_drug.dosage_form:
        form_label = matched_drug.dosage_form.short_name or matched_drug.dosage_form.name
        disp_name = f"{matched_brand_name} {form_label}"

    context = {
        "cart": cart,
        "voice_success": {
            "medicine": disp_name,
            "quantity": quantity,
            "transcript": transcript,
        }
    }
    return render(request, "pos/partials/cart_table.html", context)


# Backward-compatible alias
voice_add_to_cart_htmx = voice_medicine_search
