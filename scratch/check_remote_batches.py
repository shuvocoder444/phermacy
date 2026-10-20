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

remote_python = '/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python'
script = """
from core.models import Tenant
from inventory.models import DrugBatch
for t in Tenant.objects.all():
    batches = DrugBatch.objects.filter(tenant=t)
    print(f'Tenant: {t.name} (id={t.id}), Total Batches: {batches.count()}')
    for b in batches:
        print(f'  - {b.drug.brand_name} (Batch: {b.batch_number}, Stock: {b.current_stock}, Exp: {b.expiry_date})')

no_tenant_batches = DrugBatch.objects.filter(tenant__isnull=True)
print(f'No Tenant Batches: {no_tenant_batches.count()}')
"""

stdin, stdout, stderr = ssh.exec_command(f"{remote_python} {REMOTE_BASE}/manage.py shell -c \"{script}\"")
print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))
ssh.close()

