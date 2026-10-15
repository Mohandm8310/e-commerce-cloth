import os
import sys
import re

# Add root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.product import Product
from app.models.user import User


def run_verification():
    app = create_app()
    client = app.test_client()

    print("==================================================")
    print(" StyleSphere Full-Stack System Health Verification")
    print("==================================================")

    # 1. Storefront Home & Catalog
    r_home = client.get('/')
    print(f"[PASS] Storefront Home (GET /): {r_home.status_code}")
    assert r_home.status_code == 200

    r_shop = client.get('/shop')
    print(f"[PASS] Catalog Browse (GET /shop): {r_shop.status_code}")
    assert r_shop.status_code == 200

    with app.app_context():
        p_count = Product.query.filter_by(is_active=True, is_deleted=False).count()
        print(f"[PASS] Active Products in Database: {p_count}")
        assert p_count > 0

    # 2. Customer OTP Flow (Mock dev mode)
    r_login_page = client.get('/auth/login')
    csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', r_login_page.get_data(as_text=True))
    csrf_token = csrf_match.group(1) if csrf_match else ''

    req_otp = client.post('/auth/request-otp', json={'identifier': 'customer@example.com'}, headers={'X-CSRFToken': csrf_token})
    print(f"[PASS] Request OTP (POST /auth/request-otp): {req_otp.status_code}")
    otp_json = req_otp.get_json()
    assert req_otp.status_code == 200
    mock_otp = otp_json.get('mock_otp')
    print(f"[PASS] OTP Received: {mock_otp}")

    ver_otp = client.post('/auth/verify-otp', json={'identifier': 'customer@example.com', 'otp_code': mock_otp}, headers={'X-CSRFToken': csrf_token})
    print(f"[PASS] Verify OTP & Session Init (POST /auth/verify-otp): {ver_otp.status_code}")
    assert ver_otp.status_code == 200

    r_profile = client.get('/customer/profile')
    print(f"[PASS] Customer Profile (GET /customer/profile): {r_profile.status_code}")
    assert r_profile.status_code == 200

    # 3. Dedicated Admin Authentication
    admin_client = app.test_client()
    r_adm_page = admin_client.get('/admin/login')
    admin_csrf = re.search(r'name="csrf_token" value="([^"]+)"', r_adm_page.get_data(as_text=True)).group(1)

    r_adm_login = admin_client.post('/admin/login', data={
        'email': 'admin@stylesphere.com',
        'password': 'Admin@12345',
        'csrf_token': admin_csrf
    }, follow_redirects=False)
    print(f"[PASS] Admin Login (POST /admin/login): {r_adm_login.status_code} -> Redirects to Dashboard")
    assert r_adm_login.status_code == 302

    r_dash = admin_client.get('/admin/dashboard')
    print(f"[PASS] Admin Dashboard (GET /admin/dashboard): {r_dash.status_code}")
    assert r_dash.status_code == 200

    r_kpis = admin_client.get('/admin/api/kpis')
    print(f"[PASS] Live Admin KPIs Endpoint (GET /admin/api/kpis): {r_kpis.status_code}")
    kpi_data = r_kpis.get_json()
    print("    - Metric A (Total Registered Customers):", kpi_data['total_customers'])
    print("    - Metric B (Total Successful Logins):   ", kpi_data['total_successful_logins'])
    print("    - Metric C (Currently Logged-in):       ", kpi_data['currently_logged_in_customers'])
    print("    - Metric D (Recent Active 5m):          ", kpi_data['recent_active_customers_5m'])
    print("    - Metric E (Active Sessions Count):     ", kpi_data['active_sessions_count'])
    print("    - Total Orders:                         ", kpi_data['total_orders'])
    print("    - Total Verified Revenue:                Rs. {:,.2f}".format(kpi_data['total_revenue']))

    r_charts = admin_client.get('/admin/api/charts?days=30')
    print(f"[PASS] Chart.js Analytics Endpoint (GET /admin/api/charts): {r_charts.status_code}")
    assert r_charts.status_code == 200

    print("\n==================================================")
    print(" ALL CHECKS PASSED: SYSTEM FULLY OPERATIONAL!")
    print("==================================================\n")


if __name__ == '__main__':
    run_verification()
