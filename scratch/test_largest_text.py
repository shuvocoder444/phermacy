import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('195.250.26.201', username='webkoders', key_filename=r'C:/Users/shuvo/.ssh/id_rsa', passphrase='SHUVOshuvo123@')

script = """
import os, sys, cv2
os.environ['TESSDATA_PREFIX'] = '/home/webkoders/tessdata'
import pytesseract
pytesseract.pytesseract.tesseract_cmd = '/home/webkoders/.local/bin/tesseract'

img = cv2.imread('/home/webkoders/pos.webkoders.com/test_entacyd.jpg')
img2x = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
data = pytesseract.image_to_data(img2x, config='--psm 11 -l eng', output_type=pytesseract.Output.DICT)

words_with_sizes = []
for i in range(len(data['text'])):
    w = data['text'][i].strip()
    h = data['height'][i]
    conf = int(data['conf'][i])
    if len(w) >= 3 and conf > 20:
        words_with_sizes.append((w, h, conf))

# Sort by height (font size) descending
words_with_sizes.sort(key=lambda x: x[1], reverse=True)
print('Top 10 Biggest Words by Font Size (Height):')
for w, h, c in words_with_sizes[:10]:
    print(f'Word: {w:<15} Height: {h}px Conf: {c}')
"""

sftp = ssh.open_sftp()
with sftp.open('/home/webkoders/pos.webkoders.com/test_largest_text.py', 'wb') as f:
    f.write(script.encode('utf-8'))
sftp.close()

stdin, stdout, stderr = ssh.exec_command('/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python /home/webkoders/pos.webkoders.com/test_largest_text.py')
print('STDOUT:\n', stdout.read().decode())
print('STDERR:\n', stderr.read().decode())
ssh.close()

