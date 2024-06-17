import os
import random
from flask import Flask, render_template, redirect, request, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from sqlalchemy.sql.expression import func

from utils import check_in_session, protected

admin_code = "1234"  # Admin code should be stored securely
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "your_secret_key"
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30))
    password = db.Column(db.String(30))
    is_admin = db.Column(db.Boolean, default=False)
    balance = db.Column(db.Float, default=200.0)
    credit_card_code = db.Column(db.String(16), default=''.join([str(random.randint(0, 9)) for _ in range(16)]))


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    price = db.Column(db.Integer)
    name = db.Column(db.String(30))
    image = db.Column(db.String(500))

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    product = db.relationship('Product', backref=db.backref('comments', lazy=True))

def is_user_admin():
    if 'user' in session and session['user'].get('is_admin', False):
        return True
    return False


@app.route("/")
def products():
    is_admin = is_user_admin()
    return render_template("main.html", queryset=Product.query.all(), check_in_session=check_in_session, is_admin=is_admin)


@app.route("/apply_promo_code/<int:id>", methods=["POST"])
def apply_promo_code(id):
    product = Product.query.get(id)
    if not product:
        return "Product not found", 404

    promo_code = request.form.get("promo_code")
    discount_rates = {"CODE1": 0.1, "CODE2": 0.25, "CODE3": 0.5, "CODE4": 1}

    # Check if the promo code is valid
    if promo_code in discount_rates:
        # Apply the discount to the product's price
        discount_rate = discount_rates[promo_code]
        discounted_price = product.price * (1 - discount_rate)
        
        # Store discounted price in session
        session["discounted_price"] = discounted_price
    else:
        # If the promo code is invalid or not provided, store original price in session
        session["discounted_price"] = product.price

    return render_template("order1.html", product=product, discounted_price=session["discounted_price"])


@app.route("/checkout/<int:id>")
def checkout(id):
    product = Product.query.get(id)
    if not product:
        print("Product not found")
    
    # If no discount, render the page with the original product price
    return render_template("order1.html", product=product)

@app.route("/checkout/1/<int:id>")
def checkout1(id):
    product = Product.query.get(id)
    # Retrieve discounted price from session if it exists, otherwise, use the original price
    discounted_price = session.get("discounted_price", product.price)
    return render_template("order2.html", product=product, discounted_price=discounted_price)

@app.route("/apple")
def apple():
    return render_template("apple.html")

@app.route("/google")
def google():
    return render_template("google.html")


@app.route("/playstation")
def playstation():
    return render_template("playstation.html")

@app.route("/search_results", methods=["GET"])
def search_results():
    query = request.args.get("query", "")
    search = "%{}%".format(query)
    results = Product.query.filter(Product.name.like(search)).all()
    results_count = len(results)
    return render_template("search_results.html", queryset=results, results_count=results_count)

@app.route("/profile/<int:id>")
def get_profile(id):
    user = User.query.get(id)
    return render_template("profile.html", username=user.username, password=user.password, is_admin=user.is_admin, balance=user.balance, credit_card_code=user.credit_card_code)


@app.route("/products", methods=["POST"])
def add_products():
    name = request.form["name"]
    price = request.form["price"]
    image = request.files["image"]
    if image.filename == "":
        return "No selected file"
    
    filename = secure_filename(image.filename)
    filepath = os.path.join(app.root_path, 'static', filename)
    image.save(filepath)

    product = Product(name=name, price=price, image=filename)
    db.session.add(product)
    db.session.commit()
    return redirect(url_for("admin_page"))


@app.route("/delete_product/<int:id>", methods=["POST"])
def delete_product(id):
    product = Product.query.get(id)
    if product:
        db.session.delete(product)
        db.session.commit()
    return redirect(url_for("admin_page"))

@app.route("/favourites")
@protected
def favourites():
    if 'products' not in session:
        return 'No products found'

    ids = session.get("products")
    products = Product.query.filter(Product.id.in_(ids)).all()

    return render_template("favourites.html", queryset=products)

@app.route("/add_to_favorite/<int:id>")
def add_to_favorite(id):
    if "products" not in session:
        session["products"] = []

    if not check_in_session(id):
        session["products"].append(id)
        session.modified = True

    return redirect(url_for("products"))

@app.route("/remove_from_favorites/<int:id>")
def remove_from_favorite(id):
    if check_in_session(id):
        session["products"].remove(id)
        session.modified = True

    return redirect(url_for("products"))

@app.route('/edit_product_name/<int:id>', methods=['POST'])
def edit_product_name(id):
    if 'user' in session and session['user']['is_admin']:
        product = Product.query.get_or_404(id)
        product.name = request.form['name']
        db.session.commit()
    return redirect(url_for('product', id=id))

@app.route('/edit_product_price/<int:id>', methods=['POST'])
def edit_product_price(id):
    if 'user' in session and session['user']['is_admin']:
        product = Product.query.get_or_404(id)
        product.price = request.form['price']
        db.session.commit()
    return redirect(url_for('product', id=id))

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register_post():
    username = request.form["username"]
    password = request.form["password"]
    role = request.form["role"]
    admin_code_input = request.form.get("adminCode", "")
    credit_card_code = ''.join([str(random.randint(0, 9)) for _ in range(12)])

    if role == "admin" and admin_code_input == admin_code:
        user = User(username=username, password=password, is_admin=True, credit_card_code=credit_card_code)
    elif role == "user":
        user = User(username=username, password=password, is_admin=False, credit_card_code=credit_card_code)
    else:
        return "Invalid admin code"

    db.session.add(user)
    db.session.commit()
    return redirect(url_for("login"))


@app.route("/admin_page")
def admin_page():
    return render_template("admin.html", products=Product.query.all())

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    username = request.form["username"]
    password = request.form["password"]
    user = User.query.filter_by(username=username, password=password).first()
    if user:
        session['user'] = {'id': user.id, 'username': user.username, "is_admin": user.is_admin}
        session.modified = True
        if user.is_admin:
            return redirect(url_for("admin_page"))
        return redirect(url_for("products"))

    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    del session["user"]
    session.modified = True
    return redirect(url_for("products"))

from sqlalchemy.sql.expression import func

@app.route("/product/<int:id>", methods=["GET", "POST"])
def product(id):
    product = Product.query.get(id)
    if not product:
        print("ABORT")  # or return a custom error page


    if request.method == "POST":
        text = request.form["comment"]
        comment = Comment(text=text, product_id=id)
        db.session.add(comment)
        db.session.commit()
        # Redirect to avoid form resubmission on refresh
        return redirect(url_for('product', id=id))

    # Get two random product IDs excluding the current product
    random_products = Product.query.filter(Product.id != id).order_by(func.random()).limit(1).all()
    random_products1 = Product.query.filter(Product.id != id).order_by(func.random()).limit(1).all()


    return render_template("product.html", product=product, random_products=random_products,random_products1=random_products1)




if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
