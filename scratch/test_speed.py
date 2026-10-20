import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import time
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()

from pos.ocr_service import rank_drugs_with_multi_signal
from pos.voice_service import parse_voice_command, _find_best_variant_for_form
from pos.training_service import DrugTrainingService
from inventory.models import BrandDrug

print('--- Testing Voice Parsing Speed ---')
queries = [
    'নাপা ১০টা',
    'সারজেল ২০ বিশ পিস',
    'সেকলো ২০ ১০টা',
    'ম্যাক্সপ্রো ২০ ১০টা',
    'নাপা সিরাপ ১ ফাইল',
    'প্যান্টোনিক্স ২০ ত্রিশটা',
    'এনটাসিড প্লাস ২ পাতা',
]
for q in queries:
    t0 = time.time()
    dq, form, qty = parse_voice_command(q)
    matched = DrugTrainingService.find_match(dq)
    drug = _find_best_variant_for_form(matched or dq, form)
    elapsed = (time.time() - t0) * 1000
    print(f'Voice: "{q}" -> Drug: {drug.brand_name if drug else None} ({qty} pcs) in {elapsed:.2f} ms')

print('\n--- Testing OCR Ranking Speed on 40,000 Catalog Drugs ---')
all_drugs = list(BrandDrug.objects.filter(is_active=True).values(
    'id', 'brand_name', 'unit_mrp', 'strength',
    'dosage_form__name', 'dosage_form__short_name',
    'generic__name', 'manufacturer__name'
))
print(f'Total catalog drugs: {len(all_drugs)}')

test_ocr_texts = [
    "Napa Extra Paracetamol 500mg Caffeine 65mg Beximco Pharma",
    "Sergel 20 Esomeprazole Magnesium Trihydrate 20mg",
    "Entacyd Plus Antacid Suspension Square Pharmaceuticals",
    "Seclo 20 Omeprazole 20mg Square",
]
for text in test_ocr_texts:
    t0 = time.time()
    results = rank_drugs_with_multi_signal(text, all_drugs)
    elapsed = (time.time() - t0) * 1000
    best = results[0]['brand_name'] if results else 'None'
    print(f'OCR: "{text[:30]}..." -> Best Match: {best} ({len(results)} matches) in {elapsed:.2f} ms')

