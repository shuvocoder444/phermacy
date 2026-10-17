import os
import sys
import paramiko
import urllib.request
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

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

files_to_sync = [
    (r'D:\phermacy\inventory\services.py', f'{REMOTE_BASE}/inventory/services.py'),
    (r'D:\phermacy\templates\base.html', f'{REMOTE_BASE}/templates/base.html'),
    (r'D:\phermacy\templates\pos\pos.html', f'{REMOTE_BASE}/templates/pos/pos.html'),
    (r'D:\phermacy\templates\pos\partials\search_results.html', f'{REMOTE_BASE}/templates/pos/partials/search_results.html'),
    (r'D:\phermacy\pos\views.py', f'{REMOTE_BASE}/pos/views.py'),
    (r'D:\phermacy\pos\voice_service.py', f'{REMOTE_BASE}/pos/voice_service.py'),
    (r'D:\phermacy\pos\ocr_service.py', f'{REMOTE_BASE}/pos/ocr_service.py'),
]

for local_f, remote_f in files_to_sync:
    sftp.put(local_f, remote_f)
    print(f'[+] Synced: {local_f}')

ssh.exec_command(f'touch {REMOTE_BASE}/tmp/restart.txt')
print('[+] Touched tmp/restart.txt')

sftp.close()
ssh.close()

time.sleep(2)

test_queries = ['napa', 'sergel', 'monas', 'syrup', 'fexo', 'ace']
for q in test_queries:
    url = f'https://pos.webkoders.com/pos/search/?q={q}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'HX-Request': 'true'})
    with urllib.request.urlopen(req, timeout=10) as res:
        content = res.read().decode('utf-8', errors='ignore')
        matched = 'search-result-item' in content
        print(f'[OK] Live Search "{q}" -> Found: {matched} ({len(content)} bytes)')

