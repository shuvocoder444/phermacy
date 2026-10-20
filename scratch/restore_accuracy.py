import re

# 1. Update pos/gemini_service.py
with open('pos/gemini_service.py', 'r', encoding='utf-8') as f:
    g_content = f.read()

# Put accessible Gemini models and limit retry attempts
g_content = re.sub(
    r'GEMINI_MODELS\s*=\s*\[[^\]]+\]',
    '''GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-1.5-flash",
]''',
    g_content
)

# Max timeout 4s to prevent lag
g_content = re.sub(
    r'for model in GEMINI_MODELS:',
    '''for model in GEMINI_MODELS[:2]:''',
    g_content
)

with open('pos/gemini_service.py', 'w', encoding='utf-8') as f:
    f.write(g_content)
print("pos/gemini_service.py updated!")

# 2. Update templates/pos/pos.html
with open('templates/pos/pos.html', 'r', encoding='utf-8') as f:
    p_content = f.read()

old_cap = '''            // 2. Downscale smartly to optimal OCR resolution (max 900px width/height)
            let outW = Math.round(sWidth);
            let outH = Math.round(sHeight);
            const maxDimension = 900;
            if (outW > maxDimension || outH > maxDimension) {
                if (outW > outH) {
                    outH = Math.round((outH * maxDimension) / outW);
                    outW = maxDimension;
                } else {
                    outW = Math.round((outW * maxDimension) / outH);
                    outH = maxDimension;
                }
            }
            canvas.width = Math.max(320, outW);
            canvas.height = Math.max(160, outH);
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, sx, sy, sWidth, sHeight, 0, 0, canvas.width, canvas.height);

            // 3. Export optimized lightweight JPEG payload (only ~60-90KB for instant transmission)
            const croppedImageData = canvas.toDataURL('image/jpeg', 0.82);
            this.ocrScanning = true;

            // Execute HTMX POST with optimized lightweight payload
            htmx.ajax('POST', "{% url 'pos:camera_scan' %}", {
                target: '#camera-scan-results-box',
                swap: 'innerHTML',
                values: { 
                    'image_data': croppedImageData 
                }
            }).finally(() => {
                this.ocrScanning = false;
                this.hasScanResults = true;
            });'''

new_cap = '''            // 2. Render ONLY the cropped green box region onto canvas at full crisp native resolution
            canvas.width = Math.round(sWidth);
            canvas.height = Math.round(sHeight);
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, sx, sy, sWidth, sHeight, 0, 0, canvas.width, canvas.height);

            // 3. Export high-res crystal-clear cropped image (0.95 quality for maximum OCR accuracy)
            const croppedImageData = canvas.toDataURL('image/jpeg', 0.95);
            this.ocrScanning = true;

            // Execute HTMX POST with full-res payload
            htmx.ajax('POST', "{% url 'pos:camera_scan' %}", {
                target: '#camera-scan-results-box',
                swap: 'innerHTML',
                values: { 
                    'image_data': croppedImageData 
                }
            }).finally(() => {
                this.ocrScanning = false;
                this.hasScanResults = true;
            });'''

norm_p = p_content.replace('\r\n', '\n')
norm_old_cap = old_cap.replace('\r\n', '\n')
norm_new_cap = new_cap.replace('\r\n', '\n')

assert norm_old_cap in norm_p, "old_cap not found in pos.html"
norm_p = norm_p.replace(norm_old_cap, norm_new_cap, 1)

with open('templates/pos/pos.html', 'w', encoding='utf-8') as f:
    f.write(norm_p)
print("templates/pos/pos.html updated with crisp full-res capture!")

# 3. Update pos/voice_service.py with phonetic fallback
with open('pos/voice_service.py', 'r', encoding='utf-8') as f:
    v_content = f.read()

target_step5 = '# ==============================================================\n    # STEP 5: Gemini AI Multimodal Voice Parser (Advanced Fallback Only)'

phonetic_step = '''    # ==============================================================
    # STEP 4.5: Phonetic Soundex & Metaphone Ranking Fallback
    # ==============================================================
    if not matched_drug:
        all_brands = get_all_active_brands_cached()
        ranked = rank_phonetic_matches(drug_query, all_brands, top_n=3)
        if ranked:
            best_brand_name, score = ranked[0]
            matched_drug = _find_best_variant_for_form(best_brand_name, requested_form)
            if matched_drug:
                matched_brand_name = matched_drug.brand_name
                fefo_b = matched_drug.batches.fefo().first() or matched_drug.batches.order_by("-expiry_date").first()
                if fefo_b:
                    batch_id = str(fefo_b.id)

    '''

norm_v = v_content.replace('\r\n', '\n')
if target_step5 in norm_v and 'STEP 4.5' not in norm_v:
    norm_v = norm_v.replace(target_step5, phonetic_step + target_step5, 1)
    with open('pos/voice_service.py', 'w', encoding='utf-8') as f:
        f.write(norm_v)
    print("pos/voice_service.py updated with phonetic fallback!")

