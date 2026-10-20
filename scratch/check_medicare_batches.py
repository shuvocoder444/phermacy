import paramiko

HOST = '195.250.26.201'
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USERNAME, pkey=key, timeout=15)

script = """
import os, sys
sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
import django
django.setup()

from inventory.models import DrugBatch, BrandDrug
from core.models import Tenant

t = Tenant.objects.filter(name__icontains='Medicare').first()
print('Found tenant:', t.id, t.name)
batches = DrugBatch.objects.filter(tenant=t)
print(f'Total batches for {t.name}:', batches.count())
for b in batches:
    print(f'Batch ID: {b.id} | Batch#: {b.batch_number} | Drug: {b.drug.brand_name} | Stock: {b.current_stock} | Exp: {b.expiry_date}')
"""

client.exec_command("cat << 'EOF' > /home/webkoders/pos.webkoders.com/test_medicare.py\n" + script + "\nEOF")
stdin, stdout, stderr = client.exec_command("/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/test_medicare.py")
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
client.close()

