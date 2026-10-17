import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('195.250.26.201', username='webkoders', key_filename=r'C:/Users/shuvo/.ssh/id_rsa', passphrase='SHUVOshuvo123@')

script = """
import os, sys
sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
import django
django.setup()
from inventory.models import BrandDrug

drugs = list(BrandDrug.objects.filter(brand_name__icontains='Entacyd'))
print(f'Found {len(drugs)} drugs:')
for b in drugs:
    form = b.dosage_form.name if b.dosage_form else 'None'
    gen = b.generic.name if b.generic else 'None'
    print(f'- ID: {b.id} | Name: {b.brand_name} | Form: {form} | Strength: {b.strength} | Gen: {gen} | Stock: {b.total_stock}')
"""

sftp = ssh.open_sftp()
with sftp.open('/home/webkoders/pos.webkoders.com/query_entacyd.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/query_entacyd.py')
print('STDOUT:\n', stdout.read().decode())
print('STDERR:\n', stderr.read().decode())
ssh.close()
