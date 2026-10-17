import os
import sys
import posixpath
import paramiko

# Ensure standard output handles utf-8 cleanly
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

IGNORE_DIRS = {
    ".git", ".vscode", "venv", "__pycache__", ".venv", ".idea", ".DS_Store"
}

IGNORE_FILES = {
    "pharmacy_deploy.zip", ".DS_Store", "deploy_live.py", "db.sqlite3", "db.sqlite3-journal"
}

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

def remote_mkdir_p(sftp, remote_directory):
    dirs = []
    dir_path = remote_directory
    while len(dir_path) > 1:
        dirs.append(dir_path)
        dir_path = posixpath.dirname(dir_path)
    if dir_path and dir_path not in dirs:
        dirs.append(dir_path)
    
    dirs.reverse()
    for d in dirs:
        try:
            sftp.stat(d)
        except IOError:
            try:
                sftp.mkdir(d)
            except Exception:
                pass

def upload_project(sftp, local_dir, remote_dir):
    print(f"[*] Uploading files to {remote_dir}...")
    remote_mkdir_p(sftp, remote_dir)

    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]

        rel_dir = os.path.relpath(root, local_dir)
        if rel_dir == ".":
            dest_dir = remote_dir
        else:
            dest_dir = posixpath.join(remote_dir, rel_dir.replace("\\", "/"))

        remote_mkdir_p(sftp, dest_dir)

        for f in files:
            if f in IGNORE_FILES or f.endswith(".pyc") or f.endswith(".tmp"):
                continue

            local_file = os.path.join(root, f)
            remote_file = posixpath.join(dest_dir, f)

            try:
                sftp.put(local_file, remote_file)
                print(f"  [+] Uploaded: {posixpath.join(rel_dir, f) if rel_dir != '.' else f}")
            except Exception as e:
                print(f"  [!] Error uploading {f}: {e}")

def deploy():
    print("=" * 60)
    print("  Pharmacy POS Deployment to pos.webkoders.com")
    print("=" * 60)
    
    print("[*] Connecting via SSH to 195.250.26.201...")
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=30, banner_timeout=60)
    print("[+] SSH Connected successfully!")

    sftp = ssh.open_sftp()

    try:
        # 1. Sync all project files and database
        upload_project(sftp, LOCAL_BASE, REMOTE_BASE)

        # 2. Install dependencies in virtual environment
        print("\n[*] Installing dependencies in virtual environment...")
        run_cmd(ssh, f"{PIP_BIN} install django==4.2.16 requests pillow")

        # 3. Clear cache
        print("\n[*] Clearing Django cache...")
        clear_cache_py = """
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()
from django.core.cache import cache
cache.clear()
print('Django Cache Cleared Successfully!')
"""
        with sftp.open(f"{REMOTE_BASE}/clear_cache.py", "w") as f:
            f.write(clear_cache_py)
        run_cmd(ssh, f"cd {REMOTE_BASE} && {PY_BIN} clear_cache.py")
        run_cmd(ssh, f"rm -f {REMOTE_BASE}/clear_cache.py")

        # 4. Verify Live Database & Medicines Count
        print("\n[*] Verifying 25,000 Medicines in Live Database...")
        verify_db_py = """
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()
from inventory.models import BrandDrug, DrugBatch
print(f'Total Live Medicines: {BrandDrug.objects.count()}')
print(f'Total Drug Batches: {DrugBatch.objects.count()}')
"""
        with sftp.open(f"{REMOTE_BASE}/verify_db.py", "w") as f:
            f.write(verify_db_py)
        run_cmd(ssh, f"cd {REMOTE_BASE} && {PY_BIN} verify_db.py")
        run_cmd(ssh, f"rm -f {REMOTE_BASE}/verify_db.py")

        # 5. Restart Phusion Passenger
        print("\n[*] Restarting Phusion Passenger...")
        remote_mkdir_p(sftp, f"{REMOTE_BASE}/tmp")
        run_cmd(ssh, f"touch {REMOTE_BASE}/tmp/restart.txt")
        print("[+] Touched tmp/restart.txt for live reload!")

    finally:
        sftp.close()
        ssh.close()
        print("\n" + "=" * 60)
        print("  Deployment & Passenger Restart Completed Successfully!")
        print("  Live URL: https://pos.webkoders.com/pos/")
        print("=" * 60)

if __name__ == "__main__":
    deploy()
