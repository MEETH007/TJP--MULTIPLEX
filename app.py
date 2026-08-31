from flask import Flask
from supabase import create_client
import os

app = Flask(__name__)

# ========== PASTE YOUR REAL KEYS HERE ==========
SUPABASE_URL = "https://dkrouadnjzwztcsytlff.supabase.co"
SUPABASE_KEY = "sb_publishable_IiaYKeKYqP01AtY3g-thrw_K0xTdewa"
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
