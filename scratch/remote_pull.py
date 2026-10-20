import paramiko

host = "195.250.26.201"
user = "webkoders"
key_path = "C:/Users/shuvo/.ssh/id_rsa"
passphrase = "SHUVOshuvo123@"

key = paramiko.RSAKey.from_private_key_file(key_path, password=passphrase)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, pkey=key, timeout=15)

commands = [
    "cd /home/webkoders/pos.webkoders.com && git pull origin main",
    "touch /home/webkoders/pos.webkoders.com/tmp/restart.txt",
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    if out:
        print("OUT:", out)
    if err:
        print("ERR:", err)

client.close()
print("Deployment completed successfully!")

