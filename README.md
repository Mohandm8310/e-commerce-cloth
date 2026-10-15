# StyleSphere — Fashion E-Commerce Platform

> A full-stack clothing e-commerce web application with passwordless OTP customer authentication, server-verified Razorpay payments, product variant management with reversible 30-second soft-delete undo, and a real-time administrative analytics dashboard with live customer login monitoring.

---

## 1. Project Overview

**StyleSphere** is an e-commerce platform built for high-end contemporary fashion. It provides a customer storefront and an administrator management portal backed by a normalized MySQL 8+ database schema (with automatic zero-config SQLite development fallback).

### Key Highlights
- **Genuine Passwordless OTP Authentication:** Secure email and SMS OTP challenge generation using salted SHA-256 hashes, rate-limited attempts, and a 60-second resend cooldown.
- **Dedicated Admin Portal (`/admin/login`):** Role-based access control (`@admin_required`), secure password hashing, and audit trails for all catalog and inventory operations.
- **Product Variant Management & Reversible Deletion:** Matrix-based SKU/Size/Color variants, real-time stock indicators, soft-deletion, and an interactive **30-second Undo snackbar** with automatic state restoration.
- **Server-Verified Razorpay Checkout:** Server-side order creation, HMAC-SHA256 signature verification, idempotency-protected webhooks, and an interactive sandbox simulation modal for development testing.
- **Real-Time Admin Dashboard:** Live customer monitoring tracking 5 distinct metrics (Registered Accounts, Login Events, Currently Logged-in, Recent Active within 5 minutes, and Active Device Sessions), live KPI cards, and interactive Chart.js analytics powered by Flask-SocketIO.

---

## 2. Technology Stack

- **Frontend:** HTML5, CSS3, JavaScript ES6+, Bootstrap 5, Bootstrap Icons, Chart.js, Socket.IO Client.
- **Backend:** Python 3.9+, Flask 3.0, Flask-Login, Flask-WTF (CSRF Protection), Flask-SocketIO, SQLAlchemy 2.0 ORM, Werkzeug.
- **Database:** MySQL 8+ (InnoDB, UTF8mb4) & SQLite (local zero-config fallback).
- **Payment Gateway:** Razorpay Python SDK with HMAC-SHA256 signature verification and webhook idempotency.
- **Authentication:** Salted SHA-256 OTP tokens with timestamp expiration and attempt tracking.
- **Testing:** Pytest automated test suite covering authentication, RBAC, inventory limits, checkout, and analytics.

---

## 3. Architecture & Workflows

### System Architecture Diagram

```mermaid
flowchart TD
    subgraph ClientLayer["Frontend Layer"]
        C_Browser["Customer Browser / Mobile Drawer"]
        A_Browser["Admin Browser Dashboard"]
    end

    subgraph SecurityLayer["Security & Session Layer"]
        CSRF["Flask-WTF CSRF Protection"]
        RBAC["RBAC / @admin_required Decorator"]
        LoginMgr["Flask-Login Session Manager"]
    end

    subgraph AppLayer["Flask Application (Blueprints)"]
        AuthBP["Auth Blueprint (/auth)"]
        ProdBP["Products Blueprint (/shop, /products)"]
        CartBP["Cart Blueprint (/cart)"]
        CheckBP["Checkout Blueprint (/checkout)"]
        CustBP["Customer Blueprint (/customer)"]
        AdminBP["Admin Blueprint (/admin)"]
        SocketBP["Flask-SocketIO Real-time Gateway"]
    end

    subgraph PaymentLayer["Payment Gateway"]
        RZP["Razorpay API / Webhooks"]
    end

    subgraph DBLayer["Database (SQLAlchemy ORM / MySQL 8+)"]
        DB[("MySQL 8+ / SQLite Database\n22 Normalized Tables")]
    end

    C_Browser --> CSRF --> AuthBP & ProdBP & CartBP & CheckBP & CustBP
    A_Browser --> CSRF --> RBAC --> AdminBP & SocketBP
    AuthBP & ProdBP & CartBP & CheckBP & CustBP & AdminBP --> DBLayer
    CheckBP <--> RZP
    AuthBP -.->|Broadcast Login Event| SocketBP
    CheckBP -.->|Broadcast Order Event| SocketBP
    SocketBP -.->|Push Live Updates| A_Browser
```

### Customer OTP Authentication Flow

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer
    participant Browser as Web Browser
    participant Server as Flask Auth Service
    participant DB as Database (otp_challenges)
    participant Gateway as Transactional Mail/SMS

    Customer->>Browser: Enters email or mobile number
    Browser->>Server: POST /auth/request-otp
    Server->>Server: Validate identifier & enforce 60s cooldown
    Server->>Server: Generate 6-digit random code + salt
    Server->>DB: Store salted SHA-256 hash & expiration timestamp
    Server->>Gateway: Dispatch OTP via SMTP / SMS
    Server-->>Browser: Redirect to /auth/verify-otp
    Customer->>Browser: Enters 6-digit OTP
    Browser->>Server: POST /auth/verify-otp
    Server->>DB: Verify hash, expiration, and attempt counter
    Server->>DB: Mark challenge as is_used = True
    Server->>DB: Create/Retrieve User & Start UserSession
    Server->>Server: Establish Flask-Login session
    Server-->>Browser: Redirect to shopping catalog / checkout
```

---

## 4. Database Schema (22 Normalized Tables)

The application models 22 normalized entities in `app/models/` and provides a production DDL script in `scripts/schema.sql`:

1. `roles`: User roles (`customer`, `admin`, `superadmin`).
2. `users`: Customer and admin accounts with authentication credentials and status flags.
3. `customer_profiles`: Personal details (name, avatar, gender).
4. `otp_challenges`: One-time password tokens (salted hash, attempts, expiration, usage state).
5. `user_sessions`: Active device sessions for multi-device login tracking.
6. `login_events`: Immutable audit trail of all customer login events.
7. `categories`: Apparel categories with hierarchy support.
8. `products`: Apparel styles with pricing, discounts, SKU, and soft-delete timestamps.
9. `product_images`: Primary and secondary product photos.
10. `product_variants`: Size and color combinations with individual inventory levels.
11. `inventory_movements`: Immutable log of stock additions, orders, returns, and adjustments.
12. `carts`: Shopping carts for authenticated customers and guest sessions.
13. `cart_items`: Variant selections, quantities, and price snapshots.
14. `wishlists`: Customer saved item collections.
15. `wishlist_items`: Products saved to wishlist.
16. `addresses`: Shipping and billing addresses with default address flag.
17. `coupons`: Discount promo codes with usage limits and minimum order thresholds.
18. `orders`: Orders with financial breakdowns, status, and shipping snapshot.
19. `order_items`: Immutable snapshots of purchased garments at time of checkout.
20. `payment_transactions`: Payment attempts, transaction IDs, amounts, and statuses.
21. `payment_webhook_events`: Idempotent log of incoming payment gateway webhooks.
22. `admin_audit_logs`: Detailed audit trail of all administrator actions.

---

## 5. Live Customer Login Monitoring & Analytics

The admin dashboard provides live monitoring that distinguishes 5 customer activity dimensions:

| Metric | Name | Definition |
|---|---|---|
| **A** | **Total Registered Customers** | Total unique customer accounts registered in the database. |
| **B** | **Total Successful Logins** | Cumulative successful login events recorded in `login_events`. |
| **C** | **Currently Logged-In Customers** | Distinct customers with at least one active, unexpired session in `user_sessions`. |
| **D** | **Recent Active Customers** | Distinct customers who sent an activity heartbeat within the last 5 minutes. |
| **E** | **Currently Active Sessions** | Total number of valid device sessions across all logged-in customers. |

The frontend dashboard receives live pushes via **WebSocket (`Socket.IO`)** on customer logins and new order events, with an automatic background polling fallback every 10 seconds.

---

## 6. Directory Structure

```text
stylesphere/
├── app/
│   ├── __init__.py           # Application factory, filters, CLI commands
│   ├── extensions.py         # SQLAlchemy, LoginManager, CSRF, SocketIO
│   ├── models/               # 22 Normalized SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py           # User, Role, CustomerProfile, OTPChallenge, UserSession, LoginEvent, Address
│   │   ├── product.py        # Category, Product, ProductImage, ProductVariant, InventoryMovement
│   │   ├── cart.py           # Cart, CartItem, Wishlist, WishlistItem, Coupon
│   │   ├── order.py          # Order, OrderItem
│   │   ├── payment.py        # PaymentTransaction, PaymentWebhookEvent
│   │   └── analytics.py      # AdminAuditLog
│   ├── auth/                 # Customer OTP routes and services
│   ├── admin/                # Admin portal, RBAC, KPI calculator, CRUD with Undo
│   ├── products/             # Catalog browsing, filtering, search, product detail
│   ├── cart/                 # Shopping bag and coupon application
│   ├── checkout/             # Razorpay payment verification and webhooks
│   ├── customer/             # Customer profile, addresses, orders, order tracking, wishlist
│   ├── realtime/             # SocketIO event handlers and broadcasters
│   ├── static/
│   │   ├── css/              # style.css, admin.css
│   │   └── js/               # main.js, cart.js, admin_dashboard.js, admin_products.js
│   └── templates/
│       ├── base.html         # Storefront base layout
│       ├── index.html        # Home page
│       ├── auth/             # login.html, verify_otp.html
│       ├── products/         # catalog.html, detail.html
│       ├── cart/             # cart.html
│       ├── checkout/         # checkout.html, order_confirmation.html
│       ├── customer/         # profile.html, orders.html, track_order.html, wishlist.html
│       ├── admin/            # login.html, base_admin.html, dashboard.html, products.html, product_form.html, orders.html, order_detail.html, customers.html, audit_logs.html
│       └── pages/            # contact.html, about.html, privacy.html, terms.html, returns.html, 404.html, 403.html, 500.html
├── scripts/
│   ├── schema.sql            # MySQL 8+ Production DDL
│   └── seed_data.py          # Database seeder (admin, customer, categories, products, coupons)
├── tests/
│   ├── conftest.py           # Pytest fixtures and test client
│   ├── test_auth.py          # OTP generation, expiration, rate limiting, and session creation
│   ├── test_admin.py         # Admin RBAC, product CRUD, and 30s undo restore
│   ├── test_cart_order.py    # Cart stock constraints, coupons, state machine, and Razorpay signatures
│   ├── test_analytics.py     # Login monitoring metrics A–E and KPI calculation
│   └── test_pages.py         # Complete render test for all 20 required pages
├── uploads/                  # Local product image uploads
├── .env.example              # Environment variables template
├── .env                      # Local configuration
├── requirements.txt          # Python dependencies
├── config.py                 # App configurations (Development, Testing, Production)
├── run.py                    # Application entrypoint
└── README.md                 # Project documentation
```

---

## 7. Quickstart & Local Setup

### Step 1: Clone and Enter Directory
```bash
cd stylesphere
```

### Step 2: Set Up Virtual Environment & Dependencies
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Default `.env` settings allow running out of the box with SQLite and `MOCK_OTP=True` and `MOCK_RAZORPAY=True`. For MySQL 8+, set:
```ini
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/stylesphere_db
```

### Step 4: Seed Initial Data
```bash
python scripts/seed_data.py
```
This initializes categories, clothing styles with high-resolution fashion photography, size/color variant matrix, coupons (`WELCOME10`, `STYLE20`, `FLAT500`), sample orders, and the following accounts:
- **Administrator:** `admin@stylesphere.com` / `Admin@12345`
- **Customer:** `customer@example.com` / `9876543210`

### Step 5: Start Development Server
```bash
python run.py
```
Open your browser at:
- **Storefront:** [http://127.0.0.1:5000](http://127.0.0.1:5000)
- **Admin Portal:** [http://127.0.0.1:5000/admin/login](http://127.0.0.1:5000/admin/login)

---

## 8. Running Automated Tests

Run the full automated test suite using `pytest`:

```bash
pytest -v
```

All 16 test cases verify:
- Genuine OTP generation, validation, expiration, and reuse prevention.
- Rate limiting and cooldown enforcement.
- Admin role restrictions and prevention of privilege escalation.
- Product creation, inventory updates, soft deletion, and 30-second undo restoration.
- Cart operations, price recalculation, and stock ceiling validation.
- Coupon discounts and order total verification.
- Official Razorpay signature validation and duplicate webhook idempotency.
- Valid order fulfillment transitions according to the strict state machine.
- Privacy-conscious login metrics (A, B, C, D, E) and operational KPIs.
- Clean rendering of all 20 required pages.

---

## 9. Production Deployment Guide

### Production WSGI Server
Do not use the Flask development server in production. Deploy using **Gunicorn** with eventlet or gevent workers for WebSocket support:

```bash
pip install gunicorn eventlet
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 run:app
```

### Nginx Reverse Proxy Configuration
```nginx
server {
    listen 80;
    server_name fashion.stylesphere.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name fashion.stylesphere.com;

    ssl_certificate /etc/letsencrypt/live/stylesphere.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/stylesphere.com/privkey.pem;

    location /static/ {
        alias /var/www/stylesphere/app/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location /uploads/ {
        alias /var/www/stylesphere/uploads/;
        expires 30d;
    }

    location /socket.io/ {
        proxy_pass http://127.0.0.1:8000/socket.io/;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 10. Security & Compliance Highlights

- **Role-Based Authorization:** Protected routes use the `@admin_required` server-side decorator; permissions are never determined by client-side button visibility.
- **CSRF Defense:** `Flask-WTF` CSRF tokens protect all state-modifying requests; AJAX requests pass `X-CSRFToken` headers.
- **SQL Injection Prevention:** Parameterized SQLAlchemy ORM queries protect all database operations.
- **XSS Mitigation:** Automatic Jinja2 HTML escaping and strict input sanitation.
- **Secure Cookie Configuration:** `HttpOnly`, `SameSite=Lax`, and `Secure` (in HTTPS production) flags on all session cookies.
- **Payment Signature Verification:** Cryptographic verification using HMAC-SHA256 ensures payment tampering is impossible.
- **Audit Logging:** Every administrative product alteration, soft delete, restoration, and order transition is permanently recorded in `admin_audit_logs`.

---

## 11. License & Credits

Developed for the **StyleSphere Fashion Platform**. All photography assets utilized in demonstration mode are high-resolution fashion editorial imagery courtesy of Unsplash.
