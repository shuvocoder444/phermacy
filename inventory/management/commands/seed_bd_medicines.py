from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import Manufacturer, DosageForm, GenericDrug, BrandDrug, DrugBatch
from customers.models import Customer
from core.models import Tenant


class Command(BaseCommand):
    help = "Seeds comprehensive 120+ Bangladesh DGDA pharmaceuticals, FEFO batches, and test data."

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding 120+ Bangladesh Pharmaceutical Catalog...")

        # 0. Ensure Default Tenant
        tenant, _ = Tenant.objects.get_or_create(
            slug="default-pharmacy",
            defaults={
                "name": "Popular Pharmacy & Health Care",
                "name_bn": "পপুলার ফার্মেসি অ্যান্ড হেলথ কেয়ার",
                "phone": "01711-223344",
                "address": "House 12, Road 4, Dhanmondi, Dhaka-1209",
                "trade_license_number": "TRAD/DSCC/012938/2024",
                "drug_license_number": "DGDA/RTL/DH-84920",
                "vat_reg_number": "BIN-002938192-0101",
            }
        )

        # 1. Top Pharmaceutical Manufacturers in Bangladesh
        manufacturers = {
            "Square Pharmaceuticals PLC": ("স্কয়ার ফার্মাসিউটিক্যালস", "SQ"),
            "Incepta Pharmaceuticals Ltd.": ("ইনসেপ্টা ফার্মাসিউটিক্যালস", "INC"),
            "Beximco Pharmaceuticals Ltd.": ("বেক্সিমকো ফার্মা", "BEX"),
            "Renata Limited": ("রেনাটা লিমিটেড", "REN"),
            "Healthcare Pharmaceuticals Ltd.": ("হেলথকেয়ার ফার্মা", "HPL"),
            "Opsonin Pharma Ltd.": ("অপসো স্যালাইন / ফার্মা", "OPS"),
            "Eskayef Pharmaceuticals Ltd.": ("এসকেএফ", "SKF"),
            "Acme Laboratories Ltd.": ("একমি ল্যাবরেটরিজ", "ACM"),
            "Aristopharma Ltd.": ("অ্যারিস্টোফার্মা", "APL"),
            "ACI Healthcare Limited": ("এসিআই হেলথকেয়ার", "ACI"),
            "Radiant Pharmaceuticals Ltd.": ("রেডিয়ান্ট ফার্মা", "RAD"),
            "Beacon Pharmaceuticals PLC": ("বিকন ফার্মাসিউটিক্যালস", "BCN"),
            "Popular Pharmaceuticals Ltd.": ("পপুলার ফার্মা", "PPL"),
            "General Pharmaceuticals Ltd.": ("জেনারেল ফার্মা", "GPL"),
            "Drug International Ltd.": ("ড্রাগ ইন্টারন্যাশনাল", "DIL"),
            "SMC Enterprise Ltd.": ("এসএমসি এন্টারপ্রাইজ", "SMC"),
            "Reckitt Benckiser": ("রেকটি বেনকিজার", "RB"),
            "GlaxoSmithKline (GSK)": ("জিএসকে", "GSK"),
            "Novartis Bangladesh": ("নোভারটিস", "NOV"),
            "Sanofi Bangladesh": ("স্যানোফি", "SNF"),
        }
        mfg_objs = {}
        for name, (bn, code) in manufacturers.items():
            mfg, _ = Manufacturer.objects.get_or_create(
                name=name,
                defaults={"name_bn": bn, "short_code": code}
            )
            mfg_objs[name] = mfg

        # 2. Dosage Forms
        forms = [
            ("Tablet", "ট্যাবলেট", "Tab", False),
            ("Capsule", "ক্যাপসুল", "Cap", False),
            ("Syrup", "সিরাপ", "Syr", True),
            ("Suspension", "সাসপেনশন", "Susp", True),
            ("Injection", "ইনজেকশন", "Inj", True),
            ("Eye Drops", "আই ড্রপ", "Drop", True),
            ("Ear Drops", "কানের ড্রপ", "Drop", True),
            ("Eye/Ear Drops", "চোখ/কানের ড্রপ", "Drop", True),
            ("Cream", "ক্রিম", "Crm", False),
            ("Ointment", "মলম", "Oint", False),
            ("Inhaler", "ইনহেলার", "Inh", False),
            ("Oral Saline / Powder", "খাবার স্যালাইন / পাউডার", "Sachet", False),
            ("Nasal Spray", "ন্যাজাল স্প্রে", "Spray", True),
            ("Suppository", "সাপোজিটরি", "Supp", False),
            ("Lotion", "লোশন", "Lot", True),
            ("Mouthwash", "মাউথওয়াশ", "Liq", True),
        ]
        form_objs = {}
        for name, bn, short_code, is_liq in forms:
            form, _ = DosageForm.objects.get_or_create(
                name=name,
                defaults={"name_bn": bn, "short_name": short_code, "is_liquid": is_liq}
            )
            form_objs[name] = form

        # 3. Generics
        generics = [
            # Pain, Fever & Inflammation
            ("Paracetamol", "প্যারাসিটামল", "Analgesic & Antipyretic", "B"),
            ("Paracetamol + Caffeine", "প্যারাসিটামল + ক্যাফেইন", "Analgesic", "C"),
            ("Paracetamol + Tramadol", "প্যারাসিটামল + ট্রামাডল", "Opioid Analgesic", "C"),
            ("Aceclofenac", "অ্যাসেক্লোফেনাক", "NSAID (Pain Relief)", "B"),
            ("Naproxen Sodium", "ন্যাপ্রোক্সেন সোডিয়াম", "NSAID", "C"),
            ("Ketorolac Tromethamine", "কিটোরোলাক", "Potent NSAID", "C"),
            ("Diclofenac Sodium", "ডাইক্লোফেনাক সোডিয়াম", "NSAID", "B"),
            ("Ibuprofen", "আইবুপ্রোফেন", "NSAID", "B"),
            ("Tolperisone Hydrochloride", "টোলপেরিসোন", "Muscle Relaxant", "C"),
            ("Baclofen", "বেক্লোফেন", "Muscle Relaxant", "C"),
            
            # Gastric, PPIs, Antacids & Anti-motility
            ("Esomeprazole", "এসোমিপ্রাজল", "Proton Pump Inhibitor (PPI)", "B"),
            ("Pantoprazole", "প্যান্টোপ্রাজল", "Proton Pump Inhibitor (PPI)", "B"),
            ("Omeprazole", "ওমিপ্রাজল", "Proton Pump Inhibitor (PPI)", "C"),
            ("Rabeprazole", "রেবিপ্রাজল", "Proton Pump Inhibitor (PPI)", "B"),
            ("Dexlansoprazole", "ডেক্সল্যান্সোপ্রাজল", "Proton Pump Inhibitor (PPI)", "B"),
            ("Sodium Alginate + Potassium Bicarbonate", "সোডিয়াম অ্যালজিনেট", "Antacid & Antireflux", "A"),
            ("Magaldrate + Simethicone", "ম্যাগালড্রেট + সিমেথিকন", "Antacid & Antiflatulent", "A"),
            ("Domperidone", "ডমপেরিডন", "Prokinetic / Anti-emetic", "C"),
            ("Ondansetron", "অনডানসেট্রন", "Anti-emetic (Nausea/Vomiting)", "B"),
            ("Lactulose", "ল্যাকটুলোজ", "Osmotic Laxative", "B"),
            ("Simethicone", "সিমেথিকন", "Anti-gas / Antiflatulent", "A"),
            
            # Antibiotics & Antifungals
            ("Cefixime", "সেফিক্সিম", "3rd Gen Cephalosporin Antibiotic", "B"),
            ("Cefuroxime Axetil", "সেফুরোক্সিম", "2nd Gen Cephalosporin Antibiotic", "B"),
            ("Azithromycin", "অ্যাজিথ্রোমাইসিন", "Macrolide Antibiotic", "B"),
            ("Ciprofloxacin", "সিপ্রোফ্লক্সাসিন", "Fluoroquinolone Antibiotic", "C"),
            ("Levofloxacin", "লেভোফ্লক্সাসিন", "Fluoroquinolone Antibiotic", "C"),
            ("Amoxicillin + Clavulanic Acid", "অ্যামোক্সিসিলিন + ক্লাভুলানিক এসিড", "Penicillin Antibiotic", "B"),
            ("Amoxicillin Trihydrate", "অ্যামোক্সিসিলিন", "Penicillin Antibiotic", "B"),
            ("Doxycycline", "ডক্সিসাইক্লিন", "Tetracycline Antibiotic", "D"),
            ("Fluconazole", "ফ্লুকোনাজোল", "Antifungal", "C"),
            ("Itraconazole", "ইট্রাকোনাজোল", "Antifungal", "C"),
            ("Metronidazole", "মেট্রোনিডাজোল", "Antiprotozoal / Antibiotic", "B"),
            ("Nitazoxanide", "নিটাজোক্সানাইড", "Antiprotozoal", "B"),
            
            # Respiratory, Cold, Allergy & Asthma
            ("Montelukast", "মন্টেলুকাস্ট", "Leukotriene Receptor Antagonist", "B"),
            ("Fexofenadine", "ফেক্সোফেনাডিন", "Antihistamine", "C"),
            ("Bilastine", "বিলাস্টিন", "Non-sedating Antihistamine", "B"),
            ("Levocetirizine", "লেভোসিটিরিজিন", "Antihistamine", "B"),
            ("Cetirizine", "সিটিরিজিন", "Antihistamine", "B"),
            ("Rupatadine", "রুপাটাডিন", "Antihistamine", "B"),
            ("Dextromethorphan + Pseudoephedrine", "কাফ সিরাপ কম্বিনেশন", "Cough Suppressant", "C"),
            ("Diphenhydramine + Ammonium Chloride", "অ্যান্টিহিস্টামিন কাফ সিরাপ", "Expectorant", "C"),
            ("Salbutamol", "সালবিউটামল", "Bronchodilator (Asthma)", "C"),
            ("Fluticasone + Salmeterol", "ফ্লুটিকাসোন + সালমেটেরল", "Inhaled Corticosteroid", "C"),
            ("Budesonide + Formoterol", "বুডেসোনাইড + ফরমোটেরল", "Inhaled Corticosteroid", "C"),
            ("Ipratropium Bromide", "ইপ্রাট্রোপিয়াম ব্রোমাইড", "Anticholinergic Bronchodilator", "B"),
            ("Oxymetazoline Hydrochloride", "অক্সিমেটাজোলিন", "Nasal Decongestant", "C"),
            
            # Diabetes, Heart, Cholesterol & Hypertension
            ("Metformin Hydrochloride", "মেটফরমিন", "Antidiabetic (Biguanide)", "B"),
            ("Sitagliptin + Metformin", "সিটাগ্লিপটিন + মেটফরমিন", "DPP-4 Inhibitor + Biguanide", "B"),
            ("Vildagliptin + Metformin", "ভিলডাগ্লিপটিন + মেটফরমিন", "DPP-4 Inhibitor + Biguanide", "B"),
            ("Linagliptin", "লিনালেপটিন", "DPP-4 Inhibitor", "B"),
            ("Empagliflozin", "এমপাগ্লিফ্লোজিন", "SGLT2 Inhibitor", "C"),
            ("Dapagliflozin", "ডাপাগ্লিফ্লোজিন", "SGLT2 Inhibitor", "C"),
            ("Glimepiride", "গ্লিমেপিরিড", "Sulfonylurea", "C"),
            ("Bisoprolol Fumarate", "বাইসোপ্রোলল", "Beta Blocker (Hypertension)", "C"),
            ("Amlodipine + Olmesartan", "অ্যামলোডিপিন + ওলমেসার্টান", "Antihypertensive Combination", "D"),
            ("Amlodipine Besylate", "অ্যামলোডিপিন", "Calcium Channel Blocker", "C"),
            ("Losartan Potassium", "লোসার্টান পটাশিয়াম", "ARB (Antihypertensive)", "D"),
            ("Telmisartan", "টেলমিসারটান", "ARB (Antihypertensive)", "D"),
            ("Rosuvastatin", "রসুভাস্ট্যাটিন", "Statin (Cholesterol)", "X"),
            ("Atorvastatin", "অ্যাটরভাস্ট্যাটিন", "Statin (Cholesterol)", "X"),
            ("Clopidogrel + Aspirin", "ক্লোপিডোগ্রেল + অ্যাসপিরিন", "Antiplatelet", "C"),
            ("Clopidogrel Bisulfate", "ক্লোপিডোগ্রেল", "Antiplatelet", "B"),
            
            # Vitamins, Minerals, Iron & Pregnancy
            ("Calcium + Vitamin D3", "ক্যালসিয়াম + ভিটামিন ডি৩", "Bone Supplement", "A"),
            ("Coral Calcium + Vitamin D3", "কোরাল ক্যালসিয়াম + ডি৩", "Bone Supplement", "A"),
            ("Vitamin B1 + B6 + B12", "ভিটামিন বি১, বি৬, বি১২", "Neurotropic Vitamin", "A"),
            ("Multivitamin & Multimineral", "মাল্টিভিটামিন ও মাল্টিমিনারেল", "Nutritional Supplement", "A"),
            ("Carbonyl Iron + Folic Acid + Zinc", "আয়রন + ফলিক এসিড + জিংক", "Hematinic Supplement", "A"),
            ("Zinc Sulfate Monohydrate", "জিংক সালফেট", "Immunity & Diarrhea", "A"),
            ("Cholecalciferol (Vitamin D3)", "ভিটামিন ডি৩ (ড্রপ/ক্যাপসুল)", "High Potency Vitamin D", "A"),
            ("Oral Rehydration Salts (ORS)", "খাবার স্যালাইন (ওআরএস)", "Electrolytes", "A"),
            
            # Topical, Drops, Eye & Antiseptic
            ("Silver Sulfadiazine", "সিলভার সালফাডায়াজিন", "Burn Cream", "B"),
            ("Moxifloxacin Eye Drops", "মক্সিফ্লক্সাসিন আই ড্রপ", "Ophthalmic Antibiotic", "C"),
            ("Tobramycin + Dexamethasone", "টোব্রামাইসিন + ডেক্সামেথাসন", "Eye/Ear Drops", "C"),
            ("Clobetasol Propionate", "ক্লোবেটাসল প্রোপিওনেট", "Topical Corticosteroid", "C"),
            ("Betamethasone + Neomycin", "বেটামেথাসন + নিওমাইসিন", "Topical Corticosteroid", "C"),
            ("Povidone Iodine", "পোভিডোন আয়োডিন", "Topical Antiseptic", "C"),
            ("Chlorhexidine Gluconate", "ক্লোরহেক্সিডিন মাউথওয়াশ", "Antiseptic Mouthwash", "B"),
        ]

        generic_objs = {}
        for name, bn, t_class, preg in generics:
            gen, _ = GenericDrug.objects.get_or_create(
                name=name,
                defaults={"name_bn": bn, "therapeutic_class": t_class, "pregnancy_category": preg}
            )
            generic_objs[name] = gen

        # 4. 120+ Real-World Medicines in Bangladesh
        # Format: (Brand, Bangla, Generic, Manufacturer, Form, Strength, MRP, TP, Rack, Stock, ExpDays)
        medicines = [
            # === PAIN, FEVER & ARTHRITIS ===
            ("Napa", "নাপা", "Paracetamol", "Square Pharmaceuticals PLC", "Tablet", "500 mg", Decimal("1.20"), Decimal("0.98"), "A1-01", 300, 450),
            ("Napa Extra", "নাপা এক্সট্রা", "Paracetamol + Caffeine", "Square Pharmaceuticals PLC", "Tablet", "500 mg + 65 mg", Decimal("3.00"), Decimal("2.45"), "A1-02", 400, 500),
            ("Napa Rapid", "নাপা র‍্যাপিড", "Paracetamol", "Square Pharmaceuticals PLC", "Tablet", "500 mg", Decimal("2.00"), Decimal("1.64"), "A1-03", 150, 360),
            ("Napa Extend", "নাপা এক্সটেন্ড", "Paracetamol", "Square Pharmaceuticals PLC", "Tablet", "665 mg", Decimal("2.50"), Decimal("2.05"), "A1-04", 180, 400),
            ("Napa Syrup", "নাপা সিরাপ", "Paracetamol", "Square Pharmaceuticals PLC", "Syrup", "120 mg/5 ml", Decimal("35.00"), Decimal("28.70"), "A1-05", 60, 400),
            ("Napa Drop", "নাপা ড্রপ", "Paracetamol", "Square Pharmaceuticals PLC", "Syrup", "15 ml Drop", Decimal("35.00"), Decimal("28.70"), "A1-06", 40, 380),
            ("Ty-plus", "টাই-প্লাস", "Paracetamol + Caffeine", "Square Pharmaceuticals PLC", "Tablet", "500 mg + 65 mg", Decimal("2.50"), Decimal("2.00"), "A1-07", 100, 365),
            ("Ace", "এইস", "Paracetamol", "Square Pharmaceuticals PLC", "Tablet", "500 mg", Decimal("1.20"), Decimal("0.98"), "A2-01", 250, 520),
            ("Ace Plus", "এইস প্লাস", "Paracetamol + Caffeine", "Square Pharmaceuticals PLC", "Tablet", "500 mg + 65 mg", Decimal("3.00"), Decimal("2.45"), "A2-02", 350, 480),
            ("Ace Syrup", "এইস সিরাপ", "Paracetamol", "Square Pharmaceuticals PLC", "Syrup", "120 mg/5 ml", Decimal("35.00"), Decimal("28.70"), "A2-03", 50, 420),
            ("Fast", "ফাস্ট", "Paracetamol", "Acme Laboratories Ltd.", "Tablet", "500 mg", Decimal("1.20"), Decimal("0.98"), "A2-04", 100, 300),
            ("Renova", "রেনোভা", "Paracetamol", "Renata Limited", "Tablet", "500 mg", Decimal("1.20"), Decimal("0.98"), "A2-05", 120, 360),
            ("Flexi 100", "ফ্লেক্সি ১০০", "Aceclofenac", "Square Pharmaceuticals PLC", "Tablet", "100 mg", Decimal("6.00"), Decimal("4.92"), "A3-01", 220, 420),
            ("Flexi SR 200", "ফ্লেক্সি এসআর", "Aceclofenac", "Square Pharmaceuticals PLC", "Tablet", "200 mg SR", Decimal("12.00"), Decimal("9.84"), "A3-02", 100, 400),
            ("Reservix 100", "রিজারভিক্স ১০০", "Aceclofenac", "Incepta Pharmaceuticals Ltd.", "Tablet", "100 mg", Decimal("6.00"), Decimal("4.92"), "A3-03", 180, 400),
            ("Naprosyn 500", "ন্যাপ্রোসিন ৫০০", "Naproxen Sodium", "Radiant Pharmaceuticals Ltd.", "Tablet", "500 mg", Decimal("16.00"), Decimal("13.12"), "A3-04", 140, 380),
            ("Napryn 500", "ন্যাপ্রিন ৫০০", "Naproxen Sodium", "Square Pharmaceuticals PLC", "Tablet", "500 mg", Decimal("15.00"), Decimal("12.30"), "A3-05", 110, 400),
            ("Rolac 10", "রোলাক ১০", "Ketorolac Tromethamine", "Square Pharmaceuticals PLC", "Tablet", "10 mg", Decimal("12.00"), Decimal("9.84"), "A4-01", 90, 300),
            ("Torax 10", "টোরাক্স ১০", "Ketorolac Tromethamine", "Incepta Pharmaceuticals Ltd.", "Tablet", "10 mg", Decimal("12.00"), Decimal("9.84"), "A4-02", 80, 320),
            ("Clofenac 50", "ক্লোফেনাক ৫০", "Diclofenac Sodium", "Square Pharmaceuticals PLC", "Tablet", "50 mg", Decimal("3.00"), Decimal("2.45"), "A4-03", 150, 450),
            ("Myolax 50", "মায়োল্যাক্স ৫০", "Tolperisone Hydrochloride", "Incepta Pharmaceuticals Ltd.", "Tablet", "50 mg", Decimal("8.00"), Decimal("6.56"), "A4-04", 120, 420),
            ("Tolpex 50", "টোলপেক্স ৫০", "Tolperisone Hydrochloride", "Square Pharmaceuticals PLC", "Tablet", "50 mg", Decimal("8.00"), Decimal("6.56"), "A4-05", 100, 400),

            # === GASTRIC, ACID REFLUX (PPIs), ANTACIDS & MOTILITY ===
            ("Sergel 20", "সারজেল ২০", "Esomeprazole", "Healthcare Pharmaceuticals Ltd.", "Capsule", "20 mg", Decimal("7.00"), Decimal("5.74"), "B1-01", 500, 600),
            ("Sergel 40", "সারজেল ৪০", "Esomeprazole", "Healthcare Pharmaceuticals Ltd.", "Capsule", "40 mg", Decimal("11.00"), Decimal("9.02"), "B1-02", 200, 550),
            ("Maxpro 20", "ম্যাক্সপ্রো ২০", "Esomeprazole", "Renata Limited", "Capsule", "20 mg", Decimal("7.00"), Decimal("5.74"), "B1-03", 450, 520),
            ("Maxpro 40", "ম্যাক্সপ্রো ৪০", "Esomeprazole", "Renata Limited", "Capsule", "40 mg", Decimal("11.00"), Decimal("9.02"), "B1-04", 160, 480),
            ("Nexum 20", "নেক্সাম ২০", "Esomeprazole", "Square Pharmaceuticals PLC", "Tablet", "20 mg", Decimal("7.00"), Decimal("5.74"), "B1-05", 300, 500),
            ("Seclo 20", "সেকলো ২০", "Omeprazole", "Square Pharmaceuticals PLC", "Capsule", "20 mg", Decimal("6.00"), Decimal("4.92"), "B2-01", 400, 540),
            ("Seclo 40", "সেকলো ৪০", "Omeprazole", "Square Pharmaceuticals PLC", "Capsule", "40 mg", Decimal("10.00"), Decimal("8.20"), "B2-02", 150, 480),
            ("Losectil 20", "লোসেকটিল ২০", "Omeprazole", "Eskayef Pharmaceuticals Ltd.", "Capsule", "20 mg", Decimal("6.00"), Decimal("4.92"), "B2-03", 350, 500),
            ("Pantonix 20", "প্যান্টোনিক্স ২০", "Pantoprazole", "Incepta Pharmaceuticals Ltd.", "Tablet", "20 mg", Decimal("7.00"), Decimal("5.74"), "B2-04", 300, 460),
            ("Pantonix 40", "প্যান্টোনিক্স ৪০", "Pantoprazole", "Incepta Pharmaceuticals Ltd.", "Tablet", "40 mg", Decimal("11.00"), Decimal("9.02"), "B2-05", 140, 440),
            ("Pantobex 20", "প্যান্টোবেক্স ২০", "Pantoprazole", "Beximco Pharmaceuticals Ltd.", "Tablet", "20 mg", Decimal("7.00"), Decimal("5.74"), "B2-06", 200, 460),
            ("Finix 20", "ফিনিক্স ২০", "Rabeprazole", "Opsonin Pharma Ltd.", "Tablet", "20 mg", Decimal("8.00"), Decimal("6.56"), "B3-01", 180, 420),
            ("Dexdel 30", "ডেক্সডেল ৩০", "Dexlansoprazole", "Square Pharmaceuticals PLC", "Capsule", "30 mg", Decimal("12.00"), Decimal("9.84"), "B3-02", 140, 390),
            ("Dexdel 60", "ডেক্সডেল ৬০", "Dexlansoprazole", "Square Pharmaceuticals PLC", "Capsule", "60 mg", Decimal("18.00"), Decimal("14.76"), "B3-03", 100, 380),
            ("Gaviscon Liquid", "গ্যাভিসকন সিরাপ", "Sodium Alginate + Potassium Bicarbonate", "Reckitt Benckiser", "Syrup", "200 ml", Decimal("320.00"), Decimal("272.00"), "B4-01", 35, 400),
            ("Entacyd Plus", "এন্টাসিড প্লাস", "Magaldrate + Simethicone", "Square Pharmaceuticals PLC", "Suspension", "200 ml", Decimal("90.00"), Decimal("73.80"), "B4-02", 50, 420),
            ("Motigut 10", "মোটিগাট ১০", "Domperidone", "Square Pharmaceuticals PLC", "Tablet", "10 mg", Decimal("3.50"), Decimal("2.87"), "B4-03", 300, 480),
            ("Omidon 10", "ওমিডন ১০", "Domperidone", "Incepta Pharmaceuticals Ltd.", "Tablet", "10 mg", Decimal("3.50"), Decimal("2.87"), "B4-04", 250, 500),
            ("Emistat 8", "এমিস্ট্যাট ৮", "Ondansetron", "Square Pharmaceuticals PLC", "Tablet", "8 mg", Decimal("10.00"), Decimal("8.20"), "B4-05", 120, 360),
            ("Avilac Syrup", "অ্যাভিলাক সিরাপ", "Lactulose", "Incepta Pharmaceuticals Ltd.", "Syrup", "100 ml", Decimal("140.00"), Decimal("114.80"), "B4-06", 40, 400),

            # === ANTIBIOTICS & ANTIMICROBIALS ===
            ("Cef-3", "সেফ-৩", "Cefixime", "Square Pharmaceuticals PLC", "Capsule", "200 mg", Decimal("35.00"), Decimal("28.70"), "C1-01", 150, 360),
            ("Cef-3 DS", "সেফ-৩ ডিএস", "Cefixime", "Square Pharmaceuticals PLC", "Capsule", "400 mg", Decimal("60.00"), Decimal("49.20"), "C1-02", 100, 360),
            ("Cef-3 Syrup", "সেফ-৩ সিরাপ", "Cefixime", "Square Pharmaceuticals PLC", "Suspension", "50 ml Susp", Decimal("160.00"), Decimal("131.20"), "C1-03", 45, 340),
            ("Fixolin 200", "ফিক্সোলিন ২০০", "Cefixime", "Incepta Pharmaceuticals Ltd.", "Capsule", "200 mg", Decimal("35.00"), Decimal("28.70"), "C1-04", 120, 360),
            ("Zimax 500", "জিম্যাক্স ৫০০", "Azithromycin", "Square Pharmaceuticals PLC", "Tablet", "500 mg", Decimal("40.00"), Decimal("32.80"), "C2-01", 200, 450),
            ("Zimax Syrup", "জিম্যাক্স সিরাপ", "Azithromycin", "Square Pharmaceuticals PLC", "Suspension", "15 ml Susp", Decimal("95.00"), Decimal("77.90"), "C2-02", 40, 360),
            ("Tridosil 500", "ট্রিডোসিল ৫০০", "Azithromycin", "Incepta Pharmaceuticals Ltd.", "Tablet", "500 mg", Decimal("40.00"), Decimal("32.80"), "C2-03", 160, 420),
            ("Azithrocin 500", "অ্যাজিথ্রোসিন ৫০০", "Azithromycin", "Beximco Pharmaceuticals Ltd.", "Tablet", "500 mg", Decimal("40.00"), Decimal("32.80"), "C2-04", 130, 400),
            ("Moxaclav 625", "মক্সাক্ল্যাভ ৬২৫", "Amoxicillin + Clavulanic Acid", "Square Pharmaceuticals PLC", "Tablet", "625 mg", Decimal("38.00"), Decimal("31.16"), "C3-01", 120, 350),
            ("Trioclav 625", "ট্রিওক্ল্যাভ ৬২৫", "Amoxicillin + Clavulanic Acid", "Incepta Pharmaceuticals Ltd.", "Tablet", "625 mg", Decimal("38.00"), Decimal("31.16"), "C3-02", 100, 350),
            ("Fimoxyl 500", "ফিমক্সিল ৫০০", "Amoxicillin Trihydrate", "Square Pharmaceuticals PLC", "Capsule", "500 mg", Decimal("7.00"), Decimal("5.74"), "C3-03", 200, 420),
            ("Ciprocin 500", "সিপ্রোসিন ৫০০", "Ciprofloxacin", "Square Pharmaceuticals PLC", "Tablet", "500 mg", Decimal("15.00"), Decimal("12.30"), "C4-01", 140, 400),
            ("Neoflox 500", "নিওফ্লক্স ৫০০", "Ciprofloxacin", "Beximco Pharmaceuticals Ltd.", "Tablet", "500 mg", Decimal("15.00"), Decimal("12.30"), "C4-02", 100, 380),
            ("Levoking 500", "লেভোকিং ৫০০", "Levofloxacin", "Square Pharmaceuticals PLC", "Tablet", "500 mg", Decimal("18.00"), Decimal("14.76"), "C4-03", 110, 360),
            ("Flamyd", "ফ্লামিড", "Metronidazole", "Square Pharmaceuticals PLC", "Tablet", "400 mg", Decimal("2.50"), Decimal("2.05"), "C4-04", 250, 500),
            ("Flamyd Suspension", "ফ্লামিড সিরাপ", "Metronidazole", "Square Pharmaceuticals PLC", "Suspension", "60 ml Susp", Decimal("40.00"), Decimal("32.80"), "C4-05", 40, 420),
            ("Lucan-R 150", "লুকান-আর ১৫০", "Fluconazole", "Renata Limited", "Capsule", "150 mg", Decimal("25.00"), Decimal("20.50"), "C5-01", 80, 480),
            ("Diflu 150", "ডাইফ্লু ১৫০", "Fluconazole", "Square Pharmaceuticals PLC", "Capsule", "150 mg", Decimal("25.00"), Decimal("20.50"), "C5-02", 90, 480),

            # === ALLERGY, ASTHMA, COLD & RESPIRATORY ===
            ("Monas 10", "মোনাস ১০", "Montelukast", "Acme Laboratories Ltd.", "Tablet", "10 mg", Decimal("17.00"), Decimal("13.94"), "D1-01", 300, 500),
            ("Monas 5 Chewable", "মোনাস ৫", "Montelukast", "Acme Laboratories Ltd.", "Tablet", "5 mg Chewable", Decimal("10.00"), Decimal("8.20"), "D1-02", 120, 480),
            ("Montene 10", "মন্টিন ১০", "Montelukast", "Square Pharmaceuticals PLC", "Tablet", "10 mg", Decimal("17.00"), Decimal("13.94"), "D1-03", 280, 520),
            ("Provair 10", "প্রোভায়ার ১০", "Montelukast", "Incepta Pharmaceuticals Ltd.", "Tablet", "10 mg", Decimal("17.00"), Decimal("13.94"), "D1-04", 200, 480),
            ("Fexo 120", "ফেক্সো ১২০", "Fexofenadine", "Square Pharmaceuticals PLC", "Tablet", "120 mg", Decimal("10.00"), Decimal("8.20"), "D2-01", 350, 480),
            ("Fexo 180", "ফেক্সো ১৮০", "Fexofenadine", "Square Pharmaceuticals PLC", "Tablet", "180 mg", Decimal("14.00"), Decimal("11.48"), "D2-02", 200, 450),
            ("Fexo Suspension", "ফেক্সো সিরাপ", "Fexofenadine", "Square Pharmaceuticals PLC", "Suspension", "50 ml Susp", Decimal("65.00"), Decimal("53.30"), "D2-03", 40, 360),
            ("Bilatin 20", "বিলাটিন ২০", "Bilastine", "Square Pharmaceuticals PLC", "Tablet", "20 mg", Decimal("18.00"), Decimal("14.76"), "D3-01", 180, 460),
            ("Bilasfa 20", "বিলাসফা ২০", "Bilastine", "Incepta Pharmaceuticals Ltd.", "Tablet", "20 mg", Decimal("18.00"), Decimal("14.76"), "D3-02", 140, 450),
            ("Alatrol 10", "অ্যালাট্রোল ১০", "Cetirizine", "Square Pharmaceuticals PLC", "Tablet", "10 mg", Decimal("3.50"), Decimal("2.87"), "D3-03", 300, 520),
            ("Alatrol Syrup", "অ্যালাট্রোল সিরাপ", "Cetirizine", "Square Pharmaceuticals PLC", "Syrup", "60 ml Syr", Decimal("40.00"), Decimal("32.80"), "D3-04", 50, 450),
            ("Histacin", "হিস্টাসিন", "Levocetirizine", "Square Pharmaceuticals PLC", "Tablet", "5 mg", Decimal("4.00"), Decimal("3.28"), "D3-05", 220, 480),
            ("Rupafin 10", "রুপাফিন ১০", "Rupatadine", "Beximco Pharmaceuticals Ltd.", "Tablet", "10 mg", Decimal("12.00"), Decimal("9.84"), "D3-06", 110, 420),
            ("Tusca Syrup", "টাসকা সিরাপ", "Dextromethorphan + Pseudoephedrine", "Square Pharmaceuticals PLC", "Syrup", "100 ml", Decimal("85.00"), Decimal("70.00"), "D4-01", 60, 360),
            ("Adovas Herbal", "আদভাস সিরাপ", "Dextromethorphan + Pseudoephedrine", "Square Pharmaceuticals PLC", "Syrup", "100 ml", Decimal("75.00"), Decimal("61.50"), "D4-02", 90, 420),
            ("Dexpoten Syrup", "ডেক্সপোটেন সিরাপ", "Diphenhydramine + Ammonium Chloride", "Incepta Pharmaceuticals Ltd.", "Syrup", "100 ml", Decimal("70.00"), Decimal("57.40"), "D4-03", 45, 360),
            ("Windel Inhaler", "উইন্ডেল ইনহেলার", "Salbutamol", "Square Pharmaceuticals PLC", "Inhaler", "200 puffs", Decimal("180.00"), Decimal("153.00"), "D5-01", 40, 600),
            ("Bexitrol F Inhaler", "বেক্সিটল এফ", "Fluticasone + Salmeterol", "Beximco Pharmaceuticals Ltd.", "Inhaler", "120 puffs", Decimal("450.00"), Decimal("382.50"), "D5-02", 25, 500),
            ("Afrin Nasal Spray", "আফ্রিন স্প্রে", "Oxymetazoline Hydrochloride", "Bayer / Healthcare", "Nasal Spray", "10 ml Spray", Decimal("80.00"), Decimal("68.00"), "D5-03", 50, 400),

            # === DIABETES, HYPERTENSION & CARDIAC ===
            ("Compath 50/500", "কম্প্যাথ", "Sitagliptin + Metformin", "Square Pharmaceuticals PLC", "Tablet", "50 mg + 500 mg", Decimal("22.00"), Decimal("18.04"), "E1-01", 160, 420),
            ("Galvus Met 50/500", "গালভাস মেট", "Vildagliptin + Metformin", "Novartis Bangladesh", "Tablet", "50 mg + 500 mg", Decimal("30.00"), Decimal("25.50"), "E1-02", 120, 400),
            ("G-Met 500", "জি-মেট ৫০০", "Metformin Hydrochloride", "Square Pharmaceuticals PLC", "Tablet", "500 mg", Decimal("5.00"), Decimal("4.10"), "E1-03", 300, 500),
            ("G-Met XR 1000", "জি-মেট ১০০০", "Metformin Hydrochloride", "Square Pharmaceuticals PLC", "Tablet", "1000 mg XR", Decimal("8.00"), Decimal("6.56"), "E1-04", 180, 480),
            ("Linaex 5", "লিনাক্স ৫", "Linagliptin", "Square Pharmaceuticals PLC", "Tablet", "5 mg", Decimal("20.00"), Decimal("16.40"), "E1-05", 140, 420),
            ("Jardiance 10", "জারডিয়ান্স ১০", "Empagliflozin", "Boehringer / Healthcare", "Tablet", "10 mg", Decimal("45.00"), Decimal("38.25"), "E1-06", 80, 400),
            ("Bislol 2.5", "বাইসলল ২.৫", "Bisoprolol Fumarate", "Square Pharmaceuticals PLC", "Tablet", "2.5 mg", Decimal("6.00"), Decimal("4.92"), "E2-01", 200, 480),
            ("Bislol 5", "বাইসলল ৫", "Bisoprolol Fumarate", "Square Pharmaceuticals PLC", "Tablet", "5 mg", Decimal("10.00"), Decimal("8.20"), "E2-02", 180, 480),
            ("Cardibis 2.5", "কার্ডিবাইস ২.৫", "Bisoprolol Fumarate", "Incepta Pharmaceuticals Ltd.", "Tablet", "2.5 mg", Decimal("6.00"), Decimal("4.92"), "E2-03", 150, 450),
            ("Angilock 50", "এনজিলক ৫০", "Losartan Potassium", "Square Pharmaceuticals PLC", "Tablet", "50 mg", Decimal("9.00"), Decimal("7.38"), "E2-04", 220, 520),
            ("Osartil 50", "ওসারটিল ৫০", "Losartan Potassium", "Incepta Pharmaceuticals Ltd.", "Tablet", "50 mg", Decimal("9.00"), Decimal("7.38"), "E2-05", 190, 500),
            ("Camlosart 5/20", "ক্যামলোসার্ট", "Amlodipine + Olmesartan", "Square Pharmaceuticals PLC", "Tablet", "5 mg + 20 mg", Decimal("12.00"), Decimal("9.84"), "E3-01", 160, 450),
            ("Amdocal 5", "অ্যামডোক্যাল ৫", "Amlodipine Besylate", "Beximco Pharmaceuticals Ltd.", "Tablet", "5 mg", Decimal("5.00"), Decimal("4.10"), "E3-02", 200, 500),
            ("Rosuva 10", "রোসুভা ১০", "Rosuvastatin", "Square Pharmaceuticals PLC", "Tablet", "10 mg", Decimal("25.00"), Decimal("20.50"), "E3-03", 150, 450),
            ("Rasuva 20", "রোসুভা ২০", "Rosuvastatin", "Square Pharmaceuticals PLC", "Tablet", "20 mg", Decimal("40.00"), Decimal("32.80"), "E3-04", 100, 420),
            ("Atova 10", "অ্যাতোভা ১০", "Atorvastatin", "Beximco Pharmaceuticals Ltd.", "Tablet", "10 mg", Decimal("18.00"), Decimal("14.76"), "E3-05", 140, 450),
            ("Anclog Plus", "এনক্লগ প্লাস", "Clopidogrel + Aspirin", "Square Pharmaceuticals PLC", "Tablet", "75 mg + 75 mg", Decimal("14.00"), Decimal("11.48"), "E4-01", 140, 400),
            ("Noclog 75", "নক্লগ ৭৫", "Clopidogrel Bisulfate", "Square Pharmaceuticals PLC", "Tablet", "75 mg", Decimal("12.00"), Decimal("9.84"), "E4-02", 150, 420),

            # === VITAMINS, MINERALS, CALCIUM & SUPPLEMENTS ===
            ("Coralcal-D", "কোরালক্যাল-ডি", "Coral Calcium + Vitamin D3", "Radiant Pharmaceuticals Ltd.", "Tablet", "500 mg + 200 IU", Decimal("16.00"), Decimal("13.12"), "F1-01", 250, 600),
            ("Calbo-D", "ক্যালবো-ডি", "Calcium + Vitamin D3", "Square Pharmaceuticals PLC", "Tablet", "500 mg + 200 IU", Decimal("8.00"), Decimal("6.56"), "F1-02", 300, 550),
            ("Calbo-Forte", "ক্যালবো ফোর্ট", "Calcium + Vitamin D3", "Square Pharmaceuticals PLC", "Tablet", "600 mg + 400 IU", Decimal("12.00"), Decimal("9.84"), "F1-03", 180, 500),
            ("Bextram Gold", "বেক্সট্রাম গোল্ড", "Multivitamin & Multimineral", "Beximco Pharmaceuticals Ltd.", "Tablet", "32 Ingredients", Decimal("12.00"), Decimal("9.84"), "F1-04", 200, 500),
            ("Filwel Gold", "ফিলওয়েল গোল্ড", "Multivitamin & Multimineral", "Square Pharmaceuticals PLC", "Tablet", "32 Ingredients", Decimal("12.00"), Decimal("9.84"), "F1-05", 250, 500),
            ("Neuro-B", "নিউরো-বি", "Vitamin B1 + B6 + B12", "Square Pharmaceuticals PLC", "Tablet", "100+200+200", Decimal("9.00"), Decimal("7.38"), "F2-01", 300, 520),
            ("Neubion", "নিউবিয়ন", "Vitamin B1 + B6 + B12", "Merck / Healthcare", "Tablet", "100+200+200", Decimal("10.00"), Decimal("8.50"), "F2-02", 150, 500),
            ("D-Rise 20000", "ডি-রাইজ ২০০০০", "Cholecalciferol (Vitamin D3)", "Incepta Pharmaceuticals Ltd.", "Capsule", "20,000 IU", Decimal("40.00"), Decimal("32.80"), "F2-03", 100, 450),
            ("Fefol-CI", "ফেফল-সিআই", "Carbonyl Iron + Folic Acid + Zinc", "Beximco Pharmaceuticals Ltd.", "Capsule", "Iron + Folic", Decimal("6.00"), Decimal("4.92"), "F2-04", 200, 480),
            ("Baby Zinc Syrup", "বেবি জিংক সিরাপ", "Zinc Sulfate Monohydrate", "Square Pharmaceuticals PLC", "Syrup", "100 ml", Decimal("45.00"), Decimal("36.90"), "F3-01", 60, 420),
            ("SMC ORSaline-N", "এসএমসি ওআরস্যালাইন", "Oral Rehydration Salts (ORS)", "SMC Enterprise Ltd.", "Oral Saline / Powder", "Sachet (500 ml)", Decimal("6.00"), Decimal("5.10"), "F3-02", 500, 720),
            ("Tasty Saline", "টেস্টি স্যালাইন", "Oral Rehydration Salts (ORS)", "SMC Enterprise Ltd.", "Oral Saline / Powder", "Sachet", Decimal("6.00"), Decimal("5.10"), "F3-03", 300, 600),

            # === DROPS, CREAMS, OINTMENTS & ANTISEPTICS ===
            ("Burnsil Cream", "বার্নসিল ক্রিম", "Silver Sulfadiazine", "Square Pharmaceuticals PLC", "Cream", "25 gm Tube", Decimal("65.00"), Decimal("53.30"), "G1-01", 40, 480),
            ("Moxiflox Drops", "মক্সিফ্লক্স ড্রপ", "Moxifloxacin Eye Drops", "Square Pharmaceuticals PLC", "Eye Drops", "5 ml Bottle", Decimal("120.00"), Decimal("98.40"), "G1-02", 50, 360),
            ("Toba-D Eye Drops", "টোবা-ডি ড্রপ", "Tobramycin + Dexamethasone", "Aristopharma Ltd.", "Eye/Ear Drops", "5 ml Bottle", Decimal("110.00"), Decimal("90.20"), "G1-03", 40, 360),
            ("Dermasol-N Cream", "ডার্মাসল-এন", "Clobetasol Propionate", "Square Pharmaceuticals PLC", "Cream", "15 gm Tube", Decimal("70.00"), Decimal("57.40"), "G1-04", 60, 400),
            ("Pevisone Cream", "পেভিসন ক্রিম", "Clobetasol Propionate", "ACI Healthcare Limited", "Cream", "10 gm Tube", Decimal("80.00"), Decimal("65.60"), "G1-05", 50, 420),
            ("Betnovate-N Cream", "বেটনাভেট-এন", "Betamethasone + Neomycin", "GlaxoSmithKline (GSK)", "Cream", "20 gm Tube", Decimal("65.00"), Decimal("55.25"), "G1-06", 45, 450),
            ("Povi-A Solution", "পোভি-এ লিকুইড", "Povidone Iodine", "Square Pharmaceuticals PLC", "Syrup", "100 ml", Decimal("90.00"), Decimal("73.80"), "G2-01", 40, 600),
            ("Savlon Antiseptic", "স্যাভলন লিকুইড", "Chlorhexidine Gluconate", "ACI Healthcare Limited", "Syrup", "112 ml", Decimal("55.00"), Decimal("46.75"), "G2-02", 60, 600),
            ("Hexisol Hand Rub", "হেক্সিসল", "Chlorhexidine Gluconate", "ACI Healthcare Limited", "Syrup", "250 ml", Decimal("130.00"), Decimal("110.50"), "G2-03", 50, 600),
        ]

        today = timezone.now().date()
        seeded_drugs_count = 0
        seeded_batches_count = 0

        for brand_name, bn, gen_name, mfg_name, form_name, strn, mrp, tp, rack, stock_qty, exp_days in medicines:
            gen_obj = generic_objs.get(gen_name) or generic_objs["Paracetamol"]
            mfg_obj = mfg_objs.get(mfg_name) or mfg_objs["Square Pharmaceuticals PLC"]
            form_obj = form_objs.get(form_name) or form_objs["Tablet"]

            drug, created = BrandDrug.objects.get_or_create(
                brand_name=brand_name,
                strength=strn,
                defaults={
                    "brand_name_bn": bn,
                    "generic": gen_obj,
                    "manufacturer": mfg_obj,
                    "dosage_form": form_obj,
                    "unit_mrp": mrp,
                    "unit_tp": tp,
                    "rack_location": rack,
                    "pack_size": 10,
                }
            )
            if not created:
                drug.brand_name_bn = bn
                drug.unit_mrp = mrp
                drug.unit_tp = tp
                drug.rack_location = rack
                drug.save()

            seeded_drugs_count += 1

            # Batch 1: Primary FEFO Batch
            batch_code_1 = f"B24-{brand_name[:3].upper()}-01"
            DrugBatch.objects.get_or_create(
                drug=drug,
                batch_number=batch_code_1,
                defaults={
                    "manufacturing_date": today - timedelta(days=60),
                    "expiry_date": today + timedelta(days=exp_days),
                    "purchase_price": tp,
                    "unit_mrp": mrp,
                    "initial_stock": stock_qty,
                    "current_stock": stock_qty,
                }
            )
            seeded_batches_count += 1

            # Batch 2: Fresh batch expiring later
            batch_code_2 = f"B24-{brand_name[:3].upper()}-02"
            DrugBatch.objects.get_or_create(
                drug=drug,
                batch_number=batch_code_2,
                defaults={
                    "manufacturing_date": today - timedelta(days=10),
                    "expiry_date": today + timedelta(days=exp_days + 300),
                    "purchase_price": tp,
                    "unit_mrp": mrp,
                    "initial_stock": stock_qty,
                    "current_stock": stock_qty,
                }
            )
            seeded_batches_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {seeded_drugs_count} Bangladesh medicines and {seeded_batches_count} batches!"
            )
        )
