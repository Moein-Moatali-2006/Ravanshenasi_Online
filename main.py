from flask import Flask, render_template
from database import create_db_and_tables


app = Flask("Ravanshenasi Online")


with app.app_context():
    create_db_and_tables()

@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")

@app.route("/about/", methods=["GET"])
def about():
    return render_template("about.html")

@app.route("/support/", methods=["GET"])
def support():
    return render_template("support.html")

@app.route("/register/", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/login/", methods=["GET"])
def login():
    return render_template("login.html")
