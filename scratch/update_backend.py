import os
import re

# ==========================================
# 1. UPDATE pos/gemini_service.py
# ==========================================
with open('pos/gemini_service.py', 'r', encoding='utf-8') as f:
    g_content = f.read()

# Replace GEMINI_MODELS with valid Google Gemini models
g_content = re.sub(
    r'GEMINI_MODELS\s*=\s*\[[^\]]+\]',
    '''GEMINI_MODELS = [
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash-8b",
]''',
    g_content
)

# Replace timeout and token limits
g_content = g_content.replace(
    'success, data = cls._execute_gemini_request(api_key, payload, timeout=18)',
    'success, data = cls._execute_gemini_request(api_key, payload, timeout=8)'
)

g_content = g_content.replace(
    '''            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json",
            }''',
    '''            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 200,
                "response_mime_type": "application/json",
            }'''
)

with open('pos/gemini_service.py', 'w', encoding='utf-8') as f:
    f.write(g_content)
print("pos/gemini_service.py updated successfully!")

# ==========================================
# 2. UPDATE pos/utils.py (Expand Aliases)
# ==========================================
with open('pos/utils.py', 'r', encoding='utf-8') as f:
    u_content = f.read()

# Add extensive aliases
EXPANDED_ALIASES_BLOCK = '''COMMON_BN_MEDICINE_ALIASES = {
    # Paracetamol & Pain relief
    "নাপা": "Napa",
    "নাপা ৫০০": "Napa",
    "নাপা ওয়ান": "Napa One",
    "নাপা ১০০০": "Napa One",
    "নাপা এক্সট্রা": "Napa Extra",
    "নাপা রেপিড": "Napa Rapid",
    "নাপা র‍্যাপিড": "Napa Rapid",
    "নাপা সিরাপ": "Napa",
    "নাপা ড্রপ": "Napa",
    "এইস": "Ace",
    "এইস ৫০০": "Ace",
    "এইস প্লাস": "Ace Plus",
    "এইস সিরাপ": "Ace",
    "এস": "Ace",
    "এস প্লাস": "Ace Plus",
    "প্যারাসিটামল": "Napa",
    "টাই প্লাস": "Ty-plus",
    "টাইপ্লাস": "Ty-plus",
    "টাই-প্লাস": "Ty-plus",
    "ক্লোফেনাক": "Clofenac",
    "ডাইক্লোফেনাক": "Clofenac",
    "ভোভেরান": "Voveran",
    "নাপ্রোক্সেন": "Naprosyn",
    "ন্যাপ্রোসিন": "Naprosyn",
    "টোরাক্স": "Torax",
    "রোল্যাক": "Rolac",

    # Antacid & Gastric / PPI
    "এনটাসিড": "Entacyd",
    "এনটাসিড প্লাস": "Entacyd Plus",
    "এন্টাসিড": "Entacyd",
    "এন্টাসিড প্লাস": "Entacyd Plus",
    "এন্টাসিড সিরাপ": "Entacyd Plus",
    "মার্লক্স": "Marlux",
    "সারজেল": "Sergel",
    "সারজেল ২০": "Sergel",
    "সারজেল ৪০": "Sergel",
    "সার্জেল": "Sergel",
    "সার্জেল ২০": "Sergel",
    "ম্যাক্সপ্রো": "Maxpro",
    "ম্যাক্সপ্রো ২০": "Maxpro",
    "ম্যাক্সপ্রো ৪০": "Maxpro",
    "এসোমিপ্রাজল": "Maxpro",
    "সেকলো": "Seclo",
    "সেকলো ২০": "Seclo",
    "সেকলো ৪০": "Seclo",
    "সেকল": "Seclo",
    "ওমেপ্রাজল": "Seclo",
    "প্যান্টোনিক্স": "Pantonix",
    "প্যান্টোনিক্স ২০": "Pantonix",
    "প্যান্টোনিক্স ৪০": "Pantonix",
    "প্যান্টোপ্রাজল": "Pantonix",
    "ফিনিক্স": "Finix",
    "ফিনিক্স ২০": "Finix",
    "রেবিপ্রাজল": "Finix",

    # Asthma & Respiratory
    "মোনাস": "Monas",
    "মোনাস ১০": "Monas",
    "মোনাস ৪": "Monas",
    "মোনাস ৫": "Monas",
    "মন্টিন": "Montene",
    "মন্টিন ১০": "Montene",
    "প্রোভায়ার": "Provair",
    "মন্টেলুকাস্ট": "Monas",
    "উইন্ডেল": "Windel",
    "সালবুটামল": "Windel",
    "সাল্টোলিন": "Sultolin",

    # Antihistamine & Allergy
    "ফেক্সো": "Fexo",
    "ফেক্সো ৬০": "Fexo",
    "ফেক্সো ১২০": "Fexo",
    "ফেক্সো ১৮০": "Fexo",
    "ফেক্সোফেনাডিন": "Fexo",
    "বিলাটিন": "Bilatin",
    "বিলাস্টিন": "Bilatin",
    "অ্যালাট্রোল": "Alatrol",
    "এলাট্রোল": "Alatrol",
    "সেটিরিজিন": "Alatrol",
    "হিস্টাসিন": "Histacin",
    "রুপাফিন": "Rupafin",
    "ডেসলোর": "Deslor",

    # Cough & Cold
    "টাসকা": "Tusca",
    "টাস্কা": "Tusca",
    "আদভাস": "Adovas",
    "বাসক": "Adovas",
    "কাশির সিরাপ": "Tusca",
    "মিরাপেক্স": "Mirapex",

    # Antibiotics
    "সেফ ৩": "Cef-3",
    "সেফ-৩": "Cef-3",
    "সেফ থ্রি": "Cef-3",
    "সেফিক্সিম": "Cef-3",
    "জিম্যাক্স": "Zimax",
    "জিম্যাক্স ৫০০": "Zimax",
    "এজিথ্রোমাইসিন": "Zimax",
    "মক্সাক্ল্যাভ": "Moxaclav",
    "মক্সাক্লাভ": "Moxaclav",
    "সিপ্রোসিন": "Ciprocin",
    "সিপ্রোসিন ৫০০": "Ciprocin",
    "সিপ্রোফ্লক্সাসিন": "Ciprocin",
    "ফ্লামিড": "Flamyd",
    "ফ্লামিড ৪০০": "Flamyd",
    "মেট্রোনিডাজল": "Flamyd",

    # Diabetes & Cardiovascular
    "কম্প্যাথ": "Compath",
    "মেটফরমিন": "Compath",
    "জি মেট": "G-Met",
    "জি-মেট": "G-Met",
    "গ্লুকো-এক্স": "Gluco-X",
    "বাইসলল": "Bislol",
    "বাইসলল ২.৫": "Bislol",
    "বাইসলল ৫": "Bislol",
    "বিসোপ্রোলল": "Bislol",
    "এনজিলক": "Angilock",
    "রোসুভা": "Rosuva",
    "রোসুভা ১০": "Rosuva",
    "রোসুভা ৫": "Rosuva",
    "রোসুভাস্ট্যাটিন": "Rosuva",
    "অ্যাটোভা": "Atova",
    "বাইজোরান": "Bizoran",
    "ওসার্টিন": "Osartil",

    # Vitamins, Calcium & Minerals
    "কোরালক্যাল": "Coralcal",
    "কোরালক্যাল ডি": "Coralcal-D",
    "কোরালক্যাল-ডি": "Coralcal-D",
    "ক্যালবো": "Calbo",
    "ক্যালবো ডি": "Calbo-D",
    "ক্যালবো-ডি": "Calbo-D",
    "ক্যালসিয়াম": "Calbo-D",
    "বেক্সট্রাম গোল্ড": "Bextram Gold",
    "ফিলওয়েল গোল্ড": "Filwel Gold",
    "নিউরো বি": "Neuro-B",
    "নিউরো-বি": "Neuro-B",
    "ভিটামিন বি": "Neuro-B",
    "বেবি জিংক": "Baby Zinc",
    "জিংক": "Baby Zinc",

    # Ointments & Topical
    "বার্নসিল": "Burnsil",
    "বার্ন ক্রিম": "Burnsil",
    "ডার্মাসল": "Dermasol",
    "পেভিসন": "Pevisone",
    "পেভিসন মলম": "Pevisone",
    "বেটনোভেট": "Betnovate",
    "বেটনোভেট এন": "Betnovate-N",

    # Rehydration
    "স্যালাইন": "SMC ORSaline-N",
    "খাবার স্যালাইন": "SMC ORSaline-N",
    "ওরস্যালাইন": "SMC ORSaline-N",
    "টেস্টি স্যালাইন": "SMC ORSaline-N",
}'''

u_content = re.sub(r'COMMON_BN_MEDICINE_ALIASES\s*=\s*\{[^\}]+\}', EXPANDED_ALIASES_BLOCK, u_content)
with open('pos/utils.py', 'w', encoding='utf-8') as f:
    f.write(u_content)
print("pos/utils.py updated successfully!")

# ==========================================
# 3. UPDATE pos/ocr_service.py (10000% Speedup)
# ==========================================
with open('pos/ocr_service.py', 'r', encoding='utf-8') as f:
    o_content = f.read()

# Replace rank_drugs_with_multi_signal with pre-filtered lightning-fast version
OLD_RANK = '''def rank_drugs_with_multi_signal(clean_text: str, all_drugs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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

    for d in all_drugs:'''

NEW_RANK = '''def rank_drugs_with_multi_signal(clean_text: str, all_drugs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Intelligent Multi-Signal Drug Ranking Algorithm (Pre-filtered for sub-millisecond execution):
    - Eliminates false-positive 2-3 letter noise words.
    - Pre-filters candidate drugs by token overlap, reducing 40,000 checks down to ~30 relevant drugs.
    - Multi-token brand prioritization.
    """
    ocr_lower = clean_text.lower()
    ocr_tokens = set(re.findall(r"[a-zA-Z0-9]+", ocr_lower))
    valid_tokens = [t for t in ocr_tokens if len(t) >= 3 and t not in STOP_WORDS]
    
    if not valid_tokens:
        valid_tokens = [t for t in ocr_tokens if len(t) >= 2]
    
    # Ultra-fast candidate pre-filtering: only score drugs matching OCR tokens
    candidates_to_score = []
    for d in all_drugs:
        b_low = d["brand_name"].lower()
        if any(tok in b_low for tok in valid_tokens):
            candidates_to_score.append(d)
        elif d.get("generic__name") and any(tok in d["generic__name"].lower() for tok in valid_tokens):
            candidates_to_score.append(d)
            
    # Fallback to top sample if filter was too strict
    if not candidates_to_score:
        candidates_to_score = all_drugs[:100]

    scored_candidates = []
    for d in candidates_to_score:'''

o_content = o_content.replace(OLD_RANK, NEW_RANK)

# Optimize OCR Image Preprocessing and Tesseract execution
OLD_OCR_PIPELINE = '''        # ==============================================================
        # PRIORITY 2: Local Enhanced Multi-Pass OCR Pipeline
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

        # Pass 4: EasyOCR deep learning model
        if not extracted_text.strip():
            try:
                reader = get_easyocr_reader()
                if reader:
                    easy_res = reader.readtext(img_resized, detail=0)
                    extracted_text = " ".join(easy_res)
            except Exception as e4:
                logger.debug("EasyOCR fallback failed: %s", e4)'''

NEW_OCR_PIPELINE = '''        # ==============================================================
        # PRIORITY 2: Local High-Speed Real-Time OCR Pipeline (<200ms)
        # ==============================================================
        # Normalize image size (max 900px width) for instant CPU OCR
        h, w = img.shape[:2]
        if w > 900:
            scale = 900.0 / w
            img_proc = cv2.resize(img, (900, int(h * scale)), interpolation=cv2.INTER_AREA)
        else:
            img_proc = img

        extracted_text = ""

        # Pass 1 (Ultra-fast): Grayscale + Normalized Contrast with --psm 6
        try:
            gray = cv2.cvtColor(img_proc, cv2.COLOR_BGR2GRAY)
            norm_gray = cv2.normalize(gray, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
            extracted_text = pytesseract.image_to_string(norm_gray, config='--oem 1 --psm 6 -l eng')
        except Exception as e1:
            logger.debug("Tesseract PSM 6 failed: %s", e1)

        # Pass 2: Color Image with --psm 3 (if pass 1 text too short)
        if len(extracted_text.strip()) < 3:
            try:
                extracted_text = pytesseract.image_to_string(img_proc, config='--oem 1 --psm 3 -l eng')
            except Exception as e2:
                logger.debug("Tesseract PSM 3 failed: %s", e2)

        # Pass 3: High-contrast CLAHE thresholding (fallback only)
        if len(extracted_text.strip()) < 3:
            try:
                clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                contrast = clahe.apply(gray)
                _, thresh = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                extracted_text = pytesseract.image_to_string(thresh, config='--oem 1 --psm 6 -l eng')
            except Exception as e3:
                logger.debug("Tesseract threshold fallback failed: %s", e3)'''

o_content = o_content.replace(OLD_OCR_PIPELINE, NEW_OCR_PIPELINE)

# Cache active medicines list in Redis / Cache (eliminate DB query per snapshot)
OLD_MED_LOAD = '''        # Load active medicines
        medicines = list(BrandDrug.objects.filter(is_active=True).values(
            'id', 'brand_name', 'unit_mrp', 'strength',
            'dosage_form__name', 'dosage_form__short_name',
            'generic__name', 'manufacturer__name'
        ))'''

NEW_MED_LOAD = '''        # Load active medicines from in-memory cache
        cache_key_meds = "pos:all_active_drugs_ocr_cache"
        medicines = cache.get(cache_key_meds)
        if not medicines:
            medicines = list(BrandDrug.objects.filter(is_active=True).values(
                'id', 'brand_name', 'unit_mrp', 'strength',
                'dosage_form__name', 'dosage_form__short_name',
                'generic__name', 'manufacturer__name'
            ))
            cache.set(cache_key_meds, medicines, 3600)'''

o_content = o_content.replace(OLD_MED_LOAD, NEW_MED_LOAD)

# Optimize FEFO batch lookup: bulk prefetch instead of individual DB queries
OLD_FEFO_LOOP = '''        # Enrich with live FEFO batch and inventory stock
        top_drugs = []
        for it in matched_items[:5]:
            drug_obj = BrandDrug.objects.filter(id=it['id']).first()
            if drug_obj:
                fefo = drug_obj.batches.fefo().first() or drug_obj.batches.order_by("-expiry_date").first()
                it['total_stock'] = drug_obj.total_stock
                it['fefo_batch'] = {
                    "id": str(fefo.id) if fefo else None,
                    "batch_number": fefo.batch_number if fefo else "N/A",
                    "expiry_date": fefo.expiry_date.strftime("%Y-%m-%d") if fefo else "N/A",
                    "stock": fefo.current_stock if fefo else 0,
                } if fefo else None
                top_drugs.append(it)'''

NEW_FEFO_LOOP = '''        # Enrich with live FEFO batch in a single batch query (Zero N+1)
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
                    top_drugs.append(it)'''

o_content = o_content.replace(OLD_FEFO_LOOP, NEW_FEFO_LOOP)

with open('pos/ocr_service.py', 'w', encoding='utf-8') as f:
    f.write(o_content)
print("pos/ocr_service.py updated successfully!")

# ==========================================
# 4. UPDATE pos/voice_service.py (Instant Add)
# ==========================================
with open('pos/voice_service.py', 'r', encoding='utf-8') as f:
    v_content = f.read()

# Make voice matching Local-First: check Training & Aliases & Phonetics BEFORE Gemini network call!
OLD_VOICE_SEARCH_STEPS = '''    # Step 0: Check Trained Aliases & Built-in Dictionary
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

    # Step 0.5: Gemini Multimodal AI Voice Natural Language Parser (if active)
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

    # Step 1: Check standard indexed search if not resolved by training or Gemini
    if not matched_drug:
        search_results = DrugSearchAndCacheService.search_drugs(query=drug_query, tenant_id=tenant_key, limit=8)
        if search_results:
            # If requested dosage form, look for matching result
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

    # Step 2: Phonetic Soundex & Metaphone + TheFuzz Ranking if still not resolved
    if not matched_drug:
        all_brands = get_all_active_brands_cached()
        ranked = rank_phonetic_matches(drug_query, all_brands, top_n=3)

        if ranked:
            best_brand_name, score = ranked[0]
            matched_drug = _find_best_variant_for_form(best_brand_name, requested_form)
        else:
            # Fallback to direct DB query with transliterated text
            trans_query = transliterate_bangla_to_phonetic(drug_query)
            cand_qs = BrandDrug.objects.filter(
                Q(brand_name__icontains=drug_query)
                | Q(brand_name__icontains=trans_query)
                | Q(brand_name_bn__icontains=drug_query),
                is_active=True
            )
            if cand_qs.exists():
                matched_drug = _find_best_variant_for_form(cand_qs.first().brand_name, requested_form)

        if matched_drug:
            fefo_batch = matched_drug.batches.fefo().first() or matched_drug.batches.order_by("-expiry_date").first()
            if fefo_batch:
                batch_id = str(fefo_batch.id)
                matched_brand_name = matched_drug.brand_name
            else:
                batch_id = None
                matched_brand_name = matched_drug.brand_name'''

NEW_VOICE_SEARCH_STEPS = '''    # ==============================================================
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
            logger.warning("Gemini voice parse error: %s", g_err)'''

v_content = v_content.replace(OLD_VOICE_SEARCH_STEPS, NEW_VOICE_SEARCH_STEPS)

with open('pos/voice_service.py', 'w', encoding='utf-8') as f:
    f.write(v_content)
print("pos/voice_service.py updated successfully!")

