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

remote_verify_code = '''
import os, sys, django
sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()

from pos.voice_service import parse_voice_command, _find_best_variant_for_form
from pos.training_service import DrugTrainingService

test_cases = [
    "নাপা সিরাপ",
    "নাপা সিরাপ ১০টা",
    "নাপা ট্যাবলেট",
    "নাপা ড্রপ",
    "নাপা",
    "napa syrup 2",
    "এন্টাসিড প্লাস",
]

print("=== VOICE COMMAND DISAMBIGUATION TESTS ===")
for text in test_cases:
    drug_q, form, qty = parse_voice_command(text)
    trained_brand = DrugTrainingService.find_match(drug_q) or drug_q
    matched_drug = _find_best_variant_for_form(trained_brand, form)
    d_form = matched_drug.dosage_form.name if (matched_drug and matched_drug.dosage_form) else "None"
    fefo = matched_drug.batches.fefo().first() if matched_drug else None
    print(f"Input: '{text}' => Brand: {matched_drug.brand_name if matched_drug else 'None'} | Form: {d_form} | Strength: {matched_drug.strength if matched_drug else ''} | Batch: {fefo.batch_number if fefo else 'None'}")
'''

stdin, stdout, stderr = ssh.exec_command("/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python")
stdin.write(remote_verify_code)
stdin.channel.shutdown_write()

print("OUT:\n" + stdout.read().decode('utf-8', errors='replace'))
print("ERR:\n" + stderr.read().decode('utf-8', errors='replace'))
ssh.close()
