#!/bin/bash
# Remote Server Deployment & Startup Script for pos.webkoders.com
# Run this on the server: bash deploy_remote.sh

set -e

echo "=== 🚀 Deploying PharmaFlow BD on pos.webkoders.com ==="

# 1. Enter project directory
cd /home/webkoders/pos.webkoders.com

# 2. Setup Virtualenv if not present
if [ ! -d "venv" ]; then
    echo "Creating Python Virtual Environment..."
    python3 -m venv venv
fi

# 3. Activate venv & install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Apply Database Migrations
python manage.py migrate

# 5. Collect Static Files
python manage.py collectstatic --noinput

# 6. Restart Gunicorn / Service if running
if command -v systemctl &> /dev/null; then
    echo "Restarting service..."
    sudo systemctl restart gunicorn_pos || true
fi

echo "=== ✅ Deployment Completed Successfully on https://pos.webkoders.com ==="

