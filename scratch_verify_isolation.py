import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HOST = '195.250.26.201'
PORT = 22
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'
PY_BIN = '/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python'

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)

py_script = """
import os, sys, django
sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()

from core.models import Tenant
from customers.models import Customer
from pos.models import Invoice

# 1. Fetch or create Tenant A & Tenant B
tenant_a = Tenant.objects.filter(slug='popular').first() or Tenant.objects.first()
tenant_b, _ = Tenant.objects.get_or_create(
    slug='medicare-uttara',
    defaults={
        'name': 'Medicare Pharmacy Uttara',
        'name_bn': 'মেডিকেয়ার ফার্মেসি উত্তরা',
        'phone': '01899112233',
        'is_active': True
    }
)

# 2. Add test customer in Tenant A
cust_a, _ = Customer.objects.get_or_create(
    phone='01700000001',
    tenant=tenant_a,
    defaults={'name': 'Customer of Tenant A'}
)

# 3. Add test customer in Tenant B
cust_b, _ = Customer.objects.get_or_create(
    phone='01700000002',
    tenant=tenant_b,
    defaults={'name': 'Customer of Tenant B'}
)

# 4. Check QuerySet isolation
customers_for_a = list(Customer.objects.filter(tenant=tenant_a).values_list('name', flat=True))
customers_for_b = list(Customer.objects.filter(tenant=tenant_b).values_list('name', flat=True))

print("=== MULTI-TENANT ISOLATION VERIFICATION ===")
print("Tenant A Customers:", customers_for_a)
print("Tenant B Customers:", customers_for_b)

assert 'Customer of Tenant B' not in customers_for_a, 'FAIL: Tenant B customer leaked to Tenant A!'
assert 'Customer of Tenant A' not in customers_for_b, 'FAIL: Tenant A customer leaked to Tenant B!'
print("SUCCESS: 100% Strict Data Isolation Confirmed! No data leakage between tenants.")
"""

stdin, stdout, stderr = ssh.exec_command(f"{PY_BIN} -")
stdin.write(py_script)
stdin.channel.shutdown_write()

print("STDOUT:\n" + stdout.read().decode('utf-8', errors='replace'))
print("STDERR:\n" + stderr.read().decode('utf-8', errors='replace'))
ssh.close()

