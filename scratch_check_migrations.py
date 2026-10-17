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

code = '''
import os, sys, django
sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()
from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT app, name FROM django_migrations ORDER BY applied;")
for row in cursor.fetchall():
    print(row)
'''

stdin, stdout, stderr = ssh.exec_command("/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python")
stdin.write(code)
stdin.channel.shutdown_write()

print("OUT:\n" + stdout.read().decode('utf-8', errors='replace'))
print("ERR:\n" + stderr.read().decode('utf-8', errors='replace'))
ssh.close()

