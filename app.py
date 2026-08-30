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
        result = supabase.table("bookings").select("*").limit(1).execute()
        
        return f"""
        <h1 style="color:green;">Supabase Connected Successfully!</h1>
        <p>Your database is working.</p>
        <p>Number of records found: {len(result.data)}</p>
        """
    except Exception as e:
        return f"""
        <h1 style="color:red;">Supabase Connection Failed</h1>
        <p><strong>Error:</strong></p>
        <pre style="background:#111; color:#fff; padding:15px; border-radius:8px;">{str(e)}</pre>
        """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
