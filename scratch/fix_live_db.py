import os
import sys
import paramiko

HOST = '195.250.26.201'
PORT = 22
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'
REMOTE_BASE = '/home/webkoders/pos.webkoders.com'

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)

# Python script to run on remote
py_script = """
import os, django, sys
sys.path.append('/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()
from inventory.models import BrandDrug, DrugBatch, GenericDrug, DosageForm, Manufacturer
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

cache.delete("all_active_brand_names")

generic, _ = GenericDrug.objects.get_or_create(name='Paracetamol + Caffeine', defaults={'description': 'Analgesic'})
generic_ent, _ = GenericDrug.objects.get_or_create(name='Aluminium Hydroxide + Magnesium Hydroxide + Simethicone')
form_tab, _ = DosageForm.objects.get_or_create(name='Tablet', defaults={'short_name': 'Tab'})
mfg_edruc, _ = Manufacturer.objects.get_or_create(name='EDRUC LIMITED')
mfg_square, _ = Manufacturer.objects.get_or_create(name='SQUARE Pharmaceuticals')

ty_plus, created = BrandDrug.objects.get_or_create(
    brand_name='Ty-plus',
    defaults={'generic': generic, 'manufacturer': mfg_edruc, 'dosage_form': form_tab, 'strength': '500mg+65mg', 'brand_name_bn': 'টাই-প্লাস', 'unit_mrp': 2.50, 'unit_tp': 2.00, 'is_active': True}
)
if created:
    DrugBatch.objects.create(drug=ty_plus, batch_number='TY101', purchase_price=2.00, unit_mrp=2.50, current_stock=100, initial_stock=100, expiry_date=timezone.now().date() + timedelta(days=365))

ent_plus, created2 = BrandDrug.objects.get_or_create(
    brand_name='Entacyd Plus',
    defaults={'generic': generic_ent, 'manufacturer': mfg_square, 'dosage_form': form_tab, 'strength': '400mg+400mg+30mg', 'brand_name_bn': 'এন্টাসিড প্লাস', 'unit_mrp': 3.00, 'unit_tp': 2.50, 'is_active': True}
)
if created2:
    DrugBatch.objects.create(drug=ent_plus, batch_number='ENT102', purchase_price=2.50, unit_mrp=3.00, current_stock=100, initial_stock=100, expiry_date=timezone.now().date() + timedelta(days=365))

print('DB Seeded on live!')
"""

sftp = ssh.open_sftp()
with sftp.file(f'{REMOTE_BASE}/tmp_seed.py', 'w') as f:
    f.write(py_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command(f"source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && python {REMOTE_BASE}/tmp_seed.py")
print(stdout.read().decode())
print(stderr.read().decode())

ssh.exec_command(f'touch {REMOTE_BASE}/tmp/restart.txt')
ssh.close()
