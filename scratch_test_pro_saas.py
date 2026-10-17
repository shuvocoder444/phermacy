import urllib.request
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    ("Homepage Landing", "https://pos.webkoders.com/"),
    ("Pharmacy Registration (Sign Up)", "https://pos.webkoders.com/register/"),
    ("Pharmacy Login", "https://pos.webkoders.com/login/"),
    ("SaaS Super Admin Dashboard", "https://pos.webkoders.com/saas-admin/"),
    ("Tenant Pharmacy Dashboard", "https://pos.webkoders.com/dashboard/"),
    ("Pharmacy Inventory & Stock", "https://pos.webkoders.com/inventory/"),
    ("POS Terminal", "https://pos.webkoders.com/pos/"),
    ("Recent Invoices API", "https://pos.webkoders.com/pos/recent-invoices/"),
    ("Held Carts API", "https://pos.webkoders.com/pos/cart/held-list/"),
    ("Customer Due Ledger (Baki Khata)", "https://pos.webkoders.com/customers/"),
    ("Income & Expense Ledger (Cash Book)", "https://pos.webkoders.com/ledger/"),
]

for label, url in urls:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=15) as res:
            content = res.read().decode('utf-8', errors='replace')
            print(f"[OK 200] {label} ({url}) - Bytes: {len(content)}")
    except urllib.error.HTTPError as e:
        print(f"[ERR {e.code}] {label} ({url}) - Error: {e.reason}")
    except Exception as e:
        print(f"[FAIL] {label} ({url}) - Error: {e}")

