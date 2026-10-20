import os
import sys
import posixpath
import paramiko

HOST = "195.250.26.201"
PORT = 22
USERNAME = "webkoders"
KEY_PATH = r"C:\Users\shuvo\.ssh\id_rsa"
PASSPHRASE = "SHUVOshuvo123@"
REMOTE_BASE = "/home/webkoders/pos.webkoders.com"
LOCAL_BASE = r"D:\phermacy"

IGNORE_DIRS = {
    ".git", ".vscode", "venv", "__pycache__", ".venv", ".idea", ".DS_Store", "scratch", "media"
}

IGNORE_FILES = {
    "pharmacy_deploy.zip", ".DS_Store", "deploy_live.py", "deploy_to_cpanel.py", "db.sqlite3", ".env", "live.py", "stderr.log"
}

def run_cmd(ssh, cmd):
    print(f"[*] Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='ignore')
    err = stderr.read().decode('utf-8', errors='ignore')
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
                print(f"  [+] Created remote dir: {d}")
            except Exception:
                pass

def upload_project(sftp, local_dir, remote_dir):
    print(f"[*] Uploading files from {local_dir} to {remote_dir}...")
    remote_mkdir_p(sftp, remote_dir)

    for root, dirs, files in os.walk(local_dir):
        # Filter directories to skip
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
                print(f"  -> Uploading: {posixpath.join(rel_dir, f) if rel_dir != '.' else f}")
                sftp.put(local_file, remote_file)
            except Exception as e:
                print(f"  [!] Error uploading {f}: {e}")

def deploy():
    print("==================================================")
    print("   Deploying Pharmacy POS to pos.webkoders.com    ")
    print("==================================================")
    
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=30, banner_timeout=60)
    print("[+] Connected to SSH Server successfully!")

    sftp = ssh.open_sftp()

    try:
        # 1. Upload All Project Code & Database
        upload_project(sftp, LOCAL_BASE, REMOTE_BASE)

        # 2. Virtual Environment Pip Install
        py_bin = "/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python"
        pip_bin = "/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/pip"
        
        print("[*] Running migrations & collectstatic...")
        run_cmd(ssh, f"cd {REMOTE_BASE} && {py_bin} manage.py migrate --noinput")
        run_cmd(ssh, f"cd {REMOTE_BASE} && {py_bin} manage.py createcachetable")
        run_cmd(ssh, f"cd {REMOTE_BASE} && {py_bin} manage.py collectstatic --noinput")

        # 3. Ensure tmp directory & passenger restart
        tmp_dir = posixpath.join(REMOTE_BASE, "tmp")
        remote_mkdir_p(sftp, tmp_dir)
        run_cmd(ssh, f"touch {REMOTE_BASE}/tmp/restart.txt")
        print("[+] Touched tmp/restart.txt for WSGI live reload.")

        # 4. Check status & test running django check
        print("[*] Running Django system check on server...")
        code, out, err = run_cmd(ssh, f"cd {REMOTE_BASE} && {py_bin} manage.py check")
        print(f"Django check exit code: {code}")

        # 5. Check medicines count in db
        check_db_code = """
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()
from inventory.models import BrandDrug, DrugBatch
print(f'Total Brand Medicines in Live DB: {BrandDrug.objects.count()}')
print(f'Total Drug Batches in Live DB: {DrugBatch.objects.count()}')
"""
        with sftp.open(f"{REMOTE_BASE}/test_db_count.py", "w") as f:
            f.write(check_db_code)
        run_cmd(ssh, f"cd {REMOTE_BASE} && {py_bin} test_db_count.py")
        run_cmd(ssh, f"rm -f {REMOTE_BASE}/test_db_count.py")

    finally:
        sftp.close()
        ssh.close()
        print("\n[✔] Deployment complete!")

if __name__ == "__main__":
    deploy()

