import sys
import paramiko
import urllib.request

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HOST = '195.250.26.201'
PORT = 22
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'
REMOTE_BASE = '/home/webkoders/pos.webkoders.com'
REMOTE_PYTHON = '/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python'

def get_ssh_client():
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=25, banner_timeout=25)
    return ssh

def run_remote_command(ssh, cmd, title):
    print(f"\n[*] {title}...")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        print(out)
    if err and "warning" in err.lower():
        print(f"[Warning]: {err}")
    elif err:
        print(f"[Notice]: {err}")

def run_migrate(ssh):
    cmd = f"{REMOTE_PYTHON} {REMOTE_BASE}/manage.py migrate --noinput"
    run_remote_command(ssh, cmd, "লাইভ ডেটাবেজ মাইগ্রেশন চালানো হচ্ছে (manage.py migrate)")

def run_static(ssh):
    cmd = f"{REMOTE_PYTHON} {REMOTE_BASE}/manage.py collectstatic --noinput"
    run_remote_command(ssh, cmd, "লাইভ CSS ও স্ট্যাটিক ফাইল আপডেট করা হচ্ছে (collectstatic)")

def run_restart(ssh):
    print("\n[*] লাইভ সার্ভার রিস্টার্ট করা হচ্ছে...")
    cmd = f"touch {REMOTE_BASE}/tmp/restart.txt"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    stdout.read()
    
    # Test HTTP Status
    try:
        req = urllib.request.Request("https://pos.webkoders.com/pos/", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
        print(f"[OK] লাইভ সার্ভার সফলভাবে রিস্টার্ট হয়েছে! (HTTP Status: {status} OK)")
        print(">> সাইট লিংক: https://pos.webkoders.com/pos/")
    except Exception as e:
        print(f"[Notice] সার্ভার রিস্টার্ট সিগন্যাল পাঠানো হয়েছে ({e})")

def show_help():
    print("""
=====================================================
    PharmaFlow Live Server Controller (VS Code)
=====================================================
ব্যবহারের নিয়ম (যেকোনো একটি কমান্ড টার্মিনালে লিখুন):

1. লাইভ মাইগ্রেশন চালাতে:
   python live.py migrate
   (অথবা সংক্ষেপে: .\\migrate)

2. লাইভ CSS / স্ট্যাটিক ফাইল আপডেট করতে:
   python live.py static
   (অথবা সংক্ষেপে: .\\static)

3. লাইভ সার্ভার রিস্টার্ট করতে:
   python live.py restart
   (অথবা সংক্ষেপে: .\\restart)

4. একবারে সব (Migration + CSS + Restart) একসাথে চালাতে:
   python live.py all
   (অথবা সংক্ষেপে: .\\all)
=====================================================
""")

def main():
    arg = sys.argv[1].lower().strip() if len(sys.argv) > 1 else ""

    if not arg or arg in ["help", "-h", "--help"]:
        show_help()
        return

    print(">> লাইভ সার্ভারের সাথে সংযোগ স্থাপন করা হচ্ছে...")
    try:
        ssh = get_ssh_client()
        print("[OK] সার্ভার সংযুক্ত!")
    except Exception as e:
        print(f"[ERROR] সার্ভার কানেক্ট হতে পারেনি: {e}")
        sys.exit(1)

    try:
        if arg in ["migrate", "m", "migration"]:
            run_migrate(ssh)
        elif arg in ["static", "css", "s"]:
            run_static(ssh)
        elif arg in ["restart", "r"]:
            run_restart(ssh)
        elif arg in ["all", "deploy", "a"]:
            run_migrate(ssh)
            run_static(ssh)
            run_restart(ssh)
        else:
            print(f"[!] অজানা কমান্ড: {arg}")
            show_help()
    finally:
        ssh.close()
        print("\n[✓] কাজ সম্পন্ন হয়েছে!")

if __name__ == '__main__':
    main()
