import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('195.250.26.201', username='webkoders', key_filename=r'C:/Users/shuvo/.ssh/id_rsa', passphrase='SHUVOshuvo123@')

test_script = """
import os, sys
sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
import django
django.setup()
from django.test import RequestFactory
from pos import views, voice_service

rf = RequestFactory()

# 1. Test AI Config GET
get_req = rf.get('/pos/ai/config/')
resp_get = views.ai_config_view(get_req)
print('AI Config GET:', resp_get.content.decode('utf-8'))

# 2. Test Voice search for 'এন্টাসিড প্লাস ১০টা'
voice_req = rf.post('/pos/voice/search/', {'transcript': 'এন্টাসিড প্লাস ১০টা', 'format': 'json'})
resp_voice = voice_service.voice_medicine_search(voice_req)
print('Voice Search JSON:', resp_voice.content.decode('utf-8'))
"""

sftp = ssh.open_sftp()
with sftp.open('/home/webkoders/pos.webkoders.com/test_voice_ai.py', 'wb') as f:
    f.write(test_script.encode('utf-8'))
sftp.close()

stdin, stdout, stderr = ssh.exec_command('/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/test_voice_ai.py')
print('STDOUT:\n', stdout.read().decode())
print('STDERR:\n', stderr.read().decode())
ssh.close()
