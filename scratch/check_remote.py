import paramiko

host = "195.250.26.201"
user = "webkoders"
key_path = "C:/Users/shuvo/.ssh/id_rsa"
passphrase = "SHUVOshuvo123@"

key = paramiko.RSAKey.from_private_key_file(key_path, password=passphrase)
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, username=user, pkey=key, timeout=15)

stdin, stdout, stderr = client.exec_command("find /home/webkoders -name '.git' -maxdepth 3 2>/dev/null")
print("Git repos:", stdout.read().decode())

stdin, stdout, stderr = client.exec_command("ls -la /home/webkoders/pos.webkoders.com")
print("Directory listing:\n", stdout.read().decode())

client.close()

