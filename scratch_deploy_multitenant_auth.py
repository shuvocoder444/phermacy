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
    f'{REMOTE_BASE}/templates/auth',
    f'{REMOTE_BASE}/templates/saas_admin',
    f'{REMOTE_BASE}/templates/tenant',
    f'{REMOTE_BASE}/core',
    f'{REMOTE_BASE}/pos',
    f'{REMOTE_BASE}/customers',
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
    # Models & Backend logic
    (r'd:\phermacy\core\models.py', f'{REMOTE_BASE}/core/models.py'),
    (r'd:\phermacy\core\middleware.py', f'{REMOTE_BASE}/core/middleware.py'),
    (r'd:\phermacy\core\auth_views.py', f'{REMOTE_BASE}/core/auth_views.py'),
    (r'd:\phermacy\core\saas_services.py', f'{REMOTE_BASE}/core/saas_services.py'),
    (r'd:\phermacy\core\saas_admin_views.py', f'{REMOTE_BASE}/core/saas_admin_views.py'),
    (r'd:\phermacy\core\saas_admin_urls.py', f'{REMOTE_BASE}/core/saas_admin_urls.py'),
    (r'd:\phermacy\core\tenant_dashboard_views.py', f'{REMOTE_BASE}/core/tenant_dashboard_views.py'),
    (r'd:\phermacy\core\tenant_dashboard_urls.py', f'{REMOTE_BASE}/core/tenant_dashboard_urls.py'),
    (r'd:\phermacy\core\ledger_views.py', f'{REMOTE_BASE}/core/ledger_views.py'),
    
    (r'd:\phermacy\pos\models.py', f'{REMOTE_BASE}/pos/models.py'),
    (r'd:\phermacy\pos\services.py', f'{REMOTE_BASE}/pos/services.py'),
    (r'd:\phermacy\pos\views.py', f'{REMOTE_BASE}/pos/views.py'),
    
    (r'd:\phermacy\customers\models.py', f'{REMOTE_BASE}/customers/models.py'),
    (r'd:\phermacy\customers\views.py', f'{REMOTE_BASE}/customers/views.py'),
    
    (r'd:\phermacy\inventory\models.py', f'{REMOTE_BASE}/inventory/models.py'),
    (r'd:\phermacy\inventory\services.py', f'{REMOTE_BASE}/inventory/services.py'),
    
    (r'd:\phermacy\pharmacy_saas\urls.py', f'{REMOTE_BASE}/pharmacy_saas/urls.py'),
    
    # Templates
    (r'd:\phermacy\templates\auth\login.html', f'{REMOTE_BASE}/templates/auth/login.html'),
    (r'd:\phermacy\templates\tenant\dashboard.html', f'{REMOTE_BASE}/templates/tenant/dashboard.html'),
    (r'd:\phermacy\templates\saas_admin\dashboard.html', f'{REMOTE_BASE}/templates/saas_admin/dashboard.html'),
    (r'd:\phermacy\templates\saas_admin\tenant_detail.html', f'{REMOTE_BASE}/templates/saas_admin/tenant_detail.html'),
    (r'd:\phermacy\templates\pos\pos.html', f'{REMOTE_BASE}/templates/pos/pos.html'),
]

for local_path, remote_path in files_to_upload:
    print(f"Uploading {local_path} -> {remote_path}...")
    sftp.put(local_path, remote_path)

sftp.close()
print("Files uploaded successfully!")

# Run makemigrations and migrate on remote server
commands = [
    (
        "Make Migrations",
        f"source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && "
        f"cd {REMOTE_BASE} && python manage.py makemigrations core pos customers inventory"
    ),
    (
        "Apply Migrations",
        f"source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && "
        f"cd {REMOTE_BASE} && python manage.py migrate"
    ),
    (
        "Backfill Tenant Data & Verify Superuser",
        f"source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && "
        f"cd {REMOTE_BASE} && python manage.py shell -c \""
        f"from core.models import Tenant, StaffProfile; "
        f"from pos.models import Invoice, CashRegisterSession; "
        f"from customers.models import Customer, DueLedger; "
        f"from core.models import IncomeExpenseEntry; "
        f"from inventory.models import DrugBatch; "
        f"from django.contrib.auth.models import User; "
        f"t = Tenant.objects.first(); "
        f"if not t: "
        f"    t = Tenant.objects.create(name='Popular Pharmacy & Care', slug='popular', phone='01711000000', is_active=True); "
        f"print('Active Tenant:', t.name, t.id); "
        f"c_inv = Invoice.objects.filter(tenant__isnull=True).update(tenant=t); "
        f"c_cust = Customer.objects.filter(tenant__isnull=True).update(tenant=t); "
        f"c_due = DueLedger.objects.filter(tenant__isnull=True).update(tenant=t); "
        f"c_inc = IncomeExpenseEntry.objects.filter(tenant__isnull=True).update(tenant=t); "
        f"c_bat = DrugBatch.objects.filter(tenant__isnull=True).update(tenant=t); "
        f"c_reg = CashRegisterSession.objects.filter(tenant__isnull=True).update(tenant=t); "
        f"print(f'Backfilled: Invoices={{c_inv}}, Customers={{c_cust}}, Due={{c_due}}, Ledger={{c_inc}}, Batches={{c_bat}}'); "
        f"from core.saas_services import ensure_default_subscription_plans, ensure_tenant_subscription; "
        f"ensure_default_subscription_plans(); "
        f"ensure_tenant_subscription(t); "
        f"print('Users list:', list(User.objects.values('username', 'is_superuser'))); "
        f"from django.core.cache import cache; cache.clear(); "
        f"print('Cache cleared successfully!'); \""
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
print("\nAll deployment and migration steps completed!")

