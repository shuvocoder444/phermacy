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

install_cmds = """
mkdir -p /home/webkoders/.local/bin
mkdir -p /home/webkoders/tessdata

# Download static tesseract binary if not present
if [ ! -f /home/webkoders/.local/bin/tesseract ]; then
    echo "Downloading static tesseract binary..."
    curl -L -s -o /home/webkoders/.local/bin/tesseract https://github.com/DanielMYT/tesseract-static/releases/download/tesseract-5.5.3-rebuild/tesseract.x86_64
    chmod +x /home/webkoders/.local/bin/tesseract
fi

# Download eng and ben traineddata
if [ ! -f /home/webkoders/tessdata/eng.traineddata ]; then
    echo "Downloading eng.traineddata..."
    curl -L -s -o /home/webkoders/tessdata/eng.traineddata https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata
fi

if [ ! -f /home/webkoders/tessdata/ben.traineddata ]; then
    echo "Downloading ben.traineddata..."
    curl -L -s -o /home/webkoders/tessdata/ben.traineddata https://github.com/tesseract-ocr/tessdata_fast/raw/main/ben.traineddata
fi

export TESSDATA_PREFIX=/home/webkoders/tessdata
/home/webkoders/.local/bin/tesseract --version
"""

print("Executing static tesseract installation on server...")
stdin, stdout, stderr = ssh.exec_command(install_cmds)
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

ssh.close()

