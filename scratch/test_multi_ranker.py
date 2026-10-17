import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('195.250.26.201', username='webkoders', key_filename=r'C:/Users/shuvo/.ssh/id_rsa', passphrase='SHUVOshuvo123@')

test_ranker_script = """
import os, sys, re
os.environ["TESSDATA_PREFIX"] = "/home/webkoders/tessdata"
import pytesseract
pytesseract.pytesseract.tesseract_cmd = "/home/webkoders/.local/bin/tesseract"

sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
import django
django.setup()

import cv2, numpy as np
from thefuzz import fuzz, process
from inventory.models import BrandDrug

# Load test image
img = cv2.imread('/home/webkoders/pos.webkoders.com/test_entacyd.jpg')
img2x = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
ocr_text = pytesseract.image_to_string(img2x, config='--psm 11 -l eng').strip()
print('--- OCR EXTRACTED TEXT ---')
print(ocr_text)
print('--------------------------')

ocr_lower = ocr_text.lower()
ocr_tokens = set(re.findall(r'[a-zA-Z0-9]+', ocr_lower))
print('OCR Tokens:', sorted(list(ocr_tokens))[:30])

# Test our multi-signal ranker against all drugs
all_drugs = list(BrandDrug.objects.filter(is_active=True).values(
    'id', 'brand_name', 'unit_mrp', 'strength',
    'dosage_form__name', 'dosage_form__short_name',
    'generic__name', 'manufacturer__name'
))

scored_candidates = []

for d in all_drugs:
    b_name = d['brand_name']
    b_lower = b_name.lower().strip()
    b_tokens = [t for t in re.findall(r'[a-zA-Z0-9]+', b_lower) if len(t) >= 2]
    if not b_tokens:
        continue

    # Filter out pure noise for short names (e.g. AX, APT, OR, TIE, IN)
    is_short_brand = len(b_lower) <= 3

    # 1. Check Brand tokens against OCR
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
            elif fuzz.partial_ratio(tok, ocr_lower) >= 85:
                matched_tokens += 0.85

    if matched_tokens == 0:
        continue

    brand_ratio = matched_tokens / len(b_tokens)
    brand_score = brand_ratio * 70

    # 2. Generic Chemical Score (0-35)
    gen_score = 0
    gen_name = (d['generic__name'] or '').lower()
    if gen_name:
        for gen_part in re.findall(r'[a-zA-Z]{4,}', gen_name):
            if gen_part in ('acid', 'sodium', 'potassium', 'chloride', 'hydrochloride', 'hydrate', 'oral', 'tablet'):
                continue
            if gen_part in ocr_tokens or gen_part in ocr_lower:
                gen_score += 15
            elif fuzz.partial_ratio(gen_part, ocr_lower) >= 85:
                gen_score += 10
    gen_score = min(35, gen_score)

    # 3. Strength Score (0-20)
    str_score = 0
    str_val = (d['strength'] or '').lower()
    if str_val:
        str_nums = re.findall(r'\d+', str_val)
        for num in str_nums:
            if int(num) > 5 and (num in ocr_tokens or num in ocr_lower):
                str_score += 8
    str_score = min(20, str_score)

    # 4. Dosage Form Score (0-15)
    form_score = 0
    form_val = (d.get('dosage_form__name') or '').lower()
    if form_val:
        for f_w in re.findall(r'[a-zA-Z]{4,}', form_val):
            if f_w in ocr_tokens or f_w in ocr_lower:
                form_score += 8
            elif fuzz.partial_ratio(f_w, ocr_lower) >= 85:
                form_score += 5
    form_score = min(15, form_score)

    # 5. Combination & Secondary Word Boost
    combo_boost = 0
    if len(b_tokens) > 1 and exact_token_matches >= 1:
        if gen_score >= 15 or str_score >= 8:
            combo_boost = 25

    # Suppress noise for short brands with 0 generic and 0 strength matches
    if is_short_brand and (gen_score == 0 and str_score == 0):
        continue

    total_score = brand_score + gen_score + str_score + form_score + combo_boost
    if total_score >= 50:
        scored_candidates.append({
            'drug': d,
            'brand': b_name,
            'form': d.get('dosage_form__name'),
            'strength': d.get('strength'),
            'generic': d.get('generic__name'),
            'score': round(total_score, 1),
            'breakdown': f'Brand={brand_score:.1f}, Gen={gen_score}, Str={str_score}, Form={form_score}'
        })

scored_candidates.sort(key=lambda x: x['score'], reverse=True)
print(f'Top {len(scored_candidates[:5])} Matches:')
for i, c in enumerate(scored_candidates[:5], 1):
    print(f"{i}. [{c['score']} pts] {c['brand']} ({c['form']}) - {c['strength']} | {c['breakdown']}")
"""

sftp = ssh.open_sftp()
with sftp.open('/home/webkoders/pos.webkoders.com/test_multi_ranker.py', 'w') as f:
    f.write(test_ranker_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/test_multi_ranker.py')
print('STDOUT:\n', stdout.read().decode())
print('STDERR:\n', stderr.read().decode())
ssh.close()
