from flask import Flask, redirect, render_template
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime

from flask_login import UserMixin, LoginManager, login_user, logout_user, current_user

app = Flask(__name__)
app.config["SECRET_KEY"] = "mysecret"


basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    basedir, "data.sqlite"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
Migrate(app, db)


class PrintableMixin:
    def __repr__(self):
        """
        Gives detailed reprs like
            <Product {'description': 'A small widget', 'name': 'Widget', 'price': 10, 'category': 'Widgets', 'id': 1, 'ingredients': 'Metal, plastic'}>
        """
        clean_dict = {k: v for (k, v) in self.__dict__.items() if not k.startswith("_")}
        return f"<{self.__class__.__name__} {repr(clean_dict)}>"


class Product(PrintableMixin, db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=True)
    description = db.Column(db.String, nullable=True)
    category = db.Column(db.String, nullable=True)
    price = db.Column(db.Integer, nullable=True)
    ingredients = db.Column(db.String, nullable=True)

    order_products = db.relationship("OrderProduct", back_populates="product")


class Order(PrintableMixin, db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String, nullable=True)
    order_date = db.Column(db.String, default=datetime.utcnow, nullable=True)

    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id", name="order_customer_fk"),
        nullable=True,
    )
    customer = db.relationship(
        "Customer", foreign_keys=[customer_id], back_populates="orders"
    )

    order_products = db.relationship("OrderProduct", back_populates="order")


class OrderProduct(PrintableMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id", name="orderproduct_order_fk"),
        nullable=True,
    )
    order = db.relationship(
        "Order", foreign_keys=[order_id], back_populates="order_products"
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id", name="orderproduct_product_fk"),
        nullable=True,
    )
    product = db.relationship(
        "Product", foreign_keys=[product_id], back_populates="order_products"
    )


class Customer(PrintableMixin, db.Model, UserMixin):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=True)
    address = db.Column(db.String, nullable=True)
    phone = db.Column(db.String, nullable=True)

    orders = db.relationship("Order", back_populates="customer")


login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return Customer.query.get_or_404(user_id)


@app.route("/login-bob")
def login_bob():
    bob = Customer.query.get_or_404(3)
    login_user(bob)
    return redirect("/whoami")


@app.route("/whoami")
def whoami():
    if current_user.is_authenticated:
        return f"Current user is {current_user.first_name} {current_user.last_name}"
    else:
        return "No user is logged in"


@app.route("/logout")
def logout():
    logout_user()
    return redirect("/whoami")


# prevent browser autofetched favicon request from going to GPT
@app.route("/favicon.ico")
def favicon():
    return ("No favicon", 404)


@app.route("/test-frame")
def test_frame():
    return render_template("frame-test.html")


###

from gpt_http import gpt_hallucinate

gpt_hallucinate(app, get_gbls=lambda: globals())

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=7500)
