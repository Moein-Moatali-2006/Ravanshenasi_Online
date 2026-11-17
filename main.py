from flask import Flask, render_template
from flask_smorest import Api

from database import create_db_and_tables
from config import Config

app = Flask("Ravanshenasi Online")
app.config.from_object(Config)

api = Api(app)
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
