import os
import json
from datetime import datetime
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "tjp-cinema-secret-2026")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL")
ADMIN_REPORT_EMAIL = os.environ.get("ADMIN_REPORT_EMAIL", BREVO_SENDER_EMAIL)

BOOKINGS_PASSWORD = os.environ.get("BOOKINGS_PASSWORD", "admin123")
ADMIN_RESET_PASSWORD = os.environ.get("ADMIN_RESET_PASSWORD", "reset123")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 10 Rows (A-J) x 15 Columns = 150 Seats per auditorium (Fast rendering)
ROWS = 10
COLS = 15
TOTAL_SEATS_PER_SHOW = ROWS * COLS

MOVIES = [
    {
        "id": 0,
        "title": "Odyssey (IMAX)",
        "screen": "Screen 1 • IMAX with Laser",
        "price": 650.0,
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/1/17/2001_A_Space_Odyssey_%281968%29_poster.jpg",
        "trailer_url": "https://www.youtube-nocookie.com/embed/f_bKjZeJBBI",
        "times": ["10:00 AM", "01:30 PM", "04:00 PM", "07:30 PM"]
    },
    {
        "id": 1,
        "title": "Avengers Doomsday (Pre booking)",
        "screen": "Screen 2 • Dolby Atmos 4K",
        "price": 350.0,
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/0/0d/Avengers_Endgame_poster.jpg",
        "trailer_url": "https://www.youtube-nocookie.com/embed/irVNGjRFZGk",
        "times": ["10:30 AM", "02:00 PM", "05:30 PM", "09:00 PM"]
    },
    {
        "id": 2,
        "title": "Spider-Man: BRAND NEW DAY",
        "screen": "Screen 3 • Prime 3D",
        "price": 300.0,
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/0/00/Spider-Man_No_Way_Home_poster.jpg",
        "trailer_url": "https://www.youtube-nocookie.com/embed/62bIsvRcPv0",
        "times": ["11:00 AM", "02:30 PM", "06:00 PM", "09:30 PM"]
    },
    {
        "id": 3,
        "title": "Dune: Part THREE (IMAX)",
        "screen": "Screen 1 • IMAX with Laser",
        "price": 650.0,
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/5/52/Dune_Part_Two_poster.jpeg",
        "trailer_url": "https://www.youtube-nocookie.com/embed/NdvqHc56lE0",
        "times": ["10:15 AM", "01:45 PM", "05:15 PM", "08:45 PM"]
    },
    {
        "id": 4,
        "title": "Avengers : Endgame Encore",
        "screen": "Screen 2 • Dolby Atmos 4K",
        "price": 250.0,
        "poster_url": "https://upload.wikimedia.org/wikipedia/en/0/0d/Avengers_Endgame_poster.jpg",
        "trailer_url": "https://www.youtube-nocookie.com/embed/L2NAh3CIdig",
        "times": ["11:30 AM", "03:00 PM", "06:30 PM", "10:00 PM"]
    }
]

def get_all_shows():
    shows = []
    idx = 0
    for movie in MOVIES:
        for t in movie["times"]:
            shows.append({
                "show_id": idx,
                "movie_id": movie["id"],
                "movie": movie["title"],
                "screen": movie["screen"],
                "price": movie["price"],
                "poster_url": movie["poster_url"],
                "time": t
            })
            idx += 1
    return shows

def get_booked_seats(movie_title, time):
    """Fetches already-booked seat strings for a specific show from the bookings table."""
    try:
        res = supabase.table("bookings").select("seats").eq("movie", movie_title).eq("show_time", time).execute()
        booked = set()
        if res.data:
            for item in res.data:
                raw_seats = item.get("seats", "")
                if raw_seats:
                    for s in raw_seats.split(","):
                        booked.add(s.strip())
        return booked
    except Exception as e:
        print("Error fetching booked seats:", e)
        return set()

@app.route("/")
def index():
    all_shows = get_all_shows()
    
    # Fast query to count confirmed tickets per show
    try:
        res = supabase.table("bookings").select("movie, show_time, seats").execute()
        booked_counts = {}
        for b in (res.data or []):
            key = f"{b.get('movie')}|{b.get('show_time')}"
            seats_in_booking = len(b.get("seats", "").split(",")) if b.get("seats") else 0
            booked_counts[key] = booked_counts.get(key, 0) + seats_in_booking
    except Exception as e:
        print("Booking count query failed:", e)
        booked_counts = {}

    grouped_movies = []
    for movie in MOVIES:
        movie_shows = []
        for s in all_shows:
            if s["movie_id"] == movie["id"]:
                key = f"{s['movie']}|{s['time']}"
                taken = booked_counts.get(key, 0)
                available = max(0, TOTAL_SEATS_PER_SHOW - taken)
                movie_shows.append({
                    "show_id": s["show_id"],
                    "time": s["time"],
                    "available": available
                })
        
        grouped_movies.append({
            "id": movie["id"],
            "title": movie["title"],
            "screen": movie["screen"],
            "price": movie["price"],
            "poster_url": movie["poster_url"],
            "trailer_url": movie["trailer_url"],
            "shows": movie_shows
        })

    return render_template("index.html", movies=grouped_movies)

@app.route("/seats/<int:show_id>")
def seats(show_id):
    all_shows = get_all_shows()
    if show_id < 0 or show_id >= len(all_shows):
        flash("Invalid show selected.")
        return redirect(url_for("index"))

    show_info = all_shows[show_id]
    booked_set = get_booked_seats(show_info["movie"], show_info["time"])

    # Build 10x15 matrix with fast set lookups
    row_chars = "ABCDEFGHIJ"
    seats_data = []
    for r in range(ROWS):
        row_list = []
        for c in range(COLS):
            seat_code = f"{row_chars[r]}{c+1}"
            row_list.append(seat_code in booked_set)
        seats_data.append(row_list)

    show = {
        "movie": show_info["movie"],
        "screen": show_info["screen"],
        "time": show_info["time"],
        "price": show_info["price"],
        "poster_url": show_info["poster_url"],
        "seats": seats_data
    }
    return render_template("seats.html", show=show, show_id=show_id, rows=ROWS, cols=COLS)

@app.route("/book", methods=["POST"])
def book():
    show_id = int(request.form.get("show_id"))
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    age = request.form.get("age", "0")
    selected_seats = request.form.getlist("seats")

    all_shows = get_all_shows()
    if show_id < 0 or show_id >= len(all_shows):
        flash("Invalid show")
        return redirect(url_for("index"))

    show_info = all_shows[show_id]

    if not name or not email or not selected_seats:
        flash("Please enter name, email, and choose your seats.")
        return redirect(url_for("seats", show_id=show_id))

    try:
        age = int(age)
        if age < 1 or age > 120:
            raise ValueError
    except:
        flash("Invalid age provided.")
        return redirect(url_for("seats", show_id=show_id))

    # Double booking protection check
    already_booked = get_booked_seats(show_info["movie"], show_info["time"])
    for seat in selected_seats:
        if seat in already_booked:
            flash(f"Seat {seat} was just booked by another customer! Please pick another.")
            return redirect(url_for("seats", show_id=show_id))

    ticket_total = len(selected_seats) * show_info["price"]

    session["booking"] = {
        "name": name,
        "email": email,
        "age": age,
        "seats": selected_seats,
        "ticket_total": ticket_total,
        "movie": show_info["movie"],
        "screen": show_info["screen"],
        "show_time": show_info["time"],
        "poster_url": show_info["poster_url"]
    }

    return redirect(url_for("food"))

@app.route("/food", methods=["GET", "POST"])
def food():
    if "booking" not in session:
        return redirect(url_for("index"))

    menu = {
        1: ("Popcorn (Regular)", 150),
        2: ("Popcorn (Large Tub)", 250),
        3: ("Soft Drink (500ml)", 120),
        4: ("Nachos with Warm Cheese", 200),
        5: ("Combo (Large Popcorn + 2 Drinks)", 350),
        6: ("Bottled Mineral Water", 50)
    }

    if request.method == "POST":
        foods = []
        food_total = 0.0

        for key in menu:
            qty = int(request.form.get(f"qty_{key}", 0) or 0)
            if qty > 0:
                fname, price = menu[key]
                foods.append({"name": fname, "quantity": qty, "price": price})
                food_total += price * qty

        data = session["booking"]

        result = supabase.table("bookings").select("id").order("id", desc=True).limit(1).execute()
        next_num = 1001
        if result.data:
            next_num = 1000 + result.data[0]["id"] + 1

        ticket_id = f"TJP{next_num}"
        seats_str = ", ".join(data["seats"])
        total_price = data["ticket_total"] + food_total

        # Save to database
        supabase.table("bookings").insert({
            "ticket_id": ticket_id,
            "name": data["name"],
            "age": data["age"],
            "movie": data["movie"],
            "show_time": data["show_time"],
            "seats": seats_str,
            "ticket_total": data["ticket_total"],
            "food_total": food_total,
            "total_price": total_price,
            "foods": json.dumps(foods)
        }).execute()

        # Send Brevo email with the poster image embedded
        try:
            email_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif; max-width: 600px; margin: auto; background:#11121d; color:#ffffff; border-radius:16px; overflow:hidden; border: 1px solid #333;">
                
                <!-- Email Banner with Poster Thumbnail -->
                <div style="background: linear-gradient(135deg, #1f1b3c, #0a081a); padding: 24px; text-align: center; border-bottom: 2px solid #ffcc00;">
                    <img src="{data.get('poster_url', '')}" alt="{data['movie']}" 
                         style="width: 140px; height: 190px; object-fit: cover; border-radius: 10px; box-shadow: 0 8px 24px rgba(0,0,0,0.6); margin-bottom: 14px; border: 2px solid #ffcc00;">
                    <h1 style="color: #ffcc00; margin: 0; font-size: 24px; letter-spacing: 1px;">{data['movie']}</h1>
                    <p style="color: #a0a0b2; margin: 6px 0 0; font-size: 14px;">{data.get('screen', 'Screen 1')} &bull; {data['show_time']}</p>
                </div>

                <div style="padding: 24px;">
                    <p style="font-size: 16px; margin-top: 0;">Hi <strong>{data['name']}</strong>,</p>
                    <p style="color: #cccccc; font-size: 14px; line-height: 1.5;">Your seats are confirmed! Present this ticket or scan the QR pass below at the gate scanner.</p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; color: #ddd;">
                        <tr><td style="padding: 10px 0; border-bottom: 1px solid #2a2a3a; color:#888;">Ticket Pass ID</td><td style="padding: 10px 0; border-bottom: 1px solid #2a2a3a; text-align:right; color:#ffcc00; font-weight:bold; font-size:16px;">{ticket_id}</td></tr>
                        <tr><td style="padding: 10px 0; border-bottom: 1px solid #2a2a3a; color:#888;">Allocated Seats</td><td style="padding: 10px 0; border-bottom: 1px solid #2a2a3a; text-align:right; color:#2ecc71; font-weight:bold;">{seats_str}</td></tr>
                        <tr><td style="padding: 10px 0; border-bottom: 1px solid #2a2a3a; color:#888;">Ticket Total</td><td style="padding: 10px 0; border-bottom: 1px solid #2a2a3a; text-align:right;">Rs. {data['ticket_total']}</td></tr>
                        <tr><td style="padding: 10px 0; border-bottom: 1px solid #2a2a3a; color:#888;">Food & Snacks</td><td style="padding: 10px 0; border-bottom: 1px solid #2a2a3a; text-align:right;">Rs. {food_total}</td></tr>
                        <tr><td style="padding: 12px 0 0; font-size:16px; font-weight:bold; color:#fff;">Total Paid</td><td style="padding: 12px 0 0; text-align:right; font-size:18px; font-weight:bold; color:#ffcc00;">Rs. {total_price}</td></tr>
                    </table>

                    <div style="text-align: center; margin: 25px 0; padding: 20px; background: rgba(255,255,255,0.04); border-radius: 12px;">
                        <p style="margin: 0 0 12px; font-size: 13px; color: #aaa; text-transform: uppercase; letter-spacing: 1px;">Entrance Turnstile QR Pass</p>
                        <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={ticket_id}" 
                             alt="QR Code" width="180" height="180" style="border: 8px solid #ffffff; border-radius: 12px; background: #ffffff;">
                    </div>

                    <p style="text-align:center; color:#777; font-size:12px; margin-bottom:0;">TJP Cinema &bull; Premium Cinematic Experience</p>
                </div>
            </div>
            """

            payload = {
                "sender": {"name": "TJP Cinema", "email": BREVO_SENDER_EMAIL},
                "to": [{"email": data["email"], "name": data["name"]}],
                "subject": f"🎟️ Ticket Confirmed: {ticket_id} - {data['movie']}",
                "htmlContent": email_html
            }

            headers = {
                "accept": "application/json",
                "api-key": BREVO_API_KEY,
                "content-type": "application/json"
            }

            requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers)
        except Exception as e:
            print("Email sending failed:", str(e))

        session.pop("booking", None)
        return redirect(url_for("confirmation", ticket_id=ticket_id))

    return render_template("food.html", menu=menu)

@app.route("/confirmation/<ticket_id>")
def confirmation(ticket_id):
    result = supabase.table("bookings").select("*").eq("ticket_id", ticket_id).execute()
    if not result.data:
        flash("Ticket not found")
        return redirect(url_for("index"))
    
    b = result.data[0]
    poster = ""
    for m in MOVIES:
        if m["title"] == b.get("movie"):
            poster = m["poster_url"]
            break

    return render_template("confirmation.html", b=b, poster_url=poster)

@app.route("/bookings", methods=["GET", "POST"])
def view_bookings():
    if session.get("bookings_logged_in"):
        result = supabase.table("bookings").select("*").order("id", desc=True).execute()
        return render_template("bookings.html", bookings=result.data)

    if request.method == "POST":
        entered = request.form.get("password", "")
        if entered == BOOKINGS_PASSWORD:
            session["bookings_logged_in"] = True
            return redirect(url_for("view_bookings"))
        else:
            flash("Wrong password!")
            return redirect(url_for("view_bookings"))

    return render_template("bookings_login.html")

@app.route("/scan", methods=["GET", "POST"])
def scan():
    result = None
    if request.method == "POST":
        tid = request.form.get("ticket_id", "").strip().upper()
        res = supabase.table("bookings").select("*").eq("ticket_id", tid).execute()
        if res.data:
            result = res.data[0]
    return render_template("scan.html", result=result)

@app.route("/admin/reset", methods=["GET", "POST"])
def admin_reset():
    if request.method == "POST":
        entered = request.form.get("password", "")
        if entered != ADMIN_RESET_PASSWORD:
            flash("Wrong password!")
            return redirect(url_for("admin_reset"))

        try:
            supabase.table("bookings").delete().neq("id", 0).execute()
            flash("All bookings have been cleared successfully!")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error resetting: {str(e)}")
            return redirect(url_for("admin_reset"))

    return render_template("admin_reset.html")

@app.route("/admin/send-report", methods=["POST"])
def send_daily_report():
    entered_key = request.form.get("admin_key", "")
    if entered_key != ADMIN_RESET_PASSWORD:
        flash("Unauthorized key for revenue report!")
        return redirect(url_for("view_bookings"))

    try:
        res = supabase.table("bookings").select("*").execute()
        all_bookings = res.data or []
        
        total_tickets = len(all_bookings)
        ticket_rev = sum(b.get("ticket_total", 0.0) for b in all_bookings)
        food_rev = sum(b.get("food_total", 0.0) for b in all_bookings)
        grand_total = sum(b.get("total_price", 0.0) for b in all_bookings)

        now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")

        report_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 550px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff; color: #1a202c;">
            <h2 style="color: #d97706; margin-top: 0;">📊 TJP Cinema — Operations Report</h2>
            <p style="color: #718096; font-size: 0.9rem;">Dispatched on: <strong>{now_str}</strong></p>
            <hr style="border: none; border-top: 1px solid #edf2f7; margin: 18px 0;">
            <p><strong>Total Confirmed Bookings:</strong> {total_tickets}</p>
            <p><strong>Ticket Box Office:</strong> Rs. {ticket_rev:,.2f}</p>
            <p><strong>Food & Beverage:</strong> Rs. {food_rev:,.2f}</p>
            <div style="background: #f0fdf4; border-left: 4px solid #16a34a; padding: 12px 16px; margin-top: 15px;">
                <h3 style="margin: 0; color: #16a34a;">Grand Revenue: Rs. {grand_total:,.2f}</h3>
            </div>
        </div>
        """

        payload = {
            "sender": {"name": "TJP Cinema Ops", "email": BREVO_SENDER_EMAIL},
            "to": [{"email": ADMIN_REPORT_EMAIL, "name": "Cinema Owner"}],
            "subject": f"📊 Daily Revenue Briefing — {now_str}",
            "htmlContent": report_html
        }

        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }

        requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers)
        flash("Daily revenue briefing dispatched to your email!")
    except Exception as e:
        flash(f"Failed to generate report: {str(e)}")

    return redirect(url_for("view_bookings"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
