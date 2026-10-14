from flask import Flask


app = Flask("Ravanshenasi Online")

@app.route("/", methods=["GET"])
def home():
    return "This is a test"