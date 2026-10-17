import paramiko

REMOTE_BASE = "/home/webkoders/pos.webkoders.com"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
key = paramiko.RSAKey.from_private_key_file('C:/Users/shuvo/.ssh/id_rsa', password='SHUVOshuvo123@')
ssh.connect('195.250.26.201', username='webkoders', pkey=key)

# Ensure remote partials dir exists
ssh.exec_command(f"mkdir -p {REMOTE_BASE}/templates/partials")

sftp = ssh.open_sftp()

files = [
    (r"d:\phermacy\templates\partials\saas_admin_sidebar.html", f"{REMOTE_BASE}/templates/partials/saas_admin_sidebar.html"),
    (r"d:\phermacy\templates\partials\tenant_sidebar.html", f"{REMOTE_BASE}/templates/partials/tenant_sidebar.html"),
    (r"d:\phermacy\templates\saas_admin\dashboard.html", f"{REMOTE_BASE}/templates/saas_admin/dashboard.html"),
    (r"d:\phermacy\templates\tenant\dashboard.html", f"{REMOTE_BASE}/templates/tenant/dashboard.html"),
    (r"d:\phermacy\templates\inventory\stock_dashboard.html", f"{REMOTE_BASE}/templates/inventory/stock_dashboard.html"),
    (r"d:\phermacy\templates\customers\dashboard.html", f"{REMOTE_BASE}/templates/customers/dashboard.html"),
    (r"d:\phermacy\templates\ledger\dashboard.html", f"{REMOTE_BASE}/templates/ledger/dashboard.html"),
]

for local_path, remote_path in files:
    print(f"Uploading {local_path} -> {remote_path}...")
    sftp.put(local_path, remote_path)

sftp.close()

# Reload passenger
stdin, stdout, stderr = ssh.exec_command(f"touch {REMOTE_BASE}/tmp/restart.txt")
print("Passenger reloaded.")
ssh.close()
print("All sidebars deployed successfully!")

