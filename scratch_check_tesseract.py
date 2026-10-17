import paramiko

HOST = '195.250.26.201'
PORT = 22
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)

cmds = [
    'which tesseract || echo "no tesseract"',
    'find /home/webkoders -name "tesseract" 2>/dev/null || true',
    '/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python -c "import pytesseract; print(pytesseract.get_tesseract_version())" 2>&1 || true'
]

for cmd in cmds:
    print("---", cmd)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("ERR:", err)

ssh.close()

