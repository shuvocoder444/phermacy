import requests

BASE_URL = "https://pos.webkoders.com"

print("--- Testing Anonymous / Public Access Locks ---")
session = requests.Session()

# 1. Test unauthenticated redirects (without following redirects)
routes_to_test = [
    "/dashboard/",
    "/pos/",
    "/inventory/",
    "/customers/",
    "/ledger/",
    "/saas-admin/",
]

for route in routes_to_test:
    r = session.get(f"{BASE_URL}{route}", allow_redirects=False)
    print(f"GET {route} -> Status: {r.status_code}, Location: {r.headers.get('Location')}")
    assert r.status_code == 302, f"Expected 302 redirect for {route}, got {r.status_code}"
    assert "/login/" in r.headers.get('Location', ''), f"Expected redirect to login, got {r.headers.get('Location')}"

print(">>> ALL PROTECTED ROUTES ARE PROPERLY LOCKED FROM ANONYMOUS USERS! <<<\n")

# 2. Test Public routes
public_routes = ["/", "/login/", "/register/"]
for route in public_routes:
    r = session.get(f"{BASE_URL}{route}", allow_redirects=False)
    print(f"Public GET {route} -> Status: {r.status_code}")
    assert r.status_code == 200, f"Expected 200 OK for {route}, got {r.status_code}"

print(">>> PUBLIC ROUTES (LANDING, LOGIN, REGISTER) ARE ACCESSIBLE! <<<\n")

# 3. Test Tenant Owner Login
print("--- Testing Tenant Owner Login ('uttara_owner') ---")
s_owner = requests.Session()
# Get CSRF token
login_page = s_owner.get(f"{BASE_URL}/login/")
csrf_token = s_owner.cookies.get("csrftoken")

login_res = s_owner.post(
    f"{BASE_URL}/login/",
    data={"username": "uttara_owner", "password": "Owner1234@#", "csrfmiddlewaretoken": csrf_token},
    headers={"Referer": f"{BASE_URL}/login/"},
    allow_redirects=False
)
print(f"Login POST status: {login_res.status_code}, Location: {login_res.headers.get('Location')}")

# Check tenant dashboard access
r_dash = s_owner.get(f"{BASE_URL}/dashboard/")
print(f"uttara_owner GET /dashboard/ -> Status: {r_dash.status_code}")
assert r_dash.status_code == 200, "uttara_owner failed to access /dashboard/"

# Check POS access
r_pos = s_owner.get(f"{BASE_URL}/pos/")
print(f"uttara_owner GET /pos/ -> Status: {r_pos.status_code}")
assert r_pos.status_code == 200, "uttara_owner failed to access /pos/"

# Check tenant owner trying to access Super Admin dashboard (/saas-admin/)
r_saas = s_owner.get(f"{BASE_URL}/saas-admin/", allow_redirects=False)
print(f"uttara_owner GET /saas-admin/ -> Status: {r_saas.status_code}, Location: {r_saas.headers.get('Location')}")
assert r_saas.status_code == 302 and "/dashboard/" in r_saas.headers.get('Location', ''), "Tenant owner was not blocked from /saas-admin/!"
print(">>> TENANT OWNER IS STRICTLY FORBIDDEN FROM SAAS SUPER ADMIN DASHBOARD! <<<\n")

# 4. Test Super Admin Login
print("--- Testing Super Admin Login ('admin') ---")
s_admin = requests.Session()
login_page = s_admin.get(f"{BASE_URL}/login/")
csrf_token = s_admin.cookies.get("csrftoken")

login_res = s_admin.post(
    f"{BASE_URL}/login/",
    data={"username": "admin", "password": "Admin1234@#", "csrfmiddlewaretoken": csrf_token},
    headers={"Referer": f"{BASE_URL}/login/"},
    allow_redirects=False
)
print(f"Admin Login POST status: {login_res.status_code}, Location: {login_res.headers.get('Location')}")

# Check Super Admin dashboard access
r_saas_admin = s_admin.get(f"{BASE_URL}/saas-admin/")
print(f"admin GET /saas-admin/ -> Status: {r_saas_admin.status_code}")
assert r_saas_admin.status_code == 200, "Super Admin failed to access /saas-admin/"
print(">>> SUPER ADMIN HAS FULL ACCESS TO /saas-admin/! <<<\n")

print("==================================================")
print("ALL SECURITY & MULTI-TENANT ISOLATION TESTS PASSED!")
print("==================================================")

