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

from customers.views import customer_dashboard
from django.test import RequestFactory
from django.contrib.auth import get_user_model

User = get_user_model()
u = User.objects.first()
rf = RequestFactory()
req = rf.get('/customers/')
req.user = u
if hasattr(u, 'tenant_memberships') and u.tenant_memberships.exists():
    req.tenant = u.tenant_memberships.first().tenant
else:
    req.tenant = None

resp = customer_dashboard(req)
print('customer_dashboard response status code:', resp.status_code)
"""

client.exec_command("cat << 'EOF' > /home/webkoders/pos.webkoders.com/test_cust.py\n" + script + "\nEOF")
stdin, stdout, stderr = client.exec_command("/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/test_cust.py")
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
client.close()

