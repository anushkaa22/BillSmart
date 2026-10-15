import csv
import io
import os
import re
import secrets
import socket
import sys
import zipfile
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, send_file, session
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from sqlalchemy import func, or_, desc
from werkzeug.utils import secure_filename

from models import db, User, Product, Customer, Supplier, Sale, SaleItem, Notification, Setting

APP_NAME = "BillSmart"
APP_VERSION = "1.0.0"


def is_frozen():
    return getattr(sys, "frozen", False)


def resource_path(relative):
    """Resolve bundled resources when running under PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / relative)


def get_data_dir():
    """Writable per-user data dir. Overridable via BILLSMART_DATA_DIR.

    - Installed desktop app (frozen exe, or BILLSMART_PORTABLE=installed
      which desktop.py sets): %APPDATA%\\BillSmart (per-user, writable).
    - Plain `python app.py` dev runs: the repo folder, so the existing
      inventory.db keeps working.
    """
    override = os.environ.get("BILLSMART_DATA_DIR")
    if override:
        data_dir = Path(override)
    elif is_frozen() or os.environ.get("BILLSMART_PORTABLE") == "installed":
        if os.name == "nt":
            root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
            data_dir = Path(root) / APP_NAME
        else:
            data_dir = Path.home() / f".{APP_NAME.lower()}"
    else:
        data_dir = Path(__file__).resolve().parent
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_secret_key(data_dir):
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    key_file = data_dir / "secret.key"
    try:
        if key_file.exists():
            saved = key_file.read_text().strip()
            if len(saved) >= 32:
                return saved
        new_key = secrets.token_hex(32)
        key_file.write_text(new_key)
        return new_key
    except OSError:
        return "billsmart-dev-secret-change-me"


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = get_data_dir()
DB_PATH = DATA_DIR / "inventory.db"
UPLOAD_DIR = DATA_DIR / "product_images"
# Fresh installs: migrate legacy images shipped next to the exe/static folder.
LEGACY_UPLOAD_DIR = Path(resource_path(os.path.join("static", "images", "products")))

if is_frozen():
    app = Flask(__name__, template_folder=resource_path("templates"), static_folder=resource_path("static"))
else:
    app = Flask(__name__)
app.config.update(
    SECRET_KEY=get_secret_key(DATA_DIR),
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{DB_PATH.as_posix()}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=4 * 1024 * 1024,
    UPLOAD_FOLDER=str(UPLOAD_DIR),
    REMEMBER_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
db.init_app(app)


def find_free_port(start=51230, end=51330):
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


def run_desktop_server(host="127.0.0.1", port=0):
    """Production server for the installed desktop app (waitress)."""
    port = port or find_free_port() or 5000
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=8)
    except ImportError:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    return port


def _migrate_legacy_images():
    """Copy repo/bundled product images into the writable data dir once."""
    candidates = [BASE_DIR / "static" / "images" / "products"]
    if LEGACY_UPLOAD_DIR != candidates[0]:
        candidates.append(LEGACY_UPLOAD_DIR)
    for src_dir in candidates:
        if not src_dir.is_dir():
            continue
        for item in src_dir.iterdir():
            if not item.is_file() or item.name.startswith("."):
                continue
            dest = UPLOAD_DIR / item.name
            if not dest.exists():
                try:
                    dest.write_bytes(item.read_bytes())
                except OSError:
                    pass


@app.route("/product_images/<path:filename>")
@login_required
def product_image(filename):
    """Serve uploads from the writable data dir, falling back to legacy paths."""
    safe = secure_filename(filename)
    for directory in (UPLOAD_DIR, BASE_DIR / "static" / "images" / "products", LEGACY_UPLOAD_DIR):
        candidate = directory / safe
        if candidate.is_file():
            return send_file(candidate)
    abort(404)


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "app": APP_NAME, "version": APP_VERSION})


@app.route("/api/app-info")
@login_required
def app_info():
    return jsonify({"app": APP_NAME, "version": APP_VERSION, "data_dir": str(DATA_DIR)})


def product_image_url(filename):
    if not filename:
        return ""
    return url_for("product_image", filename=filename)


app.jinja_env.globals["product_image_url"] = product_image_url
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(24)
    return session["csrf_token"]


def check_csrf():
    submitted = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
    if request.method == "POST" and submitted != session.get("csrf_token"):
        abort(400, description="Invalid form security token.")


def make_notification(title, message, kind="info"):
    with db.session.no_autoflush:
        for user in User.query.all():
            db.session.add(Notification(user_id=user.id, title=title, message=message, type=kind))


def seed_database():
    if User.query.count() == 0:
        admin = User(username="admin", email="admin@billsmart.local", role="admin")
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.flush()
        today = date.today()
        sample_products = [
            ("Aashirvaad Atta 1kg", "BS-ATTA-001", "Staples", 58, 46, 24, 5, None),
            ("Tata Salt 1kg", "BS-SALT-001", "Staples", 28, 21, 8, 5, None),
            ("Fortune Sunflower Oil 1L", "BS-OIL-001", "Cooking Oil", 142, 118, 3, 5, today + timedelta(days=15)),
            ("Maggi Noodles 70g", "BS-MAG-001", "Packaged Food", 14, 10, 0, 4, today - timedelta(days=1)),
            ("Amul Milk 1L", "BS-MILK-001", "Dairy", 68, 59, 18, 6, today + timedelta(days=2)),
            ("Parle-G Biscuits", "BS-BIS-001", "Packaged Food", 25, 18, 42, 8, today + timedelta(days=7)),
            ("Coca-Cola 750ml", "BS-COKE-001", "Beverages", 40, 31, 15, 5, today + timedelta(days=15)),
            ("Tata Tea 250g", "BS-TEA-001", "Beverages", 125, 101, 7, 5, today + timedelta(days=30)),
        ]
        for values in sample_products:
            db.session.add(Product(name=values[0], sku=values[1], category=values[2], price=values[3], cost_price=values[4], quantity=values[5], low_stock_threshold=values[6], expiry_date=values[7]))
        db.session.add(Setting())
        db.session.commit()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count() if current_user.is_authenticated else 0
    setting = Setting.query.first() or Setting()
    return {"csrf_token": csrf_token(), "unread_count": unread, "setting": setting, "now": datetime.now()}


@app.template_filter("date_label")
def date_label(value):
    return value.strftime("%d %b") if value else ""


@app.before_request
def before_request():
    if request.method == "POST":
        check_csrf()


@app.after_request
def add_no_cache_headers(response):
    if request.endpoint in ("dashboard", "inventory", "billing", "sales", "invoice", "customers", "suppliers", "reports", "notifications", "users", "settings"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.errorhandler(403)
def forbidden(error):
    return render_template("errors/403.html"), 403


@app.errorhandler(404)
def not_found(error):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template("errors/500.html"), 500


@app.route("/")
def index():
    return redirect(url_for("dashboard" if current_user.is_authenticated else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        identity = request.form.get("identity", "").strip()
        user = User.query.filter(or_(User.username.ilike(identity), User.email.ilike(identity))).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user, remember=bool(request.form.get("remember")))
            flash("Login successful.", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid username/email or password.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not username or not email or "@" not in email:
            flash("Enter a valid name and email address.", "danger")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif User.query.filter(or_(User.username.ilike(username), User.email.ilike(email))).first():
            flash("That username or email is already registered.", "danger")
        else:
            user = User(username=username, email=email, role="staff")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.pop("csrf_token", None)
    flash("Logged out successfully.", "success")
    resp = redirect(url_for("login"))
    resp.delete_cookie(app.config.get("REMEMBER_COOKIE_NAME", "remember_token"))
    return resp


@app.route("/dashboard")
@login_required
def dashboard():
    products = Product.query.order_by(Product.name).all()
    low_stock = Product.query.filter(Product.quantity <= Product.low_stock_threshold, Product.quantity > 0).order_by(Product.quantity).limit(6).all()
    out_stock = Product.query.filter_by(quantity=0).count()
    sales = Sale.query.order_by(desc(Sale.created_at)).limit(5).all()
    total_sales = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).scalar()
    total_profit = db.session.query(func.coalesce(func.sum(SaleItem.subtotal - (SaleItem.quantity * Product.cost_price)), 0)).join(Product, SaleItem.product_id == Product.id).scalar()
    total_purchases = db.session.query(func.coalesce(func.sum(SaleItem.quantity * Product.cost_price), 0)).join(Product, SaleItem.product_id == Product.id).scalar()
    total_orders = Sale.query.count()
    # Month-over-month (local server time)
    now = datetime.now()
    first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # first day next month
    if first_this.month == 12:
        first_next = first_this.replace(year=first_this.year+1, month=1)
    else:
        first_next = first_this.replace(month=first_this.month+1)
    first_last = (first_this - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    def pct(curr, prev):
        if prev and prev != 0:
            return round((curr - prev) / prev * 100, 1)
        return 100.0 if curr else 0.0
    curr_sales = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.created_at >= first_this).scalar() or 0
    prev_sales = db.session.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.created_at >= first_last, Sale.created_at < first_this).scalar() or 0
    curr_profit = db.session.query(func.coalesce(func.sum(SaleItem.subtotal - SaleItem.quantity * Product.cost_price), 0)).join(Product, SaleItem.product_id == Product.id).join(Sale, SaleItem.sale_id == Sale.id).filter(Sale.created_at >= first_this).scalar() or 0
    prev_profit = db.session.query(func.coalesce(func.sum(SaleItem.subtotal - SaleItem.quantity * Product.cost_price), 0)).join(Product, SaleItem.product_id == Product.id).join(Sale, SaleItem.sale_id == Sale.id).filter(Sale.created_at >= first_last, Sale.created_at < first_this).scalar() or 0
    curr_purchases = db.session.query(func.coalesce(func.sum(SaleItem.quantity * Product.cost_price), 0)).join(Product, SaleItem.product_id == Product.id).join(Sale, SaleItem.sale_id == Sale.id).filter(Sale.created_at >= first_this).scalar() or 0
    prev_purchases = db.session.query(func.coalesce(func.sum(SaleItem.quantity * Product.cost_price), 0)).join(Product, SaleItem.product_id == Product.id).join(Sale, SaleItem.sale_id == Sale.id).filter(Sale.created_at >= first_last, Sale.created_at < first_this).scalar() or 0
    curr_orders = Sale.query.filter(Sale.created_at >= first_this).count()
    prev_orders = Sale.query.filter(Sale.created_at >= first_last, Sale.created_at < first_this).count()
    sales_change = pct(curr_sales, prev_sales)
    profit_change = pct(curr_profit, prev_profit)
    purchases_change = pct(curr_purchases, prev_purchases)
    orders_change = pct(curr_orders, prev_orders)
    # Low stock change (snapshot, no history) -> 0
    low_stock_change = 0.0
    # Sales Overview aggregation with rolling week/month/year filter (chart only)
    sales_range = request.args.get("range", "month").strip().lower()
    if sales_range not in ("week", "month", "year"):
        sales_range = "month"
    sales_labels = []
    sales_data = []
    chart_sales = []
    if sales_range == "year":
        # Last 12 months monthly sums
        first_month = first_this.replace(day=1)
        # go back 11 months
        year = first_month.year
        month = first_month.month - 11
        while month <= 0:
            month += 12
            year -= 1
        start_date = datetime(year, month, 1)
        rows = db.session.query(func.strftime('%Y-%m', Sale.created_at), func.coalesce(func.sum(Sale.total_amount),0)).filter(Sale.created_at >= start_date).group_by(func.strftime('%Y-%m', Sale.created_at)).order_by(func.strftime('%Y-%m', Sale.created_at)).all()
        monthly_map = {r[0]: float(r[1] or 0) for r in rows}
        # build 12 month labels from start_date
        y, m = start_date.year, start_date.month
        for i in range(12):
            key = f"{y:04d}-{m:02d}"
            # label like Sep 2026
            label_date = datetime(y, m, 1)
            sales_labels.append(label_date.strftime('%b %Y'))
            sales_data.append(monthly_map.get(key, 0.0))
            m += 1
            if m > 12:
                m = 1
                y += 1
    else:
        days = 7 if sales_range == "week" else 30
        start_date = (now - timedelta(days=days-1)).replace(hour=0, minute=0, second=0, microsecond=0)
        rows = db.session.query(func.strftime('%Y-%m-%d', Sale.created_at), func.coalesce(func.sum(Sale.total_amount),0)).filter(Sale.created_at >= start_date).group_by(func.strftime('%Y-%m-%d', Sale.created_at)).order_by(func.strftime('%Y-%m-%d', Sale.created_at)).all()
        daily_map = {r[0]: float(r[1] or 0) for r in rows}
        for i in range(days):
            d = start_date + timedelta(days=i)
            key = d.strftime('%Y-%m-%d')
            sales_labels.append(d.strftime('%d %b'))
            sales_data.append(daily_map.get(key, 0.0))
            # also build chart_sales-like objects for backward compat if needed (not used)
    # also keep raw chart_sales for legacy (as daily totals)
    chart_sales_objs = Sale.query.order_by(Sale.created_at).all()
    category_rows = db.session.query(Product.category, func.sum(SaleItem.subtotal)).join(SaleItem, SaleItem.product_id == Product.id).group_by(Product.category).all()
    categories = [{"label": row[0], "value": float(row[1] or 0)} for row in category_rows]
    category_total = sum(c["value"] for c in categories)
    top_products = db.session.query(Product.name, func.sum(SaleItem.quantity)).join(SaleItem, SaleItem.product_id == Product.id).group_by(Product.name).order_by(desc(func.sum(SaleItem.quantity))).limit(6).all()
    # Expiry management
    today = date.today()
    expired_count = Product.query.filter(Product.expiry_date != None, Product.expiry_date < today).count()
    expiring_7_count = Product.query.filter(Product.expiry_date != None, Product.expiry_date >= today, Product.expiry_date <= today + timedelta(days=7)).count()
    expiring_30_count = Product.query.filter(Product.expiry_date != None, Product.expiry_date >= today, Product.expiry_date <= today + timedelta(days=30)).count()
    expiring_7 = Product.query.filter(Product.expiry_date != None, Product.expiry_date >= today, Product.expiry_date <= today + timedelta(days=7)).order_by(Product.expiry_date).limit(6).all()
    expiring_30 = Product.query.filter(Product.expiry_date != None, Product.expiry_date >= today, Product.expiry_date <= today + timedelta(days=30)).order_by(Product.expiry_date).limit(6).all()
    expired_list = Product.query.filter(Product.expiry_date != None, Product.expiry_date < today).order_by(Product.expiry_date).limit(6).all()
    at_risk_value = db.session.query(func.coalesce(func.sum(Product.quantity * Product.cost_price),0)).filter(Product.expiry_date != None, Product.expiry_date <= today + timedelta(days=30)).scalar() or 0
    # date range string for header
    end_date = now
    date_range = f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}"
    return render_template("dashboard.html", products=products, low_stock=low_stock, out_stock=out_stock, sales=sales, total_sales=total_sales, total_profit=total_profit, total_orders=total_orders, chart_sales=chart_sales_objs, categories=categories, top_products=top_products, total_purchases=total_purchases, sales_change=sales_change, profit_change=profit_change, purchases_change=purchases_change, orders_change=orders_change, low_stock_change=low_stock_change, sales_labels=sales_labels, sales_data=sales_data, category_total=category_total, date_range=date_range, expired_count=expired_count, expiring_7=expiring_7, expiring_30=expiring_30, expiring_7_count=expiring_7_count, expiring_30_count=expiring_30_count, expired_list=expired_list, at_risk_value=at_risk_value, today=today, sales_range=sales_range)


@app.route("/inventory")
@login_required
def inventory():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all")
    sort = request.args.get("sort", "name")
    query = Product.query
    if q:
        query = query.filter(or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%"), Product.category.ilike(f"%{q}%")))
    if status == "in": query = query.filter(Product.quantity > Product.low_stock_threshold)
    elif status == "low": query = query.filter(Product.quantity > 0, Product.quantity <= Product.low_stock_threshold)
    elif status == "out": query = query.filter_by(quantity=0)
    elif status == "expired": query = query.filter(Product.expiry_date != None, Product.expiry_date < date.today())
    elif status == "expiring": query = query.filter(Product.expiry_date != None, Product.expiry_date >= date.today(), Product.expiry_date <= date.today() + timedelta(days=30))
    if sort == "price": order = Product.price
    elif sort == "quantity": order = Product.quantity
    elif sort == "expiry": order = Product.expiry_date
    else: order = Product.name
    query = query.order_by(order)
    return render_template("inventory.html", products=query.all(), q=q, status=status, sort=sort)


@app.route("/inventory/add", methods=["GET", "POST"])
@login_required
def add_product():
    return product_form()


@app.route("/inventory/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    return product_form(db.get_or_404(Product, product_id))


def get_categories(current=None):
    rows = db.session.query(Product.category).distinct().order_by(Product.category).all()
    cats = [r[0].strip() for r in rows if r[0] and r[0].strip()]
    if "General" not in cats:
        cats.append("General")
    if current and current.strip() and current.strip() not in cats:
        cats.append(current.strip())
    return sorted(cats, key=str.lower)


def make_sku(name, try_sku=None, exclude_id=None):
    base_slug = re.sub(r'[^A-Z0-9]+', '-', (name or "").upper().strip()).strip('-')[:40] or "ITEM"
    base = f"BS-{base_slug}"[:80]
    candidate = (try_sku or base).upper().strip()[:80] or base
    if not candidate.startswith("BS-") and not try_sku:
        candidate = base
    i = 2
    while True:
        existing = Product.query.filter_by(sku=candidate).first()
        if not existing or (exclude_id and existing.id == exclude_id):
            return candidate
        # collision: suffix base (not candidate) to avoid BS-X-2-3 chains
        suffix = f"-{i}"
        candidate = (base[:80-len(suffix)] + suffix).upper()
        i += 1
        if i > 999:
            candidate = f"{base[:60]}-{secrets.token_hex(2).upper()}"
            existing = Product.query.filter_by(sku=candidate).first()
            if not existing:
                return candidate


def product_form(product=None):
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        posted_sku = request.form.get("sku", "").strip().upper()
        is_new_post = product is None
        if not is_new_post:
            sku = product.sku
        else:
            sku = posted_sku or make_sku(name)
            # auto-suffix on collision instead of blocking
            existing_sku = Product.query.filter_by(sku=sku).first()
            if existing_sku:
                sku = make_sku(name, try_sku=sku)
        sel = request.form.get("category", "").strip()
        custom = request.form.get("category_custom", "").strip()
        if sel == "__other__":
            if not custom:
                flash("Please enter custom category.", "danger")
                return render_template("product_form.html", product=product, categories=get_categories(product.category if product else None))
            category = custom[:80]
        else:
            if not sel:
                flash("Please select a category.", "danger")
                return render_template("product_form.html", product=product, categories=get_categories(product.category if product else None))
            category = sel[:80]
        expiry_raw = request.form.get("expiry_date", "").strip()
        expiry_date = None
        if expiry_raw:
            try:
                expiry_date = datetime.strptime(expiry_raw, "%Y-%m-%d").date()
            except ValueError:
                flash("Invalid expiry date format. Use YYYY-MM-DD.", "danger")
                return render_template("product_form.html", product=product, categories=get_categories(product.category if product else None))
        try:
            price, cost, qty, threshold = float(request.form.get("price", 0)), float(request.form.get("cost_price", 0)), int(request.form.get("quantity", 0)), int(request.form.get("low_stock_threshold", 5))
        except ValueError:
            flash("Use valid numbers for price and stock fields.", "danger")
            return render_template("product_form.html", product=product, categories=get_categories(product.category if product else None))
        if not name or not sku:
            flash("Product name is required.", "danger")
            return render_template("product_form.html", product=product, categories=get_categories(product.category if product else None))
        is_new = product is None
        if is_new:
            product = Product()
            db.session.add(product)
            message = "Product added successfully."
        else:
            message = "Product updated successfully."
        product.name, product.sku, product.category, product.price, product.cost_price, product.quantity, product.low_stock_threshold = name, sku, category, price, cost, max(0, qty), max(0, threshold)
        product.expiry_date = expiry_date
        if is_new:
            make_notification("New product added", f"{name} was added to your catalog.", "success")
        image = request.files.get("image")
        if image and image.filename and allowed_file(image.filename):
            filename = f"{secrets.token_hex(8)}_{secure_filename(image.filename)}"
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            product.image = filename
        db.session.commit()
        flash(message, "success")
        return redirect(url_for("inventory"))
    return render_template("product_form.html", product=product, categories=get_categories(product.category if product else None))


@app.route("/inventory/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id):
    product = db.get_or_404(Product, product_id)
    if product.items:
        flash("Products used in sales cannot be deleted; set stock to zero instead.", "warning")
    else:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted successfully.", "success")
    return redirect(url_for("inventory"))


@app.route("/billing")
@login_required
def billing():
    products = Product.query.filter(Product.quantity > 0).order_by(Product.name).all()
    customers = Customer.query.order_by(Customer.name).all()
    return render_template("billing.html", products=products, customers=customers)


@app.route("/api/products")
@login_required
def product_api():
    q = request.args.get("q", "").strip()
    products = Product.query.filter(Product.quantity > 0, or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%"))).limit(30).all()
    return jsonify([{"id": p.id, "name": p.name, "sku": p.sku, "price": p.price, "quantity": p.quantity, "category": p.category} for p in products])


@app.route("/billing/complete", methods=["POST"])
@login_required
def complete_sale():
    data = request.get_json(silent=True) or request.form
    items = data.get("items", [])
    if isinstance(items, str):
        import json
        items = json.loads(items)
    if not items:
        return jsonify({"error": "Cart is empty."}), 400
    try:
        customer_id = int(data.get("customer_id")) if data.get("customer_id") else None
        discount = max(0, float(data.get("discount", 0)))
        tax_rate = max(0, float(data.get("tax", 0)))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid sale values."}), 400
    subtotal = 0
    prepared = []
    for item in items:
        product = db.session.get(Product, int(item["id"]))
        quantity = int(item["quantity"])
        if not product or quantity < 1 or quantity > product.quantity:
            return jsonify({"error": f"Insufficient stock for {product.name if product else 'a product'}."}), 400
        line_total = product.price * quantity
        subtotal += line_total
        prepared.append((product, quantity, line_total))
    discount = min(discount, subtotal)
    tax = (subtotal - discount) * tax_rate / 100
    total = subtotal - discount + tax
    invoice = f"BS-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
    sale = Sale(invoice_number=invoice, customer_id=customer_id, subtotal=subtotal, discount=discount, tax=tax, total_amount=total, payment_method=data.get("payment_method", "Cash"), created_by=current_user.id)
    db.session.add(sale)
    db.session.flush()
    for product, quantity, line_total in prepared:
        product.quantity -= quantity
        db.session.add(SaleItem(sale_id=sale.id, product_id=product.id, quantity=quantity, price=product.price, subtotal=line_total))
        if product.quantity == 0 or product.quantity <= product.low_stock_threshold:
            make_notification("Inventory alert", f"{product.name} has only {product.quantity} units remaining.", "warning")
        if product.expiry_date:
            days = (product.expiry_date - date.today()).days
            if days < 0:
                make_notification("Expiry alert", f"{product.name} expired on {product.expiry_date.strftime('%d %b %Y')} ({abs(days)}d overdue).", "danger")
            elif days <= 7:
                make_notification("Expiry alert", f"{product.name} expires in {days} days on {product.expiry_date.strftime('%d %b %Y')}.", "warning")
            elif days <= 30:
                make_notification("Expiry alert", f"{product.name} expires in {days} days.", "warning")
    make_notification("New sale recorded", f"Invoice {invoice} was completed for {total:.2f}.", "success")
    db.session.commit()
    return jsonify({"redirect": url_for("invoice", sale_id=sale.id)})


@app.route("/invoice/<int:sale_id>")
@login_required
def invoice(sale_id):
    return render_template("invoice.html", sale=db.get_or_404(Sale, sale_id))


@app.route("/sales")
@login_required
def sales():
    q = request.args.get("q", "").strip()
    query = Sale.query.outerjoin(Customer)
    if q:
        query = query.filter(or_(Sale.invoice_number.ilike(f"%{q}%"), Customer.name.ilike(f"%{q}%")))
    return render_template("sales.html", sales=query.order_by(desc(Sale.created_at)).all(), q=q)


@app.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    if request.method == "POST":
        db.session.add(Customer(name=request.form.get("name", "").strip(), phone=request.form.get("phone"), email=request.form.get("email"), address=request.form.get("address")))
        db.session.commit(); flash("Customer added successfully.", "success"); return redirect(url_for("customers"))
    q = request.args.get("q", "")
    records = Customer.query.filter(or_(Customer.name.ilike(f"%{q}%"), Customer.phone.ilike(f"%{q}%"))).order_by(Customer.name).all() if q else Customer.query.order_by(Customer.name).all()
    return render_template("customers.html", customers=records, q=q)


@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(customer_id):
    customer = db.get_or_404(Customer, customer_id)
    if request.method == "POST":
        customer.name, customer.phone, customer.email, customer.address = request.form.get("name"), request.form.get("phone"), request.form.get("email"), request.form.get("address")
        db.session.commit(); flash("Customer updated successfully.", "success"); return redirect(url_for("customers"))
    return render_template("customer_form.html", customer=customer)


@app.route("/customers/<int:customer_id>/delete", methods=["POST"])
@login_required
def delete_customer(customer_id):
    customer = db.get_or_404(Customer, customer_id)
    if customer.sales: flash("Customers with sales history cannot be deleted.", "warning")
    else: db.session.delete(customer); db.session.commit(); flash("Customer deleted successfully.", "success")
    return redirect(url_for("customers"))


@app.route("/suppliers", methods=["GET", "POST"])
@login_required
def suppliers():
    if request.method == "POST":
        db.session.add(Supplier(name=request.form.get("name", "").strip(), phone=request.form.get("phone"), email=request.form.get("email"), address=request.form.get("address")))
        db.session.commit(); flash("Supplier added successfully.", "success"); return redirect(url_for("suppliers"))
    q = request.args.get("q", "")
    records = Supplier.query.filter(or_(Supplier.name.ilike(f"%{q}%"), Supplier.phone.ilike(f"%{q}%"))).order_by(Supplier.name).all() if q else Supplier.query.order_by(Supplier.name).all()
    return render_template("suppliers.html", suppliers=records, q=q)


@app.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
@login_required
def edit_supplier(supplier_id):
    supplier = db.get_or_404(Supplier, supplier_id)
    if request.method == "POST":
        supplier.name, supplier.phone, supplier.email, supplier.address = request.form.get("name"), request.form.get("phone"), request.form.get("email"), request.form.get("address")
        db.session.commit(); flash("Supplier updated successfully.", "success"); return redirect(url_for("suppliers"))
    return render_template("supplier_form.html", supplier=supplier)


@app.route("/suppliers/<int:supplier_id>/delete", methods=["POST"])
@login_required
def delete_supplier(supplier_id):
    db.session.delete(db.get_or_404(Supplier, supplier_id)); db.session.commit(); flash("Supplier deleted successfully.", "success"); return redirect(url_for("suppliers"))


@app.route("/notifications")
@login_required
def notifications():
    return render_template("notifications.html", notifications=Notification.query.filter_by(user_id=current_user.id).order_by(desc(Notification.created_at)).all())


@app.route("/notifications/read/<int:notification_id>", methods=["POST"])
@login_required
def mark_notification(notification_id):
    notification = db.get_or_404(Notification, notification_id)
    if notification.user_id != current_user.id: abort(403)
    notification.is_read = True; db.session.commit(); return redirect(url_for("notifications"))


@app.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True}); db.session.commit(); flash("All notifications marked as read.", "success"); return redirect(url_for("notifications"))


@app.route("/notifications/delete/<int:notification_id>", methods=["POST"])
@login_required
def delete_notification(notification_id):
    notification = db.get_or_404(Notification, notification_id)
    if notification.user_id != current_user.id: abort(403)
    db.session.delete(notification); db.session.commit(); return redirect(url_for("notifications"))


@app.route("/reports")
@login_required
def reports():
    sales = Sale.query.order_by(Sale.created_at).all()
    revenue = sum(s.total_amount for s in sales)
    profit = db.session.query(func.coalesce(func.sum(SaleItem.subtotal - SaleItem.quantity * Product.cost_price), 0)).join(Product).scalar()
    best_product = db.session.query(Product.name, func.sum(SaleItem.quantity)).join(SaleItem).group_by(Product.id).order_by(desc(func.sum(SaleItem.quantity))).first()
    best_category = db.session.query(Product.category, func.sum(SaleItem.subtotal)).join(SaleItem).group_by(Product.category).order_by(desc(func.sum(SaleItem.subtotal))).first()
    today = date.today()
    expired = Product.query.filter(Product.expiry_date != None, Product.expiry_date < today).count()
    expiring_7 = Product.query.filter(Product.expiry_date != None, Product.expiry_date >= today, Product.expiry_date <= today + timedelta(days=7)).count()
    expiring_30 = Product.query.filter(Product.expiry_date != None, Product.expiry_date >= today, Product.expiry_date <= today + timedelta(days=30)).count()
    at_risk = db.session.query(func.coalesce(func.sum(Product.quantity * Product.cost_price),0)).filter(Product.expiry_date != None, Product.expiry_date <= today + timedelta(days=30)).scalar() or 0
    return render_template("reports.html", sales=sales, revenue=revenue, profit=profit, best_product=best_product, best_category=best_category, low_stock=Product.query.filter(Product.quantity <= Product.low_stock_threshold, Product.quantity > 0).count(), out_stock=Product.query.filter_by(quantity=0).count(), expired=expired, expiring_7=expiring_7, expiring_30=expiring_30, at_risk=at_risk)


@app.route("/reports/export")
@admin_required
def export_reports():
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(["Invoice", "Date", "Customer", "Payment", "Amount"])
    for sale in Sale.query.order_by(Sale.created_at).all(): writer.writerow([sale.invoice_number, sale.created_at.isoformat(), sale.customer.name if sale.customer else "Walk-in", sale.payment_method, sale.total_amount])
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="billsmart-sales.csv")


@app.route("/users")
@admin_required
def users():
    return render_template("users.html", users=User.query.order_by(User.created_at).all())


@app.route("/users/new", methods=["GET", "POST"])
@admin_required
def new_user():
    if request.method == "POST":
        username, email, password, role = request.form.get("username", "").strip(), request.form.get("email", "").strip().lower(), request.form.get("password", ""), request.form.get("role", "staff")
        if not username or not email or len(password) < 8 or User.query.filter(or_(User.username == username, User.email == email)).first():
            flash("Enter unique user details and a password of at least 8 characters.", "danger")
        else:
            user = User(username=username, email=email, role=role if role in ("admin", "staff") else "staff"); user.set_password(password); db.session.add(user); db.session.commit(); flash("User created successfully.", "success"); return redirect(url_for("users"))
    return render_template("user_form.html", user=None)


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    if request.method == "POST":
        user.username, user.email, user.role = request.form.get("username"), request.form.get("email"), request.form.get("role")
        if request.form.get("password"): user.set_password(request.form.get("password"))
        db.session.commit(); flash("User updated successfully.", "success"); return redirect(url_for("users"))
    return render_template("user_form.html", user=user)


@app.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    if user_id == current_user.id: flash("You cannot delete your own account.", "warning")
    else: db.session.delete(db.get_or_404(User, user_id)); db.session.commit(); flash("User deleted successfully.", "success")
    return redirect(url_for("users"))


@app.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    setting = Setting.query.first() or Setting()
    if request.method == "POST":
        setting.shop_name, setting.shop_email, setting.phone, setting.address, setting.currency, setting.theme = request.form.get("shop_name"), request.form.get("shop_email"), request.form.get("phone"), request.form.get("address"), request.form.get("currency"), request.form.get("theme", "light")
        db.session.add(setting); db.session.commit(); flash("Settings saved successfully.", "success"); return redirect(url_for("settings"))
    return render_template("settings.html", setting=setting)


@app.route("/settings/backup")
@admin_required
def backup_data():
    """Download a zip of the database + product images (todo.md: add backups)."""
    _migrate_legacy_images()
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as bundle:
        if DB_PATH.is_file():
            bundle.write(DB_PATH, arcname="inventory.db")
        if UPLOAD_DIR.is_dir():
            for item in sorted(UPLOAD_DIR.iterdir()):
                if item.is_file() and not item.name.startswith("."):
                    bundle.write(item, arcname=f"product_images/{item.name}")
    memory.seek(0)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return send_file(
        memory,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"billsmart-backup-{stamp}.zip",
    )


with app.app_context():
    db.create_all()
    seed_database()
    _migrate_legacy_images()

if __name__ == "__main__":
    if is_frozen() or os.environ.get("BILLSMART_PORTABLE") == "installed":
        run_desktop_server()
    else:
        app.run(debug=True)
