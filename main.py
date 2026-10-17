from flask import Flask, render_template


app = Flask("Ravanshenasi Online")

@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")


@app.route("/about", methods=["GET"])
def about():
    return render_template("about.html")