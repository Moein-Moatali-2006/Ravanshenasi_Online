from flask import Flask, render_template


app = Flask("Ravanshenasi Online")

@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")