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

from django.contrib.auth.models import User
from core.models import Tenant, StaffProfile

print("=== CURRENT USERS ===")
for u in User.objects.all():
    prof = getattr(u, 'staff_profile', None)
    t_name = prof.tenant.name if (prof and prof.tenant) else "None"
    print(f"Username: '{u.username}', SuperUser: {u.is_superuser}, Active: {u.is_active}, Tenant: '{t_name}'")

print("\\n=== TENANTS ===")
for t in Tenant.objects.all():
    print(f"Tenant: '{t.name}' (Slug: '{t.slug}', Active: {t.is_active})")
"""

stdin, stdout, stderr = ssh.exec_command(f"{PY_BIN} -")
stdin.write(py_script)
stdin.channel.shutdown_write()

print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()

