from __future__ import annotations

import base64
import os
import sys

# Prevent OpenBLAS thread exhaustion
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# Prevent ascii encoding errors on Apache/Passenger stdout/stderr
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import logging
import re
from typing import Any, Dict, List, Optional

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import pytesseract
except ImportError:
    pytesseract = None
try:
    from thefuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from inventory.models import BrandDrug
from pos.gemini_service import GeminiAIService
from pos.training_service import DrugTrainingService
from pos.utils import decode_image_input, get_easyocr_reader

logger = logging.getLogger(__name__)

# Auto-configure Tesseract binary on Linux server if static binary is present
STATIC_TESS_BIN = "/home/webkoders/.local/bin/tesseract"
if os.path.exists(STATIC_TESS_BIN):
    pytesseract.pytesseract.tesseract_cmd = STATIC_TESS_BIN
    os.environ["TESSDATA_PREFIX"] = "/home/webkoders/tessdata"

STOP_WORDS = {
    "mfg", "lic", "dar", "no", "exp", "batch", "date", "mrp", "tk", "bdt",
    "tab", "cap", "mg", "ml", "capsule", "tablet", "pharma", "ltd", "plc",
    "price", "retail", "strip", "box", "rx", "only", "keep", "out", "reach",
    "for", "use", "usp", "bp", "g", "gm", "mcg", "store", "cool", "dry",
    "place", "protect", "light", "children"
}


def _safe_partial_ratio(s1: str, s2: str) -> int:
    if not s1 or not s2:
        return 0
    if fuzz is not None and hasattr(fuzz, 'partial_ratio'):
        try:
            return fuzz.partial_ratio(s1, s2)
        except Exception:
            pass
    import difflib
    return int(difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio() * 100)


def rank_drugs_with_multi_signal(clean_text: str, all_drugs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Intelligent Multi-Signal Drug Ranking Algorithm:
    - Eliminates false-positive 2-3 letter noise words (e.g. AX, APT, OR, TIE).
    - Multi-token brand prioritization (e.g. Entacyd Plus over Entacyd if combination evidence exists).
    - Chemical / Generic co-occurrence detection (e.g. Simethicone, Paracetamol).
    - Strength & Dosage form disambiguation (e.g. Chewable Tablet vs Suspension).
    """
    ocr_lower = clean_text.lower()
    ocr_tokens = set(re.findall(r"[a-zA-Z0-9]+", ocr_lower))
    scored_candidates = []

    for d in all_drugs:
        b_name = d["brand_name"]
        b_lower = b_name.lower().strip()
        b_tokens = [t for t in re.findall(r"[a-zA-Z0-9]+", b_lower) if len(t) >= 2]
        if not b_tokens:
            continue

        is_short_brand = len(b_lower) <= 3

        # 1. Brand Tokens Matching
        matched_tokens = 0
        exact_token_matches = 0
        for tok in b_tokens:
            if len(tok) <= 3:
                if tok in ocr_tokens:
                    exact_token_matches += 1
                    matched_tokens += 1
            else:
                if tok in ocr_tokens or tok in ocr_lower:
                    matched_tokens += 1
                    exact_token_matches += 1
                elif _safe_partial_ratio(tok, ocr_lower) >= 85:
                    matched_tokens += 0.85

        if matched_tokens == 0:
            continue

        brand_ratio = matched_tokens / len(b_tokens)
        brand_score = brand_ratio * 70.0

        # 2. Generic Chemical Score (0-35)
        gen_score = 0
        gen_name = (d.get("generic__name") or "").lower()
        if gen_name:
            for gen_part in re.findall(r"[a-zA-Z]{4,}", gen_name):
                if gen_part in ("acid", "sodium", "potassium", "chloride", "hydrochloride", "hydrate", "oral", "tablet"):
                    continue
                if gen_part in ocr_tokens or gen_part in ocr_lower:
                    gen_score += 15
                elif _safe_partial_ratio(gen_part, ocr_lower) >= 85:
                    gen_score += 10
        gen_score = min(35, gen_score)

        # 3. Strength Score (0-20)
        str_score = 0
        str_val = (d.get("strength") or "").lower()
        if str_val:
            str_nums = re.findall(r"\d+", str_val)
            for num in str_nums:
                if int(num) > 5 and (num in ocr_tokens or num in ocr_lower):
                    str_score += 8
        str_score = min(20, str_score)

        # 4. Dosage Form Score (0-15)
        form_score = 0
        form_val = (d.get("dosage_form__name") or "").lower()
        if form_val:
            for f_w in re.findall(r"[a-zA-Z]{4,}", form_val):
                if f_w in ocr_tokens or f_w in ocr_lower:
                    form_score += 8
                elif _safe_partial_ratio(f_w, ocr_lower) >= 85:
                    form_score += 5
        form_score = min(15, form_score)

        # 5. Combination Boost for Multi-token Brands
        combo_boost = 0
        if len(b_tokens) > 1 and exact_token_matches >= 1:
            if gen_score >= 15 or str_score >= 8:
                combo_boost = 25

        # Suppress noise for short names if no supporting chemical/strength matches
        if is_short_brand and (gen_score == 0 and str_score == 0):
            continue

        total_score = brand_score + gen_score + str_score + form_score + combo_boost
        if total_score >= 50:
            item_copy = dict(d)
            item_copy["name"] = item_copy["brand_name"]
            item_copy["price"] = float(item_copy["unit_mrp"])
            item_copy["dosage_form"] = item_copy.get("dosage_form__short_name") or item_copy.get("dosage_form__name") or "Tab"
            item_copy["generic_name"] = item_copy.get("generic__name") or "N/A"
            item_copy["manufacturer"] = item_copy.get("manufacturer__name") or "N/A"
            item_copy["score"] = round(total_score, 1)
            item_copy["ai_engine"] = "local"
            scored_candidates.append(item_copy)

    scored_candidates.sort(key=lambda x: x["score"], reverse=True)
    return scored_candidates


@csrf_exempt
def scan_medicine_ocr(request):
    """
    Enterprise Pharmacy POS Camera OCR Scanner:
    1. Decodes uploaded image (file or base64 canvas snapshot).
    2. Priority 1: Google Gemini Flash Vision Multimodal AI (if active).
    3. Priority 2: High-contrast Tesseract multi-pass & EasyOCR deep learning.
    4. Self-Learning: Checks user-taught custom aliases.
    5. Multi-Signal Composite Ranker with FEFO Batch & Stock enrichment.
    """
    if request.method != "POST":
        return JsonResponse({"status": "failed", "message": "শুধুমাত্র POST রিকোয়েস্ট গ্রহণযোগ্য"})

    image_file = request.FILES.get("image")
    image_data = request.POST.get("image_data", "").strip()

    if not image_file and not image_data:
        return JsonResponse({"status": "failed", "message": "ছবি পাওয়া যায়নি"})

    try:
        raw_bytes = None
        img = None
        if image_file:
            raw_bytes = image_file.read()
            file_bytes = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        elif image_data:
            header, img = decode_image_input(image_data)
            if img is not None:
                _, buf = cv2.imencode('.jpg', img)
                raw_bytes = buf.tobytes()

        if img is None or raw_bytes is None:
            return JsonResponse({"status": "failed", "message": "ভুল ইমেজ ফরম্যাট"})

        # ==============================================================
        # PRIORITY 1: Google Gemini Flash Vision Multimodal Engine
        # ==============================================================
        if GeminiAIService.is_gemini_active():
            try:
                gemini_res = GeminiAIService.analyze_medicine_image(raw_bytes)
                if gemini_res and (gemini_res.get("brand_name") or gemini_res.get("generic_name")):
                    gemini_matches = GeminiAIService.match_drug_from_gemini(gemini_res)
                    if gemini_matches:
                        primary_brand = gemini_matches[0]["brand_name"]
                        raw_summary = f"{gemini_res.get('brand_name', '')} {gemini_res.get('strength', '')} ({gemini_res.get('dosage_form', '')})".strip()
                        if request.headers.get("HX-Request") and request.POST.get("format") != "json":
                            return render(request, "pos/partials/camera_scan_results.html", {
                                "detected_drugs": gemini_matches[:6],
                                "primary_brand_name": primary_brand,
                                "raw_text": raw_summary,
                                "ai_engine": "gemini",
                            })
                        return JsonResponse({
                            "status": "success",
                            "medicine": gemini_matches[0],
                            "primary_brand_name": primary_brand,
                            "score": gemini_matches[0]["score"],
                            "raw_text": raw_summary,
                            "results": gemini_matches[:6],
                            "ai_engine": "gemini",
                        })
                    elif gemini_res.get("brand_name"):
                        primary_brand = gemini_res.get("brand_name").strip()
                        raw_summary = f"{primary_brand} {gemini_res.get('strength', '')} ({gemini_res.get('dosage_form', '')})".strip()
                        if request.headers.get("HX-Request") and request.POST.get("format") != "json":
                            return render(request, "pos/partials/camera_scan_results.html", {
                                "detected_drugs": [],
                                "primary_brand_name": primary_brand,
                                "raw_text": raw_summary,
                                "ai_engine": "gemini",
                            })
                        return JsonResponse({
                            "status": "partial",
                            "primary_brand_name": primary_brand,
                            "raw_text": raw_summary,
                            "results": [],
                            "ai_engine": "gemini",
                        })
            except Exception as gemini_err:
                logger.warning("Gemini Vision processing error: %s", gemini_err)

        # ==============================================================
        # PRIORITY 2: Local Enhanced Multi-Pass OCR Pipeline
        # (Proven accurate on foil strips, bottles, and packaging)
        # ==============================================================
        img_resized = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        extracted_text = ""

        # Pass 1: Raw color image with --psm 3
        try:
            extracted_text = pytesseract.image_to_string(img_resized, config='--psm 3 -l eng')
        except Exception as e1:
            logger.debug("Tesseract PSM 3 failed: %s", e1)

        # Pass 2: Grayscale with --psm 11
        if not extracted_text.strip():
            try:
                gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
                extracted_text = pytesseract.image_to_string(gray, config='--psm 11 -l eng')
            except Exception as e2:
                logger.debug("Tesseract PSM 11 grayscale failed: %s", e2)

        # Pass 3: Blue ink isolation (Red channel CLAHE + Adaptive Gaussian Thresholding)
        if not extracted_text.strip():
            try:
                _, _, r_channel = cv2.split(img_resized)
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                contrast_red = clahe.apply(r_channel)
                denoised = cv2.medianBlur(contrast_red, 3)
                thresh = cv2.adaptiveThreshold(
                    denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
                )
                if np.mean(thresh) < 127:
                    thresh = cv2.bitwise_not(thresh)
                extracted_text = pytesseract.image_to_string(thresh, config='--psm 11 -l eng')
            except Exception as e3:
                logger.debug("Tesseract threshold preprocessing failed: %s", e3)

        # Pass 4: EasyOCR deep learning model (fallback)
        if not extracted_text.strip():
            try:
                reader = get_easyocr_reader()
                if reader:
                    easy_res = reader.readtext(img_resized, detail=0)
                    extracted_text = " ".join(easy_res)
            except Exception as e4:
                logger.debug("EasyOCR fallback failed: %s", e4)

        clean_text = extracted_text.strip()
        safe_log_text = clean_text.encode('ascii', errors='backslashreplace').decode('ascii')
        logger.info("Local OCR Extracted Text: %s", safe_log_text)

        if not clean_text:
            if request.headers.get("HX-Request") and request.POST.get("format") != "json":
                return render(request, "pos/partials/camera_scan_results.html", {
                    "detected_drugs": [],
                    "raw_text": "কোনো টেক্সট রিড করা যায়নি",
                    "ai_engine": "local",
                })
            return JsonResponse({
                "status": "failed",
                "message": "কোনো টেক্সট রিড করা যায়নি",
                "raw_text": ""
            })

        # Load active medicines from cache for fast access
        cache_key_meds = "pos:all_active_drugs_ocr_cache"
        medicines = cache.get(cache_key_meds)
        if not medicines:
            medicines = list(BrandDrug.objects.filter(is_active=True).values(
                'id', 'brand_name', 'unit_mrp', 'strength',
                'dosage_form__name', 'dosage_form__short_name',
                'generic__name', 'manufacturer__name'
            ))
            cache.set(cache_key_meds, medicines, 3600)

        # Check User Training / Custom Nicknames
        matched_items = []
        trained_brand = DrugTrainingService.find_match(clean_text)
        if not trained_brand:
            for l in clean_text.split('\n'):
                t_match = DrugTrainingService.find_match(l)
                if t_match:
                    trained_brand = t_match
                    break

        if trained_brand:
            trained_item = next((m for m in medicines if m['brand_name'].lower() == trained_brand.lower()), None)
            if trained_item:
                c = dict(trained_item)
                c['name'] = c['brand_name']
                c['price'] = float(c['unit_mrp'])
                c['dosage_form'] = c.get('dosage_form__short_name') or c.get('dosage_form__name') or 'Tab'
                c['generic_name'] = c.get('generic__name') or 'N/A'
                c['manufacturer'] = c.get('manufacturer__name') or 'N/A'
                c['score'] = 100
                c['ai_engine'] = 'trained'
                matched_items.append(c)

        # Multi-signal intelligent scoring (full accurate ranking)
        ranked_local = rank_drugs_with_multi_signal(clean_text, medicines)
        for rk in ranked_local:
            if not any(it['id'] == rk['id'] for it in matched_items):
                matched_items.append(rk)

        # Enrich with live FEFO batch in batch query (Zero N+1)
        top_drugs = []
        top_candidates = matched_items[:6]
        top_ids = [it['id'] for it in top_candidates]
        if top_ids:
            drug_objs = list(BrandDrug.objects.filter(id__in=top_ids).prefetch_related('batches'))
            drug_map = {d.id: d for d in drug_objs}
            for it in top_candidates:
                d_obj = drug_map.get(it['id'])
                if d_obj:
                    fefo = d_obj.batches.fefo().first() or d_obj.batches.order_by("-expiry_date").first()
                    it['total_stock'] = d_obj.total_stock
                    it['fefo_batch'] = {
                        "id": str(fefo.id) if fefo else None,
                        "batch_number": fefo.batch_number if fefo else "N/A",
                        "expiry_date": fefo.expiry_date.strftime("%Y-%m-%d") if fefo else "N/A",
                        "stock": fefo.current_stock if fefo else 0,
                    } if fefo else None
                    top_drugs.append(it)

        # HTMX partial response
        primary_brand = top_drugs[0]["brand_name"] if top_drugs else ""
        if request.headers.get("HX-Request") and request.POST.get("format") != "json":
            return render(request, "pos/partials/camera_scan_results.html", {
                "detected_drugs": top_drugs,
                "primary_brand_name": primary_brand,
                "raw_text": clean_text[:150],
                "ai_engine": "local",
            })

        # JSON response
        if top_drugs:
            best_drug = top_drugs[0]
            return JsonResponse({
                "status": "success",
                "medicine": best_drug,
                "primary_brand_name": primary_brand,
                "score": best_drug.get("score", 100),
                "raw_text": clean_text,
                "results": top_drugs,
                "ai_engine": "local",
            })
        else:
            return JsonResponse({
                "status": "failed",
                "message": "ওষুধের ডাটাবেজে মিল খুঁজে পাওয়া যায়নি",
                "raw_text": clean_text,
            })

    except Exception as e:
        logger.exception("OCR error: %s", e)
        return JsonResponse({
            "status": "failed",
            "message": f"প্রসেসিং এরর: {str(e)}"
        })


# Backward compatible aliases
process_camera_scan_htmx = scan_medicine_ocr
