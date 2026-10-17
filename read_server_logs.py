import sys
import paramiko

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

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)

# Check last 50 lines of stderr.log
stdin, stdout, stderr = ssh.exec_command(f"tail -n 50 {REMOTE_BASE}/stderr.log")
print("=== LAST 50 LINES OF STDERR.LOG ===")
print(stdout.read().decode('utf-8', errors='ignore'))

# Check python execution test
py_bin = "/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python"
stdin, stdout, stderr = ssh.exec_command(f"cd {REMOTE_BASE} && {py_bin} manage.py check")
print("=== DJANGO CHECK OUTPUT ===")
print("STDOUT:", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:", stderr.read().decode('utf-8', errors='ignore'))

ssh.close()

