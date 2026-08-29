from flask import Flask
from supabase import create_client
import os

app = Flask(__name__)

# ========== PASTE YOUR REAL KEYS HERE ==========
SUPABASE_URL = "https://dkrouadnjzwztcsytlff.supabase.co/rest/v1/"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRrcm91YWRuanp3enRjc3l0bGZmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgwMDQ2MzEsImV4cCI6MjEwMzU4MDYzMX0.pv24V4QMbvrtf8KvO8jWh6ZHQnWSaFYR0XhenpixO5Q"
# ==============================================

@app.route("/")
def home():
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Try to read from the bookings table
        result = supabase.table("bookings").select("*").limit(1).execute()
        
        return f"""
        <h1>Supabase Connection Successful!</h1>
        <p>Connected to Supabase correctly.</p>
        <p>Bookings table is accessible.</p>
        <pre>{result}</pre>
        """
    except Exception as e:
        return f"""
        <h1 style="color:red;">Error Connecting to Supabase</h1>
        <p><strong>Error Message:</strong></p>
        <pre style="background:#222; color:#fff; padding:15px;">{str(e)}</pre>
        """

if __name__ == "__main__":
    app.run(debug=True)
