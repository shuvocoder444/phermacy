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

batches = DrugBatch.objects.filter(current_stock__gt=0).select_related('drug', 'tenant')
print('Total active batches with stock > 0:', batches.count())
for b in batches[:20]:
    t_name = b.tenant.name if b.tenant else 'No Tenant'
    d_name = b.drug.brand_name if b.drug else 'No Drug'
    print(f'Batch: {b.batch_number} | Drug: {d_name} | Stock: {b.current_stock} | Tenant: {t_name}')
"""

client.exec_command("cat << 'EOF' > /home/webkoders/pos.webkoders.com/test_batches.py\n" + script + "\nEOF")
stdin, stdout, stderr = client.exec_command("/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/test_batches.py")
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
client.close()

