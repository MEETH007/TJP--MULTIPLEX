from flask import Flask
import requests
import os

app = Flask(__name__)

@app.route("/")
def home():
    brevo_api_key = os.environ.get("BREVO_API_KEY")
    sender_email = os.environ.get("BREVO_SENDER_EMAIL")

    if not brevo_api_key:
        return "<h2 style='color:red;'>BREVO_API_KEY is missing in Environment Variables</h2>"

    if not sender_email:
        return "<h2 style='color:red;'>BREVO_SENDER_EMAIL is missing in Environment Variables</h2>"

    # Test payload
    payload = {
        "sender": {
            "name": "TJP Cinema Test",
            "email": sender_email
        },
        "to": [
            {
                "email": sender_email,  # sending to yourself for testing
                "name": "Test User"
            }
        ],
        "subject": "Brevo Test Email from TJP Cinema",
        "htmlContent": "<h2>This is a test email</h2><p>If you received this, Brevo is working correctly!</p>"
    }

    headers = {
        "accept": "application/json",
        "api-key": brevo_api_key,
        "content-type": "application/json"
    }

    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers=headers
        )

        if response.status_code in [200, 201]:
            return f"""
            <h2 style='color:green;'>Success! Email sent successfully.</h2>
            <p>Check your inbox: <strong>{sender_email}</strong></p>
            <pre>{response.text}</pre>
            """
        else:
            return f"""
            <h2 style='color:red;'>Brevo Error</h2>
            <p>Status Code: {response.status_code}</p>
            <pre>{response.text}</pre>
            """
    except Exception as e:
        return f"<h2 style='color:red;'>Error:</h2><pre>{str(e)}</pre>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
