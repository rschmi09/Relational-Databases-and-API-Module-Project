# Module Project: Building an E-Commerce API with Flask, SQLAlchemy, Marshmallow, and MySQL
from __future__ import annotations
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy import ForeignKey, Table, Column, Integer, String, select
from marshmallow import ValidationError, fields, validate, validates
from typing import List, Optional
from sqlalchemy import DateTime, func, Numeric


# Initialize Flask app
app = Flask(__name__)

# MySQL database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:root2@localhost/ecommerce_api'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy and Marshmallow (extensions)
db = SQLAlchemy(app)
ma = Marshmallow(app)

#---------------------------
# Association Table and Models
#---------------------------

# Association Table for Many-to-Many (Many Orders to Many Products)
order_product = db.Table(
    'order_product',
    db.metadata,
    db.Column('order_id', ForeignKey('orders.id'), primary_key=True),      # Because this is a primary key, it cannot be duplicated
    db.Column('product_id', ForeignKey('products.id'), primary_key=True)   # Because this is a primary key, it cannot be duplicated
)

# Models
class User(db.Model):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    address: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(200), unique=True)
    
    # One-to-Many relationship from this User to a List of Orders
    orders: Mapped[List['Order']] = relationship(
        'Order', 
        back_populates='user',
        cascade='all, delete-orphan'
    )

class Order(db.Model):
    __tablename__ = 'orders'

    id: Mapped[int] = mapped_column(primary_key=True)
    order_date: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), # Database sets the time
        nullable=False 
    )
    user_id: Mapped[int] = mapped_column(db.ForeignKey('users.id'), nullable=False)
    #quantity: Mapped[int] = mapped_column(nullable=False)
    #status: Mapped[bool] = mapped_column(default=False, nullable=False)
    
    # Many-to-One relationship, Many Orders to One User
    user: Mapped['User'] = relationship('User', back_populates='orders')
    
    # Many-to-Many relationship from this Order to a List of Products
    products: Mapped[List['Product']] = relationship(
        'Product', 
        secondary=order_product, 
        back_populates='orders'
    )

class Product(db.Model):
    __tablename__ = 'products'

    id: Mapped[int] = mapped_column(primary_key=True)
    product_name: Mapped[str] = mapped_column(String(60), nullable=False)
    price: Mapped[float] = mapped_column(
        Numeric(10, 2),         # 10 total digits, 2 after decimal
        nullable=False
    )
    
    # Many-to-Many relationship from this Product to a List of Orders
    orders: Mapped[List['Order']] = relationship(
        'Order', 
        secondary=order_product, 
        back_populates='products'
    )

#---------------------------
# Define Marshmallow Schemas
#---------------------------

# User Schema
class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        include_fk = True

# Order Schema
class OrderSchema(ma.SQLAlchemyAutoSchema):
    user_id = fields.Integer(required=True)
    order_date = fields.DateTime(required=False, allow_none=True)

    class Meta:
        model = Order
        include_fk = True

    @validates("user_id",)
    def validate_user_id(self, value):
        if not db.session.get(User, value):
            raise ValidationError("User ID does not exist.")

# Product Schema
class ProductSchema(ma.SQLAlchemyAutoSchema):
    price = fields.Float(
        attribute="price",
        required=True, 
        validate=validate.Range(min=0)
    )

    class Meta:
        model = Product
        include_fk = True


#---------------------------
# Initialize Schemas
#---------------------------

user_schema = UserSchema()                    # Handles serialization and deserialization of the User model
users_schema = UserSchema(many=True)          # Can serialize many User objects (a list of them)
order_schema = OrderSchema()                  # Handles serialization and deserialization of the Order model
orders_schema = OrderSchema(many=True)        # Can serialize many Order objects (a list of them)
product_schema = ProductSchema()              # Handles serialization and deserialization of the Product model
products_schema = ProductSchema(many=True)    # Can serialize many Product objects (a list of them)


#---------------------------
# Creating API Endpoints
#---------------------------

# ---------------------------
# User Endpoints
# ---------------------------

# Create a new user
@app.route('/users', methods=['POST'])
def create_user():
    try:
        # Expect a "users" key containing a list - having trouble with postman
        users_list = request.json.get("users")
        if not users_list:
            return jsonify({"error": 'request must be an object with a "users" key containing an array'}), 400

        new_users = []
        for user_data in users_list:
            # Validate each user dict using your schema
            validated_data = user_schema.load(user_data)
            new_user = User(
                name=validated_data['name'],
                address=validated_data['address'],
                email=validated_data.get('email')
            )

            db.session.add(new_user)
            new_users.append(new_user)

        db.session.commit()

    except ValidationError as e:
        return jsonify(e.messages), 400

    return users_schema.jsonify(new_users), 201



# Retrieve/Read all users
@app.route('/users', methods=['GET'])
def get_users():
   query = select(User)
   users = db.session.execute(query).scalars().all()

   return users_schema.jsonify(users), 200


# Retrieve a single user by ID
@app.route('/users/<int:id>', methods=['GET'])
def get_user(id):
    user = db.session.get(User, id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    return user_schema.jsonify(user), 200


# Update a user by ID
@app.route('/users/<int:id>', methods=['PUT'])
def update_user(id):
    user = db.session.get(User, id)
    
    if not user:
        return jsonify({"message": "Invalid User ID"}), 400
    
    try:
        user_data = user_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400
    
    user.name = user_data['name']
    user.address = user_data['address']
    user.email = user_data['email']

    db.session.commit()
    return user_schema.jsonify(user), 200


# Delete a user by ID
@app.route('/users/<int:id>', methods=['DELETE'])
def delete_user(id):
    user = db.session.get(User, id)
    
    if not user:
        return jsonify({"message": "Invalid User ID"}), 400
    
    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "User deleted"}), 200


#---------------------------
# Product Endpoints
#---------------------------

# Create a new product
@app.route('/products', methods=['POST'])
def create_product():
    try:
        products_list = request.json.get("products")
        if not products_list:
            return jsonify({"error": 'request must be an object with a "products" key containing an array'}), 400

        new_products = []
        for product_data in products_list:
            validated_data = product_schema.load(product_data)
            new_product = Product(
                product_name=validated_data['product_name'],
                price=validated_data['price']
            )
            db.session.add(new_product)
            new_products.append(new_product)

        db.session.commit()

    except ValidationError as e:
        return jsonify(e.messages), 400

    return products_schema.jsonify(new_products), 201



# Retrieve/Read all products
@app.route('/products', methods=['GET'])
def get_products():
   query = select(Product)
   products = db.session.execute(query).scalars().all()
   return products_schema.jsonify(products), 200


# Retrieve a single product by ID
@app.route('/products/<int:id>', methods=['GET'])
def get_product(id):
    product = db.session.get(Product, id)
    if not product:
        return jsonify({"message": "Product not found"}), 404
    return product_schema.jsonify(product), 200


# Update a product by ID
@app.route('/products/<int:id>', methods=['PUT'])
def update_product(id):
    product = db.session.get(Product, id)

    if not product:
        return jsonify({"message": "Invalid Product ID"}), 400

    try:
        product_data = product_schema.load(request.json)
    except ValidationError as e:
        return jsonify(e.messages), 400

    product.product_name = product_data['product_name']
    product.price = product_data['price']

    db.session.commit()

    return product_schema.jsonify(product), 200


# Delete a product by ID
@app.route('/products/<int:id>', methods=['DELETE'])
def delete_product(id):
    product = db.session.get(Product, id)

    if not product:
        return jsonify({"message": "Invalid Product ID"}), 400

    db.session.delete(product)
    db.session.commit()

    return jsonify({"message": "Product deleted"}), 200


#---------------------------
# Order Endpoints
#---------------------------

# Create a new order
@app.route('/orders', methods=['POST'])
def create_order():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 415

    data = request.json
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User does not exist"}), 400

    try:
        new_order = Order(user_id=user_id)
        db.session.add(new_order)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "id": new_order.id,
        "user_id": new_order.user_id,
        "order_date": str(new_order.order_date)
    }), 201



# Add a product to an order
@app.route("/orders/<int:order_id>/add_product/<int:product_id>", methods=["PUT"])
def add_product_to_order(order_id, product_id):
    order = db.session.get(Order, order_id)
    product = db.session.get(Product, product_id)

    if not order or not product:
        return jsonify({"message": "Order or Product not found"}), 404

    if product in order.products:
        return jsonify({"message": "Product already in order"}), 400

    order.products.append(product)
    db.session.commit()

    return order_schema.jsonify(order), 200


# Retrieve/Read all orders for a user
@app.route("/orders/user/<int:user_id>", methods=["GET"])
def get_orders_for_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    return orders_schema.jsonify(user.orders), 200


# Retrieve/Read all products in an order
@app.route("/orders/<int:order_id>/products", methods=["GET"])
def get_products_for_order(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({"message": "Order not found"}), 404

    return products_schema.jsonify(order.products), 200


# Delete an order by ID
@app.route("/orders/<int:order_id>/remove_product/<int:product_id>", methods=["DELETE"])
def remove_product_from_order(order_id, product_id):
    order = db.session.get(Order, order_id)
    product = db.session.get(Product, product_id)

    if not order or not product:
        return jsonify({"message": "Order or Product not found"}), 404
    
    if product not in order.products:
        return jsonify({"message": "Product not in order"}), 400
    
    order.products.remove(product)
    db.session.commit()

    return jsonify({"message": "Product removed from order"}), 200


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    
    app.run(debug=True)