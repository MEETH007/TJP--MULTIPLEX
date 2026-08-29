from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h1>Basic Flask is Working!</h1>
    <p>If you can see this, the basic app is running correctly on Render.</p>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
