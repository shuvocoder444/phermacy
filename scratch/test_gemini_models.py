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

import requests
from pos.gemini_service import GeminiAIService

api_key = GeminiAIService.get_api_key()
models_to_test = [
    'gemini-flash-latest',
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-3-flash-preview',
]

for m in models_to_test:
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}'
    payload = {
        'contents': [{'parts': [{'text': 'Hello, reply with OK'}]}]
    }
    r = requests.post(url, json=payload, timeout=10)
    print(f'Model: {m} -> Status: {r.status_code}, Res: {r.text[:100]}')
"""

client.exec_command("cat << 'EOF' > /home/webkoders/pos.webkoders.com/test_models.py\n" + script + "\nEOF")
stdin, stdout, stderr = client.exec_command("/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/test_models.py")
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
client.close()

