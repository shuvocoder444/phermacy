import paramiko

REMOTE_BASE = "/home/webkoders/pos.webkoders.com"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
key = paramiko.RSAKey.from_private_key_file('C:/Users/shuvo/.ssh/id_rsa', password='SHUVOshuvo123@')
ssh.connect('195.250.26.201', username='webkoders', pkey=key)

sftp = ssh.open_sftp()

files = [
    (r"d:\phermacy\templates\partials\tenant_sidebar.html", f"{REMOTE_BASE}/templates/partials/tenant_sidebar.html"),
    (r"d:\phermacy\templates\pos\pos.html", f"{REMOTE_BASE}/templates/pos/pos.html"),
    (r"d:\phermacy\pos\views.py", f"{REMOTE_BASE}/pos/views.py"),
]

for local_path, remote_path in files:
    print(f"Uploading {local_path} -> {remote_path}...")
    sftp.put(local_path, remote_path)

sftp.close()

# Reload passenger
stdin, stdout, stderr = ssh.exec_command(f"touch {REMOTE_BASE}/tmp/restart.txt")
print("Passenger reloaded.")
ssh.close()
print("POS unified sidebar deployed successfully!")

