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

script = """
from inventory.models import BrandDrug, DrugBatch
print('Drugs:', BrandDrug.objects.count())
print('Batches:', DrugBatch.objects.count())
"""

c = f'source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && cd {REMOTE_BASE} && python manage.py shell -c "{script}"'

stdin, stdout, stderr = ssh.exec_command(c)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()

