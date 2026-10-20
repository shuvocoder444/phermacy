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
print("API Key present:", bool(api_key), "Length:", len(api_key))
if api_key:
    print("API Key preview:", api_key[:8] + "..." + api_key[-4:])
    r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}")
    print("Status:", r.status_code)
    if r.status_code == 200:
        models = [m['name'] for m in r.json().get('models', [])]
        print("Available models:", models[:15])
    else:
        print("Error response:", r.text[:400])
"""

client.exec_command("cat << 'EOF' > /home/webkoders/pos.webkoders.com/test_gem.py\n" + script + "\nEOF")
stdin, stdout, stderr = client.exec_command("/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/test_gem.py")
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
client.close()

