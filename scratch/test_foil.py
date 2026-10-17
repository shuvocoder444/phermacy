import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('195.250.26.201', username='webkoders', key_filename=r'C:/Users/shuvo/.ssh/id_rsa', passphrase='SHUVOshuvo123@')
sftp = ssh.open_sftp()

local_img = r'C:\Users\shuvo\.gemini\antigravity\brain\e4dbed86-1b54-4e49-b46a-fe9116975646\.user_uploaded\media_1791523969194_ba432a37.jpg'
sftp.put(local_img, '/home/webkoders/pos.webkoders.com/test_entacyd.jpg')

remote_script = """
import os, sys
os.environ["TESSDATA_PREFIX"] = "/home/webkoders/tessdata"
import pytesseract
pytesseract.pytesseract.tesseract_cmd = "/home/webkoders/.local/bin/tesseract"

sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
import django
django.setup()

import cv2, numpy as np
from thefuzz import process, fuzz
from inventory.models import BrandDrug

img = cv2.imread('/home/webkoders/pos.webkoders.com/test_entacyd.jpg')
print('Image loaded, shape:', img.shape)

# Tesseract standard
txt = pytesseract.image_to_string(img, config='--psm 3 -l eng').strip()
print('Tesseract Raw PSM 3:', repr(txt[:200]))

# Resize 2x
img2x = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
txt2x = pytesseract.image_to_string(img2x, config='--psm 11 -l eng').strip()
print('Tesseract 2x PSM 11:', repr(txt2x[:200]))

from pos.ocr_service import scan_medicine_ocr
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile

with open('/home/webkoders/pos.webkoders.com/test_entacyd.jpg', 'rb') as f:
    up_file = SimpleUploadedFile('test.jpg', f.read(), content_type='image/jpeg')

rf = RequestFactory()
req = rf.post('/pos/ocr/scan/', {'format': 'json'})
req.FILES['image'] = up_file

resp = scan_medicine_ocr(req)
print('Current scan_medicine_ocr response:', resp.content.decode('utf-8', errors='ignore')[:400])
"""

with sftp.open('/home/webkoders/pos.webkoders.com/test_script_foil.py', 'w') as f:
    f.write(remote_script)

sftp.close()

stdin, stdout, stderr = ssh.exec_command('/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/test_script_foil.py')
print('STDOUT:\n', stdout.read().decode())
print('STDERR:\n', stderr.read().decode())
ssh.close()
