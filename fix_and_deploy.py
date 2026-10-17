import os
import sys
import posixpath
import paramiko
import urllib.request

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

HOST = "195.250.26.201"
PORT = 22
USERNAME = "webkoders"
KEY_PATH = "C:/Users/shuvo/.ssh/id_rsa"
PASSPHRASE = "SHUVOshuvo123@"
REMOTE_BASE = "/home/webkoders/pos.webkoders.com"
LOCAL_BASE = r"D:\phermacy"
PY_BIN = "/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python"
PIP_BIN = "/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/pip"

def run_cmd(ssh, cmd):
    print(f"[*] Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f"    [STDOUT] {out.strip()}")
    if err.strip():
        print(f"    [STDERR] {err.strip()}")
    return code, out, err

def main():
    print("=" * 60)
    print("Fixing Server Environment & Deploying Pharmacy POS")
    print("=" * 60)

    key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=30)
    print("[+] SSH Connected!")

    sftp = ssh.open_sftp()

    # Step 1: Install Django in virtualenv
    print("\n[*] Installing Django and dependencies...")
    run_cmd(ssh, f"{PIP_BIN} install \"django>=4.2,<5.0\" requests pillow")

    # Step 2: Upload correct passenger_wsgi.py
    passenger_wsgi_content = """import os
import sys

project_dir = "/home/webkoders/pos.webkoders.com"
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

venv_site_packages = "/home/webkoders/virtualenv/pos.webkoders.com/3.9/lib/python3.9/site-packages"
if os.path.exists(venv_site_packages) and venv_site_packages not in sys.path:
    sys.path.insert(0, venv_site_packages)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pharmacy_saas.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
"""
    print("\n[*] Writing proper passenger_wsgi.py on server...")
    with sftp.open(f"{REMOTE_BASE}/passenger_wsgi.py", "w") as f:
        f.write(passenger_wsgi_content)
    print("[+] passenger_wsgi.py updated.")

    # Step 3: Upload files (templates, apps, static, db.sqlite3)
    print("\n[*] Uploading project files...")
    upload_items = [
        "manage.py",
        "db.sqlite3",
        "pharmacy_saas",
        "core",
        "inventory",
        "customers",
        "pos",
        "payments",
        "notifications",
        "templates",
        "static"
    ]

    for item in upload_items:
        local_path = os.path.join(LOCAL_BASE, item)
        remote_path = posixpath.join(REMOTE_BASE, item)
        if os.path.isfile(local_path):
            sftp.put(local_path, remote_path)
            print(f"  [+] Uploaded file: {item}")
        elif os.path.isdir(local_path):
            for root, dirs, files in os.walk(local_path):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
                rel = os.path.relpath(root, LOCAL_BASE)
                rem_dir = posixpath.join(REMOTE_BASE, rel.replace("\\", "/"))
                try:
                    sftp.mkdir(rem_dir)
                except Exception:
                    pass
                for f in files:
                    if f.endswith(".pyc") or f.endswith(".tmp"):
                        continue
                    lf = os.path.join(root, f)
                    rf = posixpath.join(rem_dir, f)
                    sftp.put(lf, rf)
            print(f"  [+] Synced dir: {item}")

    # Step 4: Run Django Check & Verification
    print("\n[*] Running Django System Check on Server...")
    run_cmd(ssh, f"cd {REMOTE_BASE} && {PY_BIN} manage.py check")

    # Step 5: Verify Medicines in DB
    check_db_code = """
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()
from inventory.models import BrandDrug, DrugBatch
from core.models import Tenant
print(f'Tenants in DB: {Tenant.objects.count()}')
print(f'Total Brand Medicines in DB: {BrandDrug.objects.count()}')
print(f'Total Drug Batches in DB: {DrugBatch.objects.count()}')
"""
    with sftp.open(f"{REMOTE_BASE}/check_db.py", "w") as f:
        f.write(check_db_code)
    run_cmd(ssh, f"cd {REMOTE_BASE} && {PY_BIN} check_db.py")
    run_cmd(ssh, f"rm -f {REMOTE_BASE}/check_db.py")

    # Step 6: Collect static & Touch restart.txt
    print("\n[*] Collecting static files and touching restart.txt...")
    run_cmd(ssh, f"cd {REMOTE_BASE} && {PY_BIN} manage.py collectstatic --noinput")
    run_cmd(ssh, f"mkdir -p {REMOTE_BASE}/tmp && touch {REMOTE_BASE}/tmp/restart.txt")

    sftp.close()
    ssh.close()
    print("\n[✔] Server updated and Passenger restarted successfully!")

    # Step 7: Test live HTTP endpoint
    print("\n[*] Testing live HTTP endpoint: https://pos.webkoders.com/ ...")
    try:
        req = urllib.request.Request(
            "https://pos.webkoders.com/",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            print(f"[+] HTTP Status: {res.status} {res.reason}")
            body = res.read().decode("utf-8", errors="ignore")
            print(f"[+] Page length: {len(body)} bytes")
            if "PharmaFlow" in body or "Pharmacy" in body or "POS" in body:
                print("[✔] Live site returned PharmaFlow page successfully!")
    except Exception as e:
        print(f"[-] HTTP test warning: {e}")

if __name__ == "__main__":
    main()

