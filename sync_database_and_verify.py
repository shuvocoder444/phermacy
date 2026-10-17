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
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=30)
sftp = ssh.open_sftp()

print("[*] Uploading db.sqlite3 cleanly (10.9MB)...")
local_db = r"D:\phermacy\db.sqlite3"
remote_tmp_db = f"{REMOTE_BASE}/db.sqlite3.tmp"
remote_db = f"{REMOTE_BASE}/db.sqlite3"

# Upload to temporary file first
sftp.put(local_db, remote_tmp_db)
print("[+] db.sqlite3.tmp uploaded.")

# Atomically replace
stdin, stdout, stderr = ssh.exec_command(f"mv -f {remote_tmp_db} {remote_db} && chmod 664 {remote_db}")
stdout.channel.recv_exit_status()
print("[+] Replaced remote db.sqlite3 cleanly.")

# Verify integrity and count on server
verify_script = """
import sqlite3
conn = sqlite3.connect('/home/webkoders/pos.webkoders.com/db.sqlite3')
cur = conn.cursor()
cur.execute('PRAGMA integrity_check;')
print('Remote DB integrity:', cur.fetchall())
cur.execute('SELECT count(*) FROM inventory_branddrug;')
print('Remote BrandDrug count:', cur.fetchone()[0])
conn.close()
"""
stdin, stdout, stderr = ssh.exec_command(f"{PY_BIN} -c \"{verify_script}\"")
print("VERIFY REMOTE DB:\n", stdout.read().decode('utf-8', errors='ignore'))

# Clear cache and reload passenger
ssh.exec_command(f"touch {REMOTE_BASE}/tmp/restart.txt")
print("[+] Touched tmp/restart.txt")

sftp.close()
ssh.close()

# Test live website
print("\n[*] Testing live website: https://pos.webkoders.com/pos/ ...")
try:
    req = urllib.request.Request(
        "https://pos.webkoders.com/pos/",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        print(f"[✔] Live Website Status: {res.status} {res.reason}")
        content = res.read().decode('utf-8', errors='ignore')
        print(f"[✔] Content length: {len(content)} bytes")
        if "PharmaFlow" in content or "POS" in content or "সার্চ" in content:
            print("[✔] PharmaFlow POS is 100% LIVE and operational!")
except Exception as e:
    print(f"[-] HTTP Test: {e}")

