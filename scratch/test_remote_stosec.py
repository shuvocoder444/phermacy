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

from inventory.models import BrandDrug
from inventory.services import DrugSearchAndCacheService

qs = BrandDrug.objects.filter(brand_name__icontains='Stosec')
print('Stosec count on live DB:', qs.count())
for d in qs:
    print('Drug:', d.brand_name, d.strength, d.dosage_form)

# Test search service
res = DrugSearchAndCacheService.search_drugs('stosec', tenant_id='default_tenant', limit=5)
print('Search service results for stosec:', len(res))
if res:
    print('First res:', res[0]['brand_name'])
"""

client.exec_command("cat << 'EOF' > /home/webkoders/pos.webkoders.com/test_stosec.py\n" + script + "\nEOF")
stdin, stdout, stderr = client.exec_command("/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/test_stosec.py")
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
client.close()

