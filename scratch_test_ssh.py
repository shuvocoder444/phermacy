import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
key = paramiko.RSAKey.from_private_key_file('C:/Users/shuvo/.ssh/id_rsa', password='SHUVOshuvo123@')
ssh.connect('195.250.26.201', username='webkoders', pkey=key)

test_code = """
import os, sys, django
sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

c = Client()
u = User.objects.get(username='admin')
c.force_login(u)
try:
    res = c.get('/saas-admin/')
    print('STATUS_CODE:', res.status_code)
except Exception as e:
    import traceback
    traceback.print_exc()
"""

stdin, stdout, stderr = ssh.exec_command("/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python", get_pty=True)
stdin.write(test_code)
stdin.channel.shutdown_write()
print("STDOUT:", stdout.read().decode())
print("STDERR:", stderr.read().decode())
ssh.close()

