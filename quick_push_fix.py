import os
import sys
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
PY_BIN = "/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python"

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)
sftp = ssh.open_sftp()

# 1. Upload updated pharmacy_saas/__init__.py
sftp.put(r"D:\phermacy\pharmacy_saas\__init__.py", f"{REMOTE_BASE}/pharmacy_saas/__init__.py")
print("[+] Uploaded safe pharmacy_saas/__init__.py")

# 2. Run Django manage.py check
stdin, stdout, stderr = ssh.exec_command(f"cd {REMOTE_BASE} && {PY_BIN} manage.py check")
out = stdout.read().decode('utf-8', errors='ignore')
err = stderr.read().decode('utf-8', errors='ignore')
print("DJANGO CHECK STDOUT:", out)
print("DJANGO CHECK STDERR:", err)

# 3. Touch restart.txt
ssh.exec_command(f"touch {REMOTE_BASE}/tmp/restart.txt")
print("[+] Touched tmp/restart.txt")

sftp.close()
ssh.close()

# 4. Test live website
print("\n[*] Testing live website: https://pos.webkoders.com/pos/ ...")
try:
    req = urllib.request.Request(
        "https://pos.webkoders.com/pos/",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        print(f"[✔] Live Website Status: {res.status} {res.reason}")
        print(f"[✔] Response bytes: {len(res.read())}")
except Exception as e:
    print(f"[-] HTTP Test: {e}")

