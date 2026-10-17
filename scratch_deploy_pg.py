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
sftp = ssh.open_sftp()
sftp.put(r'D:\phermacy\pharmacy_saas\settings.py', f'{REMOTE_BASE}/pharmacy_saas/settings.py')
sftp.put(r'D:\phermacy\requirements.txt', f'{REMOTE_BASE}/requirements.txt')
sftp.close()

cmds = [
    'source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && pip install psycopg2-binary',
    'source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && cd ' + REMOTE_BASE + ' && python manage.py migrate',
    'source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && cd ' + REMOTE_BASE + ' && python manage.py seed_bd_medicines',
    'source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && cd ' + REMOTE_BASE + ' && python manage.py shell -c "from django.contrib.auth.models import User; User.objects.filter(username=\'admin\').exists() or User.objects.create_superuser(\'admin\', \'admin@example.com\', \'admin123\')"',
    f'touch {REMOTE_BASE}/tmp/restart.txt'
]

for c in cmds:
    print('Running:', c)
    stdin, stdout, stderr = ssh.exec_command(c)
    print(stdout.read().decode('utf-8', errors='replace'))
    err = stderr.read().decode('utf-8', errors='replace')
    if err:
        print('ERR:', err)

ssh.close()
print('Done.')
