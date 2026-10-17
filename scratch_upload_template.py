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

print("Uploading pos.html...")
sftp.put(r'd:\phermacy\templates\pos\pos.html', f'{REMOTE_BASE}/templates/pos/pos.html')

sftp.close()

c = f'touch {REMOTE_BASE}/tmp/restart.txt'
ssh.exec_command(c)
ssh.close()
print('Done.')

