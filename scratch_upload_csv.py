import paramiko
import os

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
sftp = ssh.open_sftp()

print("Uploading medicine.csv...")
sftp.put(r'd:\phermacy\scratch\medicine.csv', f'{REMOTE_BASE}/medicine.csv')

print("Uploading seed command...")
sftp.put(r'd:\phermacy\inventory\management\commands\seed_csv_medicines.py', f'{REMOTE_BASE}/inventory/management/commands/seed_csv_medicines.py')

sftp.close()

cmds = [
    f'source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && cd {REMOTE_BASE} && python manage.py seed_csv_medicines medicine.csv',
    f'touch {REMOTE_BASE}/tmp/restart.txt'
]

for c in cmds:
    print('Running:', c)
    stdin, stdout, stderr = ssh.exec_command(c)
    # Print incrementally so it doesn't just buffer everything at the end
    for line in iter(stdout.readline, ""):
        print(line, end="")
    err = stderr.read().decode('utf-8', errors='replace')
    if err:
        print('ERR:', err)

ssh.close()
print('Done.')

