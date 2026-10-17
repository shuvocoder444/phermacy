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

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)
sftp = ssh.open_sftp()

# Ensure remote directories exist
remote_dirs = [
    f'{REMOTE_BASE}/templates/saas_admin',
    f'{REMOTE_BASE}/templates/tenant',
    f'{REMOTE_BASE}/core',
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
    (r'd:\phermacy\core\saas_services.py', f'{REMOTE_BASE}/core/saas_services.py'),
    (r'd:\phermacy\core\saas_admin_views.py', f'{REMOTE_BASE}/core/saas_admin_views.py'),
    (r'd:\phermacy\core\saas_admin_urls.py', f'{REMOTE_BASE}/core/saas_admin_urls.py'),
    (r'd:\phermacy\core\tenant_dashboard_views.py', f'{REMOTE_BASE}/core/tenant_dashboard_views.py'),
    (r'd:\phermacy\core\tenant_dashboard_urls.py', f'{REMOTE_BASE}/core/tenant_dashboard_urls.py'),
    (r'd:\phermacy\pharmacy_saas\urls.py', f'{REMOTE_BASE}/pharmacy_saas/urls.py'),
    (r'd:\phermacy\pos\utils.py', f'{REMOTE_BASE}/pos/utils.py'),
    (r'd:\phermacy\pos\gemini_service.py', f'{REMOTE_BASE}/pos/gemini_service.py'),
    (r'd:\phermacy\pos\voice_service.py', f'{REMOTE_BASE}/pos/voice_service.py'),
    (r'd:\phermacy\pos\training_service.py', f'{REMOTE_BASE}/pos/training_service.py'),
    (r'd:\phermacy\pos\ocr_service.py', f'{REMOTE_BASE}/pos/ocr_service.py'),
    (r'd:\phermacy\templates\saas_admin\dashboard.html', f'{REMOTE_BASE}/templates/saas_admin/dashboard.html'),
    (r'd:\phermacy\templates\saas_admin\tenant_detail.html', f'{REMOTE_BASE}/templates/saas_admin/tenant_detail.html'),
    (r'd:\phermacy\templates\tenant\dashboard.html', f'{REMOTE_BASE}/templates/tenant/dashboard.html'),
    (r'd:\phermacy\templates\pos\pos.html', f'{REMOTE_BASE}/templates/pos/pos.html'),
    (r'd:\phermacy\templates\ledger\dashboard.html', f'{REMOTE_BASE}/templates/ledger/dashboard.html'),
    (r'd:\phermacy\templates\customers\dashboard.html', f'{REMOTE_BASE}/templates/customers/dashboard.html'),
    (r'd:\phermacy\templates\landing.html', f'{REMOTE_BASE}/templates/landing.html'),
]

for local_path, remote_path in files_to_upload:
    print(f"Uploading {local_path} -> {remote_path}...")
    sftp.put(local_path, remote_path)

sftp.close()

seed_cmd = (
    f'source /home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/activate && '
    f'cd {REMOTE_BASE} && python manage.py shell -c "'
    f'from core.saas_services import ensure_default_subscription_plans, ensure_tenant_subscription; '
    f'from core.models import Tenant; '
    f'plans = ensure_default_subscription_plans(); '
    f'print(\'Seeded plans:\', len(plans)); '
    f'[ensure_tenant_subscription(t) for t in Tenant.objects.all()]; '
    f'from django.core.cache import cache; cache.clear(); '
    f'print(\'SaaS seeding & cache clearing completed\')"'
)

cmds = [
    seed_cmd,
    f'touch {REMOTE_BASE}/tmp/restart.txt',
]

for c in cmds:
    print('Running command...')
    stdin, stdout, stderr = ssh.exec_command(c)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out:
        print(out)
    if err:
        print('ERR:', err)

ssh.close()
print('Full SaaS Deployment completed successfully!')
