import paramiko
import sys

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

from customers.models import Customer
d = Customer.objects.filter(phone__in=['01700000001', '01700000002']).delete()
print('Cleaned up test customers:', d)
"""

stdin, stdout, stderr = ssh.exec_command(f"{PY_BIN} -")
stdin.write(py_script)
stdin.channel.shutdown_write()
print(stdout.read().decode())
ssh.close()

