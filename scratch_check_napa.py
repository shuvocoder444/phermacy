import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HOST = '195.250.26.201'
PORT = 22
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)

remote_code = '''
import os, sys, django
sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()
from inventory.models import BrandDrug
qs = BrandDrug.objects.filter(brand_name__iexact='Napa')
for n in qs:
    form = n.dosage_form.name if n.dosage_form else 'None'
    bc = n.batches.count()
    first_b = n.batches.first()
    b_id = str(first_b.id) if first_b else 'None'
    print(f"ID:{n.id} | Brand:{n.brand_name} | Form:{form} | Strength:{n.strength} | Batches:{bc} | Stock:{n.total_stock} | BatchID:{b_id}")
'''

stdin, stdout, stderr = ssh.exec_command("/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python")
stdin.write(remote_code)
stdin.channel.shutdown_write()

print("OUT:\n" + stdout.read().decode('utf-8', errors='replace'))
print("ERR:\n" + stderr.read().decode('utf-8', errors='replace'))
ssh.close()

