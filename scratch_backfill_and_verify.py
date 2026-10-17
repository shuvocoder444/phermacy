import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

HOST = '195.250.26.201'
PORT = 22
USERNAME = 'webkoders'
KEY_PATH = 'C:/Users/shuvo/.ssh/id_rsa'
PASSPHRASE = 'SHUVOshuvo123@'
REMOTE_BASE = '/home/webkoders/pos.webkoders.com'
PY_BIN = '/home/webkoders/virtualenv/pos.webkoders.com/3.9/bin/python'

key = paramiko.RSAKey.from_private_key_file(KEY_PATH, password=PASSPHRASE)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USERNAME, pkey=key, port=PORT, timeout=15)

py_script = """
import os, sys, django
sys.path.insert(0, '/home/webkoders/pos.webkoders.com')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pharmacy_saas.settings')
django.setup()

from core.models import Tenant, StaffProfile, SubscriptionPlan, TenantSubscription, IncomeExpenseEntry
from pos.models import Invoice, CashRegisterSession
from customers.models import Customer, DueLedger
from inventory.models import DrugBatch
from django.contrib.auth.models import User
from core.saas_services import ensure_default_subscription_plans, ensure_tenant_subscription

t = Tenant.objects.first()
if not t:
    t = Tenant.objects.create(name='Popular Pharmacy & Care', slug='popular', phone='01711000000', is_active=True)

print("Active Tenant:", t.name, t.id)

# Backfill
c_inv = Invoice.objects.filter(tenant__isnull=True).update(tenant=t)
c_cust = Customer.objects.filter(tenant__isnull=True).update(tenant=t)
c_due = DueLedger.objects.filter(tenant__isnull=True).update(tenant=t)
c_inc = IncomeExpenseEntry.objects.filter(tenant__isnull=True).update(tenant=t)
c_bat = DrugBatch.objects.filter(tenant__isnull=True).update(tenant=t)
c_reg = CashRegisterSession.objects.filter(tenant__isnull=True).update(tenant=t)

print(f"Backfill Result -> Invoices: {c_inv}, Customers: {c_cust}, Dues: {c_due}, Ledger: {c_inc}, Batches: {c_bat}, Registers: {c_reg}")

# Ensure subscription
ensure_default_subscription_plans()
sub = ensure_tenant_subscription(t)
print(f"Tenant Subscription -> Plan: {sub.plan.name}, Active: {sub.is_active}, Valid: {sub.is_valid}")

# Check staff profile for existing users
for u in User.objects.all():
    profile = StaffProfile.objects.filter(user=u).first()
    if not profile:
        profile = StaffProfile.objects.create(user=u, tenant=t, role='ADMIN' if u.is_superuser else 'CASHIER', is_active=True)
        print(f"Created StaffProfile for {u.username} bound to {t.name}")
    else:
        if not profile.tenant:
            profile.tenant = t
            profile.save()
            print(f"Linked existing profile {u.username} to {t.name}")

print("Users and roles:")
for u in User.objects.all():
    prof = getattr(u, 'staff_profile', None)
    print(f" - {u.username} (superuser={u.is_superuser}, staff={u.is_staff}) -> Tenant: {prof.tenant.name if prof and prof.tenant else 'None'}")

from django.core.cache import cache
cache.clear()
print("Cache cleared successfully!")
"""

stdin, stdout, stderr = ssh.exec_command(f"{PY_BIN} -")
stdin.write(py_script)
stdin.channel.shutdown_write()

print("STDOUT:\n" + stdout.read().decode('utf-8', errors='replace'))
print("STDERR:\n" + stderr.read().decode('utf-8', errors='replace'))

# Restart passenger
stdin, stdout, stderr = ssh.exec_command(f"touch {REMOTE_BASE}/tmp/restart.txt")
print("Passenger restarted.")

ssh.close()

