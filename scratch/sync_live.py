import paramiko

HOST = '195.250.26.201'
PORT = 22
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'
REMOTE_BASE = '/home/webkoders/pos.webkoders.com'

files_to_sync = [
    (r'd:\phermacy\pos\views.py', f'{REMOTE_BASE}/pos/views.py'),
    (r'd:\phermacy\inventory\services.py', f'{REMOTE_BASE}/inventory/services.py'),
    (r'd:\phermacy\templates\pos\pos.html', f'{REMOTE_BASE}/templates/pos/pos.html'),
]

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)
sftp = ssh.open_sftp()

for local_p, remote_p in files_to_sync:
    print(f"Uploading {local_p} -> {remote_p}")
    sftp.put(local_p, remote_p)

sftp.close()

# Restart the application
print("Restarting app via restart.txt...")
cmd = f'touch {REMOTE_BASE}/tmp/restart.txt'
stdin, stdout, stderr = ssh.exec_command(cmd)
stdout.read()

# Verify syntax on remote python
check_cmd = f'/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python {REMOTE_BASE}/manage.py check'
print("Running remote manage.py check...")
stdin, stdout, stderr = ssh.exec_command(check_cmd)
out = stdout.read().decode('utf-8')
err = stderr.read().decode('utf-8')
if out:
    print("Remote check output:", out)
if err:
    print("Remote check error:", err)

ssh.close()
print("All files synchronized and remote app successfully restarted!")
