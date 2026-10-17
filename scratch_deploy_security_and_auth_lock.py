import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HOST = '195.250.26.201'
PORT = 22
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'
REMOTE_BASE = '/home/webkoders/pos.webkoders.com'
PY_BIN = '/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python'

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)
sftp = ssh.open_sftp()

files_to_upload = [
    (r'd:\phermacy\core\decorators.py', f'{REMOTE_BASE}/core/decorators.py'),
    (r'd:\phermacy\core\middleware.py', f'{REMOTE_BASE}/core/middleware.py'),
    (r'd:\phermacy\core\saas_admin_views.py', f'{REMOTE_BASE}/core/saas_admin_views.py'),
    (r'd:\phermacy\core\tenant_dashboard_views.py', f'{REMOTE_BASE}/core/tenant_dashboard_views.py'),
    (r'd:\phermacy\core\ledger_views.py', f'{REMOTE_BASE}/core/ledger_views.py'),
    (r'd:\phermacy\customers\views.py', f'{REMOTE_BASE}/customers/views.py'),
    (r'd:\phermacy\inventory\views.py', f'{REMOTE_BASE}/inventory/views.py'),
    (r'd:\phermacy\pos\views.py', f'{REMOTE_BASE}/pos/views.py'),
]

for local_path, remote_path in files_to_upload:
    print(f"Uploading {local_path} -> {remote_path}...")
    sftp.put(local_path, remote_path)

sftp.close()
print("All security locked views uploaded successfully!")

# Set test passwords & ensure tenant owner exists
py_setup = """
import os, sys, django
sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Tenant, StaffProfile
from core.saas_services import ensure_tenant_subscription

# 1. Ensure Super Admin user
admin_user, _ = User.objects.get_or_create(username='admin', defaults={'is_superuser': True, 'is_staff': True})
admin_user.is_superuser = True
admin_user.is_staff = True
admin_user.set_password('Admin1234@#')
admin_user.save()
print("Super Admin password set: username='admin', password='Admin1234@#'")

# 2. Ensure Tenant Pharmacy Owner user
tenant_b = Tenant.objects.filter(slug='medicare-uttara').first()
if not tenant_b:
    tenant_b = Tenant.objects.create(
        name='Medicare Pharmacy Uttara',
        name_bn='মেডিকেয়ার ফার্মেসি উত্তরা',
        slug='medicare-uttara',
        phone='01899112233',
        is_active=True
    )

owner_user, _ = User.objects.get_or_create(username='uttara_owner')
owner_user.is_superuser = False
owner_user.is_staff = False
owner_user.first_name = "উত্তরা ফার্মেসি ওনার"
owner_user.set_password('Owner1234@#')
owner_user.save()

profile, created = StaffProfile.objects.get_or_create(user=owner_user, defaults={'tenant': tenant_b, 'role': 'OWNER', 'is_active': True})
if not created:
    profile.tenant = tenant_b
    profile.role = 'OWNER'
    profile.is_active = True
    profile.save()

ensure_tenant_subscription(tenant_b)

print(f"Tenant Owner set: username='uttara_owner', password='Owner1234@#' bound to {tenant_b.name}")

from django.core.cache import cache
cache.clear()
print("Cache cleared!")
"""

stdin, stdout, stderr = ssh.exec_command(f"{PY_BIN} -")
stdin.write(py_setup)
stdin.channel.shutdown_write()

print("STDOUT:\n" + stdout.read().decode('utf-8', errors='replace'))
print("STDERR:\n" + stderr.read().decode('utf-8', errors='replace'))

# Restart passenger
stdin, stdout, stderr = ssh.exec_command(f"touch {REMOTE_BASE}/tmp/restart.txt")
print("Passenger reloaded.")
ssh.close()
