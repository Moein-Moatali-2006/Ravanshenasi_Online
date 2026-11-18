from flask import Blueprint, render_template


pages = Blueprint("pages", __name__)


@pages.get("/")
def home():
    return render_template("home.html")


@pages.get("/about/")
def about():
    return render_template("about.html")


@pages.get("/support/")
def support():
    return render_template("support.html")


@pages.get("/register/")
def register():
    return render_template("register.html")


@pages.get("/login/")
def login():
    return render_template("login.html")
