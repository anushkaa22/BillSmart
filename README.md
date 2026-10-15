# BillSmart

## About the project

BillSmart is a web-based inventory, billing, sales, and shop management system built for a small retail business. It was designed as a final-year project with a practical focus: the dashboard, stock levels, invoices, notifications, and reports all use data stored in SQLite rather than placeholder values.

## Problem statement

Small shops often manage products, stock counts, and sales across notebooks or disconnected spreadsheets. That makes it difficult to know what is available, which items need reordering, and how the business is performing. BillSmart brings those activities into one straightforward workspace.

## Objectives

- Maintain an unlimited product catalog with stock thresholds.
- Provide a quick point-of-sale checkout flow.
- Keep customer, supplier, and sales records connected.
- Give shop owners useful revenue and profit summaries.
- Protect private business data with authentication and role-based access.

## Features

BillSmart includes registration, login, logout, hashed passwords, admin/staff roles, inventory CRUD, product image upload, search and stock filters, POS checkout, customer selection, invoices, sales history, customer and supplier records, real notifications, low-stock alerts, reports with CSV export, settings, responsive layouts, and a local-storage light/dark theme.

## Technologies used

- Python 3.11+
- Flask, Flask-SQLAlchemy, Flask-Login
- SQLite
- Jinja templates, HTML, CSS, JavaScript
- Chart.js and Bootstrap Icons via CDN

## Project structure

```text
BillSmart/
├── app.py
├── models.py
├── config.py
├── requirements.txt
├── inventory.db                 # created automatically on first run
├── README.md
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   ├── js/dashboard.js
│   ├── js/billing.js
│   └── images/products/
└── templates/
    ├── base.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── inventory.html
    ├── product_form.html
    ├── billing.html
    ├── invoice.html
    ├── sales.html
    ├── customers.html
    ├── customer_form.html
    ├── suppliers.html
    ├── supplier_form.html
    ├── reports.html
    ├── notifications.html
    ├── users.html
    ├── user_form.html
    ├── settings.html
    └── errors/
```

## Database design

The database contains `User`, `Product`, `Customer`, `Supplier`, `Sale`, `SaleItem`, `Notification`, and `Setting` models. A sale belongs to an optional customer and a creator, and contains multiple sale items. Each sale item references a product and stores the price and subtotal at the time of sale. Product cost prices allow reports to calculate profit. Relationships use SQLAlchemy foreign keys and cascades where appropriate.

The database is created with `db.create_all()` on first run and is not deleted when the application restarts. Sample products are inserted only when no users exist, so the initial setup is useful without overwriting existing business data. The database file is ignored by Git for privacy; keep a backup of `inventory.db` when deploying a real store.

## Authentication

Public registration creates a `staff` account only. It validates the email, password length, confirmation, and duplicate username/email values. Passwords are stored only as Werkzeug password hashes. Login accepts either username or email and uses Flask-Login to manage the session. Logout is a POST action that calls `logout_user()`, clears the session, and redirects to login. Private routes use `login_required`.

## Default admin account

- Username: `admin`
- Email: `admin@billsmart.local`
- Password: `Admin@123`

Change this password after the first login. The default admin is created only if the database has no users.

## Admin and staff roles

Admins can manage products, users, settings, and reports in addition to the daily sales workflow. Staff can view inventory, operate billing, view sales, and manage customer and supplier records. The restrictions are enforced on the server with an `admin_required` decorator, not only by hiding links in templates.

## How to install

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in a browser. Set a production `SECRET_KEY` environment variable before deployment.

## Desktop app (Windows installer)

BillSmart ships as an installable Windows desktop app — a native window powered by the same Flask code, fully usable offline (charts, icons, and fonts are bundled in `static/vendor/`).

```powershell
# 1. Build the app bundle (output: dist\BillSmart\BillSmart.exe, ~63 MB)
powershell -ExecutionPolicy Bypass -File .\build.ps1

# 2. Build the installer too (needs Inno Setup 6, output: installer-output\BillSmart-Setup-1.0.0.exe)
powershell -ExecutionPolicy Bypass -File .\build.ps1 -Installer
```

Install `BillSmart-Setup-1.0.0.exe` on any Windows 10/11 laptop (Microsoft Edge WebView2 is preinstalled; the installer warns with a download link if it is missing). Shop data lives in `%APPDATA%\BillSmart\` (`inventory.db`, `product_images/`, `secret.key`), so reinstalls and updates keep all records.

- **Uninstall:** Control Panel → Programs → Programs and Features → BillSmart → Uninstall (shop data is preserved; delete `%APPDATA%\BillSmart` manually for a full wipe).
- **Backup:** Settings → Backup data downloads a zip of the database + product images.
- **Portable/dev overrides:** `BILLSMART_DATA_DIR` forces a data folder; `python desktop.py` runs the desktop shell from source.

## How the system works

An administrator adds products and sets a low-stock threshold. Staff or admins select in-stock products in Billing / POS, adjust quantities, optionally select a customer, and apply a discount, tax rate, and payment method. Completing checkout creates an invoice and sale items in one database transaction, reduces product quantities, and generates notifications for the sale and any stock alert. Dashboard and report values then update from those records.

## Future scope

Possible extensions include barcode scanning, GST-compliant invoices, WhatsApp invoice sharing, cloud database hosting, multi-store support, richer date-range analytics, supplier purchase orders, and automated backups.

## Conclusion

BillSmart provides a clean foundation for a small retail shop management system. The architecture is intentionally understandable: Flask routes handle workflows, SQLAlchemy models represent the business data, Jinja templates render the application shell, and small JavaScript files add responsive interactions without introducing a separate frontend framework.
