import csv
import re
from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from inventory.models import Manufacturer, DosageForm, GenericDrug, BrandDrug, DrugBatch
from core.models import Tenant

class Command(BaseCommand):
    help = "Seeds medicines from CSV file."

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Path to medicine.csv')

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        self.stdout.write(f"Reading CSV from {csv_path}...")

        # 0. Ensure Default Tenant
        tenant, _ = Tenant.objects.get_or_create(
            slug="default-pharmacy",
            defaults={
                "name": "Default Pharmacy",
                "phone": "01700-000000",
                "address": "Dhaka",
            }
        )

        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = list(reader)

        total_rows = len(data)
        self.stdout.write(f"Found {total_rows} records. Starting import...")

        today = timezone.now().date()
        
        # Cache dictionaries
        mfg_objs = {}
        gen_objs = {}
        form_objs = {}

        # Bulk lists
        new_drugs = []
        new_batches = []
        
        batch_size = 1000
        processed = 0

        with transaction.atomic():
            for row in data:
                brand_name = row['brand name'].strip()
                if not brand_name:
                    continue

                mfg_name = row['manufacturer'].strip() or "Unknown Manufacturer"
                gen_name = row['generic'].strip() or "Unknown Generic"
                form_name = row['dosage form'].strip() or "Tablet"
                strength = row['strength'].strip()

                # Extract price from 'package container' e.g. '100 ml bottle: ৳ 40.12'
                container = row.get('package container', '')
                price = Decimal("0.00")
                match = re.search(r'৳\s*([\d\.]+)', container)
                if match:
                    try:
                        price = Decimal(match.group(1))
                    except:
                        pass
                if price == 0:
                    price = Decimal("10.00") # default fallback
                    
                tp = price * Decimal("0.85") # 15% discount for TP

                # Get or Create Manufacturer
                if mfg_name not in mfg_objs:
                    mfg, _ = Manufacturer.objects.get_or_create(name=mfg_name)
                    mfg_objs[mfg_name] = mfg
                
                # Get or Create Generic
                if gen_name not in gen_objs:
                    gen, _ = GenericDrug.objects.get_or_create(name=gen_name)
                    gen_objs[gen_name] = gen

                # Get or Create Form
                if form_name not in form_objs:
                    is_liq = any(x in form_name.lower() for x in ['syrup', 'suspension', 'solution', 'drop', 'liquid'])
                    form, _ = DosageForm.objects.get_or_create(
                        name=form_name,
                        defaults={"is_liquid": is_liq}
                    )
                    form_objs[form_name] = form
                    
                # We will just get_or_create drug directly to avoid complex bulk_create conflicts on unique fields
                drug, created = BrandDrug.objects.get_or_create(
                    brand_name=brand_name,
                    strength=strength,
                    defaults={
                        "generic": gen_objs[gen_name],
                        "manufacturer": mfg_objs[mfg_name],
                        "dosage_form": form_objs[form_name],
                        "unit_mrp": price,
                        "unit_tp": tp,
                        "pack_size": 10,
                    }
                )
                
                # Create a batch if created
                if created:
                    DrugBatch.objects.create(
                        drug=drug,
                        batch_number=f"B-{drug.id}-01",
                        manufacturing_date=today - timedelta(days=30),
                        expiry_date=today + timedelta(days=730),
                        purchase_price=tp,
                        unit_mrp=price,
                        initial_stock=100,
                        current_stock=100
                    )

                processed += 1
                if processed % 1000 == 0:
                    self.stdout.write(f"Processed {processed}/{total_rows}")

        self.stdout.write(self.style.SUCCESS(f"Successfully processed {processed} medicines!"))

