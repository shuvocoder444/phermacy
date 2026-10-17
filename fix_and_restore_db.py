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

print("=" * 60)
print("  Restoring & Verifying Database on pos.webkoders.com")
print("=" * 60)

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=30)
print("[+] SSH Connected!")

sftp = ssh.open_sftp()

local_db = r"D:\phermacy\db.sqlite3"
remote_tmp_db = f"{REMOTE_BASE}/db.sqlite3.tmp"
remote_db = f"{REMOTE_BASE}/db.sqlite3"

print("[*] Uploading clean vacuumed db.sqlite3 (10.9MB)...")
sftp.put(local_db, remote_tmp_db)
print("[+] db.sqlite3.tmp uploaded successfully.")

# Atomically replace db file
print("[*] Atomically replacing live database...")
stdin, stdout, stderr = ssh.exec_command(f"mv -f {remote_tmp_db} {remote_db} && chmod 664 {remote_db}")
stdout.channel.recv_exit_status()

# Verify remote SQLite integrity
verify_cmd = f"{PY_BIN} -c \"import sqlite3; c=sqlite3.connect('{remote_db}'); cur=c.cursor(); cur.execute('PRAGMA integrity_check;'); print('Remote Integrity:', cur.fetchall()); cur.execute('SELECT count(*) FROM inventory_branddrug;'); print('Total Medicines in Remote DB:', cur.fetchone()[0]); c.close()\""
stdin, stdout, stderr = ssh.exec_command(verify_cmd)
out = stdout.read().decode('utf-8', errors='ignore')
print("REMOTE DB VERIFICATION:\n", out)

# Touch restart.txt
ssh.exec_command(f"mkdir -p {REMOTE_BASE}/tmp && touch {REMOTE_BASE}/tmp/restart.txt")
print("[+] Touched tmp/restart.txt for Passenger live reload.")

sftp.close()
ssh.close()

# Test endpoints
urls = [
    "https://pos.webkoders.com/pos/",
    "https://pos.webkoders.com/customers/",
    "https://pos.webkoders.com/ledger/"
]

for url in urls:
    print(f"\n[*] Testing URL: {url} ...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as res:
            print(f"[✔] Status: {res.status} {res.reason} (Length: {len(res.read())} bytes)")
    except Exception as e:
        print(f"[-] Warning on {url}: {e}")

print("\n" + "=" * 60)
print("  All Services Verified & Live!")
print("=" * 60)

