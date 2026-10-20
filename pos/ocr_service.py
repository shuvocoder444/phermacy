from __future__ import annotations

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
import shutil
from typing import Any

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
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from core.decorators import tenant_user_required

from inventory.models import BrandDrug
from pos.gemini_service import GeminiAIService
from pos.training_service import DrugTrainingService
from pos.utils import decode_image_input, get_easyocr_reader

logger = logging.getLogger(__name__)

# Auto-configure Tesseract binary on Linux server if static binary is present
STATIC_TESS_BIN = "/home/webkoders/.local/bin/tesseract"
WINDOWS_TESS_BIN = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if pytesseract is not None and os.path.exists(STATIC_TESS_BIN):
    pytesseract.pytesseract.tesseract_cmd = STATIC_TESS_BIN
    os.environ["TESSDATA_PREFIX"] = "/home/webkoders/tessdata"
elif pytesseract is not None and os.path.exists(WINDOWS_TESS_BIN):
    pytesseract.pytesseract.tesseract_cmd = WINDOWS_TESS_BIN

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


def _tesseract_available() -> bool:
    if pytesseract is None:
        return False
    command = str(getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract"))
    return os.path.isfile(command) if os.path.dirname(command) else shutil.which(command) is not None


def _read_large_text(image, config: str) -> str:
    """Keep prominent, confident text and discard packaging fine print."""
    data = pytesseract.image_to_data(
        image, config=config, output_type=pytesseract.Output.DICT
    )
    min_height = max(14, round(image.shape[0] * 0.008))
    lines = {}
    for i, word in enumerate(data.get("text", [])):
        word = word.strip()
        try:
            height = int(data["height"][i])
            confidence = float(data["conf"][i])
        except (KeyError, ValueError, TypeError):
            continue
        if not word or height < min_height or confidence < 15:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
    return "\n".join(" ".join(words) for words in lines.values())


def extract_prominent_candidate_brand(clean_text: str) -> tuple[str, str, str]:
    """
    Extracts the most plausible brand name, dosage form, and strength from raw OCR text
    when no catalog match is found.
    Example: 'uet Tablet ae & wt Duet Table a a4' -> ('Duet', 'Tablet', '')
    """
    if not clean_text:
        return "", "Tablet", ""

    lower_t = clean_text.lower()
    form = "Tablet"
    if "cap" in lower_t or "capsule" in lower_t:
        form = "Capsule"
    elif "syr" in lower_t or "syrup" in lower_t:
        form = "Syrup"
    elif "susp" in lower_t:
        form = "Suspension"
    elif "drop" in lower_t:
        form = "Eye Drops"
    elif "inj" in lower_t:
        form = "Injection"

    str_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(mg|mcg|ml|gm|g)\b', clean_text, re.IGNORECASE)
    strength = f"{str_match.group(1)} {str_match.group(2)}" if str_match else ""

    ignore = {
        "tablet", "tablets", "capsule", "capsules", "syrup", "suspension",
        "pharma", "pharmaceuticals", "ltd", "plc", "mg", "ml", "batch",
        "date", "exp", "mfg", "mrp", "lic", "dar", "keep", "cool", "dry",
        "place", "light", "children", "reach", "only", "use", "usp", "bdt",
        "table", "strip", "box", "price", "retail", "standard"
    }

    # Find title-cased words (e.g. Duet, Imotil, Napa)
    title_words = [w for w in re.findall(r'\b[A-Z][a-z]{2,}\b', clean_text) if w.lower() not in ignore]
    if title_words:
        from collections import Counter
        return Counter(title_words).most_common(1)[0][0], form, strength

    # Fallback to any alphabetic word of len >= 3
    all_words = [w.capitalize() for w in re.findall(r'\b[a-zA-Z]{3,}\b', clean_text) if w.lower() not in ignore]
    if all_words:
        from collections import Counter
        return Counter(all_words).most_common(1)[0][0], form, strength

    return "", form, strength


def rank_drugs_with_multi_signal(clean_text: str, all_drugs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Intelligent Multi-Signal Drug Ranking Algorithm:
    - High-speed candidate pre-filtering using token n-grams and character prefixes.
    - Token-level fuzzy matching (difflib/SequenceMatcher >= 70%) to gracefully handle foil reflections.
    - Dosage form, strength, and generic corroboration with safety disambiguation.
    """
    import difflib
    ocr_lower = clean_text.lower()
    ocr_tokens = set(re.findall(r"[a-z]+|\d+", ocr_lower))
    ocr_words = [t for t in ocr_tokens if len(t) >= 3 and not t.isdigit()]

    if not ocr_words:
        return []

    ocr_strength_numbers = {
        number
        for number, _unit in re.findall(
            r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|µg|ml|gm|g|iu)?\b", ocr_lower
        )
    }

    has_tab = bool(re.search(r"\b(tab|tablet|tablets)\b", ocr_lower))
    has_cap = bool(re.search(r"\b(cap|capsule|capsules)\b", ocr_lower))
    has_syr = bool(re.search(r"\b(syr|syrup|susp|suspension)\b", ocr_lower))

    # Fast 2-char prefix index to narrow candidates across 40k items in <10ms
    ocr_prefixes = {w[:3] for w in ocr_words if len(w) >= 3}
    candidates = []
    for d in all_drugs:
        b_lower = (d.get("brand_name") or "").lower()
        if any(p in b_lower for p in ocr_prefixes) or any(t in b_lower for t in ocr_words):
            candidates.append(d)

    if not candidates:
        return []

    scored_candidates = []
    for d in candidates:
        b_name = d["brand_name"]
        b_lower = b_name.lower().strip()
        b_tokens = [t for t in re.findall(r"[a-z]+", b_lower) if len(t) >= 3 and t not in ("tab", "cap", "tablet", "capsule", "standard", "plus")]
        if not b_tokens:
            b_tokens = [t for t in re.findall(r"[a-z]+", b_lower) if len(t) >= 3]
        if not b_tokens:
            continue

        best_brand_sim = 0.0
        exact_brand_hit = False

        for bt in b_tokens:
            if bt in ocr_tokens:
                best_brand_sim = max(best_brand_sim, 1.0)
                exact_brand_hit = True
            else:
                for ow in ocr_words:
                    if bt in ow or ow in bt:
                        sim = len(min(bt, ow, key=len)) / len(max(bt, ow, key=len))
                        best_brand_sim = max(best_brand_sim, sim)
                    else:
                        sim = difflib.SequenceMatcher(None, bt, ow).ratio()
                        if sim > best_brand_sim:
                            best_brand_sim = sim

        if best_brand_sim < 0.70:
            continue

        brand_score = best_brand_sim * 65.0

        # Strength Score
        str_score = 0
        drug_strength = (d.get("strength") or "").lower()
        drug_strength_nums = set(re.findall(r"\d+(?:\.\d+)?", drug_strength))
        if drug_strength_nums and ocr_strength_numbers:
            if drug_strength_nums.intersection(ocr_strength_numbers):
                str_score = 15.0

        # Dosage Form Score
        form_score = 0
        d_form = ((d.get("dosage_form__name") or "") + " " + (d.get("dosage_form__short_name") or "")).lower()
        if ("tab" in d_form and has_tab) or ("cap" in d_form and has_cap) or ("syr" in d_form and has_syr):
            form_score = 15.0

        # Generic Chemical Score
        gen_score = 0
        gen_name = (d.get("generic__name") or "").lower()
        if gen_name:
            for gp in re.findall(r"[a-z]{4,}", gen_name):
                if gp in ("acid", "sodium", "potassium", "chloride", "hydrochloride", "hydrate", "oral", "tablet"):
                    continue
                if gp in ocr_tokens:
                    gen_score += 15
        gen_score = min(25, gen_score)

        total_score = brand_score + str_score + form_score + gen_score
        if total_score >= 45:
            item_copy = dict(d)
            item_copy["name"] = item_copy["brand_name"]
            item_copy["price"] = float(item_copy["unit_mrp"])
            item_copy["dosage_form"] = item_copy.get("dosage_form__short_name") or item_copy.get("dosage_form__name") or "Tab"
            item_copy["generic_name"] = item_copy.get("generic__name") or "N/A"
            item_copy["manufacturer"] = item_copy.get("manufacturer__name") or "N/A"
            item_copy["score"] = min(100, round(total_score, 1))
            item_copy["_rank_score"] = total_score
            item_copy["ai_engine"] = "local"
            scored_candidates.append(item_copy)

    scored_candidates.sort(key=lambda x: x["_rank_score"], reverse=True)
    if scored_candidates:
        best_score = scored_candidates[0]["_rank_score"]
        scored_candidates = [item for item in scored_candidates if item["_rank_score"] >= best_score - 25]
    for item in scored_candidates:
        item.pop("_rank_score", None)
    return scored_candidates


def _gemini_scan_response(request, raw_bytes: bytes):
    """Return a confident AI match, or None so the local OCR result can be used."""
    if not GeminiAIService.is_gemini_active():
        return None
    try:
        tenant = getattr(request, "tenant", None)
        tenant_key = str(tenant.id) if tenant else None
        result = GeminiAIService.analyze_medicine_image(raw_bytes)
        if not result or not (result.get("brand_name") or result.get("generic_name")):
            return None
        matches = GeminiAIService.match_drug_from_gemini(result, tenant_key=tenant_key)

        primary_brand = (result.get("brand_name") or "").strip()
        if matches:
            primary_brand = matches[0]["brand_name"]

        raw_summary = f"{result.get('brand_name', '')} {result.get('strength', '')} ({result.get('dosage_form', '')}) - {result.get('generic_name', '')} [{result.get('manufacturer', '')}]".strip()
        if request.headers.get("HX-Request") and request.POST.get("format") != "json":
            return render(request, "pos/partials/camera_scan_results.html", {
                "detected_drugs": matches[:6] if matches else [],
                "primary_brand_name": primary_brand,
                "gemini_result": result,
                "raw_text": raw_summary,
                "ai_engine": "gemini",
            })
        return JsonResponse({
            "status": "success",
            "medicine": matches[0] if matches else None,
            "primary_brand_name": primary_brand,
            "gemini_result": result,
            "score": matches[0]["score"] if matches else 95,
            "raw_text": raw_summary,
            "results": matches[:6] if matches else [],
            "ai_engine": "gemini",
        })
    except Exception as err:
        logger.warning("Gemini Vision processing error: %s", err)
        if "quota" in str(err).lower() or "429" in str(err):
            request._gemini_quota_error = True
        return None


@tenant_user_required
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


    # Guard optional imports so a missing local OCR dependency returns a useful
    # setup error instead of a NoneType.frombuffer traceback.
    if cv2 is None or np is None or pytesseract is None or not _tesseract_available():
        message = "Local OCR needs NumPy, OpenCV, pytesseract, and the Tesseract OCR engine. Install the Python requirements and the Tesseract engine, then retry."
        if request.headers.get("HX-Request") and request.POST.get("format") != "json":
            return HttpResponse(
                f'<div class="p-4 text-center text-rose-700 bg-rose-50 rounded-xl">{message}</div>',
                status=503,
            )
        return JsonResponse({"status": "failed", "message": message}, status=503)

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

        # Downscale to optimal AI vision resolution (max 900px, ~50KB) for sub-second network transmission
        height, width = img.shape[:2]
        longest_edge = max(height, width)
        if longest_edge > 900:
            scale = 900 / longest_edge
            img = cv2.resize(img, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
        encoded, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if encoded:
            raw_bytes = buffer.tobytes()

        # ==============================================================
        # PRIORITY 1: Multimodal AI Vision (Google Gemini) - Instant & Accurate
        # ==============================================================
        if GeminiAIService.is_gemini_active():
            gemini_response = _gemini_scan_response(request, raw_bytes)
            if gemini_response is not None:
                return gemini_response

        # ==============================================================
        # PRIORITY 2: Local Enhanced Multi-Pass OCR Pipeline
        # (Proven accurate on foil strips, bottles, and packaging)
        # ==============================================================
        img_resized = img  # Keep native compact size for 5x faster local OCR
        extracted_text = ""

        # Pass 1: Raw color image with --psm 3
        try:
            extracted_text = _read_large_text(img_resized, config='--psm 3 -l eng')
        except Exception as e1:
            logger.debug("Tesseract PSM 3 failed: %s", e1)

        # Pass 2: Grayscale with --psm 11
        if not extracted_text.strip():
            try:
                gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
                extracted_text = _read_large_text(gray, config='--psm 11 -l eng')
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
                extracted_text = _read_large_text(thresh, config='--psm 11 -l eng')
            except Exception as e3:
                logger.debug("Tesseract threshold preprocessing failed: %s", e3)

        # Avoid initializing EasyOCR inside a cashier request: its first model
        # load can take much longer than the scan itself. Empty/weak local reads
        # go to the bounded Gemini fallback below.

        clean_text = extracted_text.strip()
        safe_log_text = clean_text.encode('ascii', errors='backslashreplace').decode('ascii')
        logger.info("Local OCR Extracted Text: %s", safe_log_text)

        if not clean_text:
            gemini_response = _gemini_scan_response(request, raw_bytes)
            if gemini_response is not None:
                return gemini_response
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
        tenant = getattr(request, "tenant", None)
        tenant_key = str(tenant.id) if tenant else "default_tenant"
        cache_key_meds = f"pos:all_active_drugs_ocr_cache:{tenant_key}"
        medicines = cache.get(cache_key_meds)
        if not medicines:
            catalog_scope = Q(tenant__isnull=True) | Q(tenant=tenant)
            medicines = list(BrandDrug.objects.filter(catalog_scope, is_active=True).values(
                'id', 'brand_name', 'unit_mrp', 'strength',
                'dosage_form__name', 'dosage_form__short_name',
                'generic__name', 'manufacturer__name'
            ))
            cache.set(cache_key_meds, medicines, 3600)

        # Check User Training / Custom Nicknames
        matched_items = []
        trained_brand = DrugTrainingService.find_match(clean_text, tenant_key)
        if not trained_brand:
            for l in clean_text.split('\n'):
                t_match = DrugTrainingService.find_match(l, tenant_key)
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

        # Only spend time on alternate preprocessing when the fast first OCR
        # pass found no catalog candidate. This recovers labels where grayscale
        # or contrast cleanup reads the brand more clearly without slowing
        # scans that already have a strong exact match.
        if not ranked_local:
            alternate_texts = []
            try:
                gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
                gray_text = _read_large_text(gray, config='--psm 11 -l eng').strip()
                if gray_text:
                    alternate_texts.append(gray_text)
                    ranked_local = rank_drugs_with_multi_signal(gray_text, medicines)
            except Exception as err:
                logger.debug("Tesseract grayscale retry failed: %s", err)

            if not ranked_local:
                try:
                    _, _, r_channel = cv2.split(img_resized)
                    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                    contrast_red = clahe.apply(r_channel)
                    denoised = cv2.medianBlur(contrast_red, 3)
                    thresh = cv2.adaptiveThreshold(
                        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                        cv2.THRESH_BINARY, 21, 10
                    )
                    if np.mean(thresh) < 127:
                        thresh = cv2.bitwise_not(thresh)
                    threshold_text = _read_large_text(
                        thresh, config='--psm 11 -l eng'
                    ).strip()
                    if threshold_text:
                        alternate_texts.append(threshold_text)
                        ranked_local = rank_drugs_with_multi_signal(threshold_text, medicines)
                except Exception as err:
                    logger.debug("Tesseract threshold retry failed: %s", err)

            if alternate_texts:
                clean_text = "\n".join([clean_text, *alternate_texts]).strip()

        for rk in ranked_local:
            if not any(it['id'] == rk['id'] for it in matched_items):
                matched_items.append(rk)

        # Enrich with live FEFO batch in batch query (Zero N+1)
        top_drugs = []
        top_candidates = matched_items[:6]
        top_ids = [it['id'] for it in top_candidates]
        if top_ids:
            drug_objs = list(BrandDrug.objects.filter(Q(tenant__isnull=True) | Q(tenant=tenant), id__in=top_ids).prefetch_related('batches'))
            drug_map = {d.id: d for d in drug_objs}
            for it in top_candidates:
                d_obj = drug_map.get(it['id'])
                if d_obj:
                    tenant_batches = d_obj.batches.filter(tenant=tenant)
                    fefo = tenant_batches.fefo().first() or tenant_batches.order_by("-expiry_date").first()
                    it['total_stock'] = tenant_batches.aggregate(total=Sum("current_stock"))["total"] or 0
                    it['fefo_batch'] = {
                        "id": str(fefo.id) if fefo else None,
                        "batch_number": fefo.batch_number if fefo else "N/A",
                        "expiry_date": fefo.expiry_date.strftime("%Y-%m-%d") if fefo else "N/A",
                        "stock": fefo.current_stock if fefo else 0,
                    } if fefo else None
                    top_drugs.append(it)

        # Strong local matches return without a network round-trip. Ask vision
        # only when local OCR found no match or the text evidence is ambiguous.
        if not top_drugs or top_drugs[0].get("score", 0) < 75:
            gemini_response = _gemini_scan_response(request, raw_bytes)
            if gemini_response is not None:
                return gemini_response

        # HTMX partial response
        primary_brand = top_drugs[0]["brand_name"] if top_drugs else ""
        sug_brand, sug_form, sug_strength = "", "Tablet", ""
        if not top_drugs:
            sug_brand, sug_form, sug_strength = extract_prominent_candidate_brand(clean_text)

        if request.headers.get("HX-Request") and request.POST.get("format") != "json":
            return render(request, "pos/partials/camera_scan_results.html", {
                "detected_drugs": top_drugs,
                "primary_brand_name": primary_brand,
                "suggested_brand_name": sug_brand,
                "suggested_dosage_form": sug_form,
                "suggested_strength": sug_strength,
                "raw_text": clean_text[:150],
                "ai_engine": "local",
                "quota_warning": getattr(request, "_gemini_quota_error", False),
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
            "message": f"প্রসেসিং এরর: {e!s}"
        })


# Backward compatible aliases
process_camera_scan_htmx = scan_medicine_ocr
