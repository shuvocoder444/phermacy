import paramiko
HOST = '195.250.26.201'
PORT = 22
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)

cmds = [
    'uapi Postgresql create_database name=webkoders_pos',
    'uapi Postgresql create_user user=webkoders_posstf password="5&EnaK4~Wm,~TYMb"',
    'uapi Postgresql grant_all_privileges user=webkoders_posstf database=webkoders_pos',
    'uapi Postgresql set_password user=webkoders_posstf password="5&EnaK4~Wm,~TYMb"',
]
for c in cmds:
    print("Running:", c)
    stdin, stdout, stderr = ssh.exec_command(c)
    print("OUT:", stdout.read().decode('utf-8', errors='replace'))
    print("ERR:", stderr.read().decode('utf-8', errors='replace'))
ssh.close()
