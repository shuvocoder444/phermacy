import paramiko
import sys
import posixpath

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HOST = '195.250.26.201'
PORT = 22
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'
REMOTE_BASE = '/home/webkoders/pos.webkoders.com'
PY_BIN = '/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python'

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)
sftp = ssh.open_sftp()

# Ensure remote directories
remote_dirs = [
    f'{REMOTE_BASE}/templates/inventory',
    f'{REMOTE_BASE}/templates/inventory/partials',
    f'{REMOTE_BASE}/templates/auth',
    f'{REMOTE_BASE}/templates/pos/partials',
    f'{REMOTE_BASE}/inventory',
]
for d in remote_dirs:
    try:
        sftp.stat(d)
    except IOError:
        try:
            sftp.mkdir(d)
            print(f"Created remote dir: {d}")
        except Exception as e:
            print(f"Dir note: {e}")

files_to_upload = [
    # Core & Auth
    (r'd:\phermacy\core\auth_views.py', f'{REMOTE_BASE}/core/auth_views.py'),
    (r'd:\phermacy\pharmacy_saas\urls.py', f'{REMOTE_BASE}/pharmacy_saas/urls.py'),
    
    # Inventory
    (r'd:\phermacy\inventory\views.py', f'{REMOTE_BASE}/inventory/views.py'),
    (r'd:\phermacy\inventory\urls.py', f'{REMOTE_BASE}/inventory/urls.py'),
    (r'd:\phermacy\templates\inventory\stock_dashboard.html', f'{REMOTE_BASE}/templates/inventory/stock_dashboard.html'),
    (r'd:\phermacy\templates\inventory\partials\stock_table.html', f'{REMOTE_BASE}/templates/inventory/partials/stock_table.html'),
    
    # POS
    (r'd:\phermacy\pos\views.py', f'{REMOTE_BASE}/pos/views.py'),
    (r'd:\phermacy\pos\urls.py', f'{REMOTE_BASE}/pos/urls.py'),
    (r'd:\phermacy\templates\pos\pos.html', f'{REMOTE_BASE}/templates/pos/pos.html'),
    (r'd:\phermacy\templates\pos\partials\recent_invoices_modal.html', f'{REMOTE_BASE}/templates/pos/partials/recent_invoices_modal.html'),
    (r'd:\phermacy\templates\pos\partials\held_carts_modal.html', f'{REMOTE_BASE}/templates/pos/partials/held_carts_modal.html'),
    
    # Templates & Navigation
    (r'd:\phermacy\templates\auth\register.html', f'{REMOTE_BASE}/templates/auth/register.html'),
    (r'd:\phermacy\templates\auth\login.html', f'{REMOTE_BASE}/templates/auth/login.html'),
    (r'd:\phermacy\templates\tenant\dashboard.html', f'{REMOTE_BASE}/templates/tenant/dashboard.html'),
    (r'd:\phermacy\templates\landing.html', f'{REMOTE_BASE}/templates/landing.html'),
    (r'd:\phermacy\templates\customers\dashboard.html', f'{REMOTE_BASE}/templates/customers/dashboard.html'),
    (r'd:\phermacy\templates\ledger\dashboard.html', f'{REMOTE_BASE}/templates/ledger/dashboard.html'),
]

for local_path, remote_path in files_to_upload:
    print(f"Uploading {local_path} -> {remote_path}...")
    sftp.put(local_path, remote_path)

sftp.close()
print("All professional SaaS files uploaded successfully!")

# Clear cache and restart passenger
commands = [
    (
        "Clear Cache",
        f"source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && "
        f"cd {REMOTE_BASE} && python manage.py shell -c \""
        f"from django.core.cache import cache; cache.clear(); "
        f"print('Cache cleared successfully!')\""
    ),
    (
        "Restart Passenger",
        f"touch {REMOTE_BASE}/tmp/restart.txt"
    ),
]

for label, cmd in commands:
    print(f"\n--- Running: {label} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out:
        print(out)
    if err:
        print("ERR/WARNING:", err)

ssh.close()
print("\nProfessional SaaS Deployment complete!")

