from datetime import date, datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    sales = db.relationship("Sale", backref="creator", lazy=True)
    notifications = db.relationship("Notification", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    sku = db.Column(db.String(80), unique=True, nullable=False)
    category = db.Column(db.String(80), nullable=False, default="General")
    price = db.Column(db.Float, nullable=False, default=0)
    cost_price = db.Column(db.Float, nullable=False, default=0)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=5)
    expiry_date = db.Column(db.Date, nullable=True)
    image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    items = db.relationship("SaleItem", backref="product", lazy=True)

    @property
    def status(self):
        if self.quantity == 0:
            return "Out of Stock"
        if self.expiry_date and self.expiry_date < date.today():
            return "Expired"
        if self.quantity <= self.low_stock_threshold:
            return "Low Stock"
        return "In Stock"

    @property
    def expiry_status(self):
        if not self.expiry_date:
            return None
        today = date.today()
        delta = (self.expiry_date - today).days
        if delta < 0:
            return "Expired"
        if delta <= 7:
            return "Expiring Soon"
        if delta <= 30:
            return "Expiring"
        return "Fresh"

    @property
    def days_to_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(40))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    sales = db.relationship("Sale", backref="customer", lazy=True)


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    phone = db.Column(db.String(40))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(40), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    total_amount = db.Column(db.Float, nullable=False, default=0)
    subtotal = db.Column(db.Float, nullable=False, default=0)
    discount = db.Column(db.Float, nullable=False, default=0)
    tax = db.Column(db.Float, nullable=False, default=0)
    payment_method = db.Column(db.String(30), nullable=False, default="Cash")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    items = db.relationship("SaleItem", backref="sale", lazy=True, cascade="all, delete-orphan")


class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(30), nullable=False, default="info")
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(140), default="BillSmart Store")
    shop_email = db.Column(db.String(120), default="hello@billsmart.local")
    phone = db.Column(db.String(40), default="")
    address = db.Column(db.Text, default="")
    currency = db.Column(db.String(10), default="₹")
    theme = db.Column(db.String(20), default="light")
