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

from core.models import Tenant, StaffProfile
from django.contrib.auth.models import User

t = Tenant.objects.first()
print("Tenant:", t.name)

for u in User.objects.all():
    profile = StaffProfile.objects.filter(user=u).first()
    if not profile:
        profile = StaffProfile.objects.create(
            user=u,
            tenant=t,
            role='ADMIN' if u.is_superuser else 'CASHIER',
            is_active=True
        )
        print(f"Created StaffProfile for: {u.username}")
    else:
        if not profile.tenant:
            profile.tenant = t
            profile.save()
        print(f"StaffProfile exists for: {u.username} -> Tenant: {profile.tenant.name}")

print("Total Users:", User.objects.count())
"""

stdin, stdout, stderr = ssh.exec_command(f"{PY_BIN} -")
stdin.write(py_script)
stdin.channel.shutdown_write()

print("STDOUT:\n" + stdout.read().decode('utf-8', errors='replace'))
print("STDERR:\n" + stderr.read().decode('utf-8', errors='replace'))
ssh.close()

