import paramiko

REMOTE_BASE = "/home/webkoders/pos.webkoders.com"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
key = paramiko.RSAKey.from_private_key_file('C:/Users/shuvo/.ssh/id_rsa', password='SHUVOshuvo123@')
ssh.connect('195.250.26.201', username='webkoders', pkey=key)

sftp = ssh.open_sftp()

files = [
    (r"d:\phermacy\templates\auth\login.html", f"{REMOTE_BASE}/templates/auth/login.html"),
    (r"d:\phermacy\templates\auth\register.html", f"{REMOTE_BASE}/templates/auth/register.html"),
]

for local_path, remote_path in files:
    print(f"Uploading {local_path} -> {remote_path}...")
    sftp.put(local_path, remote_path)

sftp.close()

# Touch restart
ssh.exec_command(f"touch {REMOTE_BASE}/tmp/restart.txt")
print("Uploaded templates and restarted Passenger!")
ssh.close()

