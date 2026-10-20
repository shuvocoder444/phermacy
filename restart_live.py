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
REMOTE_PATH = '/home/webkoders/pos.webkoders.com/tmp/restart.txt'

def restart_server():
    print("[*] লাইভ সার্ভার রিস্টার্ট করা হচ্ছে...")
    try:
        key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=20)
        
        # Touch restart.txt to trigger Passenger reload
        cmd = f"touch {REMOTE_PATH}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        ssh.close()

        # Check live site
        req = urllib.request.Request("https://pos.webkoders.com/pos/", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status

        print(f"[OK] লাইভ সার্ভার সফলভাবে রিস্টার্ট হয়েছে! (HTTP Status: {status} OK)")
        print(">> সাইট লিংক: https://pos.webkoders.com/pos/")
    except Exception as e:
        print(f"[ERROR] রিস্টার্ট করতে সমস্যা হয়েছে: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    restart_server()

