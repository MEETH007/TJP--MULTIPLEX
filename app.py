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

# ========== Environment Keys ==========
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL")
ADMIN_REPORT_EMAIL = os.environ.get("ADMIN_REPORT_EMAIL", BREVO_SENDER_EMAIL)

BOOKINGS_PASSWORD = os.environ.get("BOOKINGS_PASSWORD", "admin123")
ADMIN_RESET_PASSWORD = os.environ.get("ADMIN_RESET_PASSWORD", "reset123")
# =======================================

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ROWS = 16
COLS = 34

MOVIES = [
    {
        "id": 0,
        "title": "Odyssey (IMAX)",
        "screen": "Screen 1 • IMAX with Laser",
        "price": 650.0,
        "poster_url": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600&auto=format&fit=crop&q=80",
        "trailer_url": "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "times": ["10:00 AM", "01:30 PM", "04:00 PM", "07:30 PM"]
    },
    {
        "id": 1,
        "title": "Avengers Doomsday (Pre booking)",
        "screen": "Screen 2 • Dolby Atmos 4K",
        "price": 350.0,
        "poster_url": "https://images.unsplash.com/photo-1635805737707-575885ab0820?w=600&auto=format&fit=crop&q=80",
        "trailer_url": "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "times": ["10:30 AM", "02:00 PM", "05:30 PM", "09:00 PM"]
    },
    {
        "id": 2,
        "title": "Spider-Man: BRAND NEW DAY",
        "screen": "Screen 3 • Prime 3D",
        "price": 300.0,
        "poster_url": "https://images.unsplash.com/photo-1604200213928-ba3cf4fc8436?w=600&auto=format&fit=crop&q=80",
        "trailer_url": "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "times": ["11:00 AM", "02:30 PM", "06:00 PM", "09:30 PM"]
    },
    {
        "id": 3,
        "title": "Dune: Part THREE (IMAX)",
        "screen": "Screen 1 • IMAX with Laser",
        "price": 650.0,
        "poster_url": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600&auto=format&fit=crop&q=80",
        "trailer_url": "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "times": ["10:15 AM", "01:45 PM", "05:15 PM", "08:45 PM"]
    },
    {
        "id": 4,
        "title": "Avengers : Endgame Encore",
        "screen": "Screen 2 • Dolby Atmos 4K",
        "price": 250.0,
        "poster_url": "https://images.unsplash.com/photo-1568876694728-451bbf694b83?w=600&auto=format&fit=crop&q=80",
        "trailer_url": "https://www.youtube.com/embed/TcMBFSGVi1c",
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
                "time": t
            })
            idx += 1
    return shows

def get_show_key(movie_title, time):
    return f"{movie_title}|{time}"

def initialize_seats():
    try:
        # Check per showtime so newly added movies get seats created automatically
        for movie in MOVIES:
            for t in movie["times"]:
                show_key = get_show_key(movie["title"], t)
                check = supabase.table("seats").select("id").eq("show_key", show_key).limit(1).execute()
                if not check.data:
                    print(f"Creating seats for: {show_key}")
                    seats_to_insert = []
                    for r in range(ROWS):
                        for c in range(COLS):
                            seats_to_insert.append({
                                "show_key": show_key,
                                "row": r,
                                "col": c,
                                "is_booked": False
                            })
                    for i in range(0, len(seats_to_insert), 400):
                        batch = seats_to_insert[i:i+400]
                        supabase.table("seats").insert(batch).execute()
        print("Seat verification complete.")
    except Exception as e:
        print("Init error:", str(e))

def get_available_count(movie_title, time):
    show_key = get_show_key(movie_title, time)
    result = supabase.table("seats")\
        .select("id", count="exact")\
        .eq("show_key", show_key)\
        .eq("is_booked", False)\
        .execute()
    return result.count or 0

def get_seats_for_show(movie_title, time):
    show_key = get_show_key(movie_title, time)
    result = supabase.table("seats")\
        .select("row, col, is_booked")\
        .eq("show_key", show_key)\
        .execute()
    
    seats = [[False for _ in range(COLS)] for _ in range(ROWS)]
    for item in result.data:
        seats[item["row"]][item["col"]] = item["is_booked"]
    return seats

# ================= ROUTES =================

@app.route("/")
def index():
    all_shows = get_all_shows()
    grouped_movies = []
    
    for movie in MOVIES:
        movie_shows = []
        for s in all_shows:
            if s["movie_id"] == movie["id"]:
                avail = get_available_count(s["movie"], s["time"])
                movie_shows.append({
                    "show_id": s["show_id"],
                    "time": s["time"],
                    "available": avail
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
    seats_data = get_seats_for_show(show_info["movie"], show_info["time"])

    show = {
        "movie": show_info["movie"],
        "screen": show_info["screen"],
        "time": show_info["time"],
        "price": show_info["price"],
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
    current_seats = get_seats_for_show(show_info["movie"], show_info["time"])

    if not name or not email or not selected_seats:
        flash("Please enter name, email, and select your seats.")
        return redirect(url_for("seats", show_id=show_id))

    try:
        age = int(age)
        if age < 1 or age > 120:
            raise ValueError
    except:
        flash("Invalid age provided.")
        return redirect(url_for("seats", show_id=show_id))

    sel_rows = []
    sel_cols = []
    for seat in selected_seats:
        row_char = seat[0]
        col = int(seat[1:]) - 1
        row = ord(row_char) - 65

        if current_seats[row][col]:
            flash(f"Seat {seat} is already booked!")
            return redirect(url_for("seats", show_id=show_id))

        sel_rows.append(row)
        sel_cols.append(col)

    show_key = get_show_key(show_info["movie"], show_info["time"])
    for r, c in zip(sel_rows, sel_cols):
        supabase.table("seats").update({"is_booked": True})\
            .eq("show_key", show_key).eq("row", r).eq("col", c).execute()

    ticket_total = len(sel_rows) * show_info["price"]

    session["booking"] = {
        "name": name,
        "email": email,
        "age": age,
        "rows": sel_rows,
        "cols": sel_cols,
        "ticket_total": ticket_total,
        "movie": show_info["movie"],
        "screen": show_info["screen"],
        "show_time": show_info["time"]
    }

    return redirect(url_for("food"))

@app.route("/food", methods=["GET", "POST"])
def food():
    if "booking" not in session:
        return redirect(url_for("index"))

    menu = {
        1: ("Popcorn (Small)", 150),
        2: ("Popcorn (Large)", 250),
        3: ("Soft Drink", 120),
        4: ("Nachos with Cheese", 200),
        5: ("Combo (Popcorn + Drink)", 320),
        6: ("Bottled Water", 50)
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
        seats_str = ", ".join([f"{chr(65 + r)}{c + 1}" for r, c in zip(data["rows"], data["cols"])])
        total_price = data["ticket_total"] + food_total

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

        try:
            email_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; background:#121218; color:#fff; padding:24px; border-radius:12px;">
                <h2 style="color: #ffcc00;">TJP Cinema - Booking Confirmation</h2>
                <p>Hello <strong>{data['name']}</strong>,</p>
                <p>Your tickets have been confirmed!</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0; color:#ddd;">
                    <tr><td style="padding: 8px; border-bottom: 1px solid #333;">Ticket ID</td><td style="padding: 8px; border-bottom: 1px solid #333; color:#ffcc00; font-weight:bold;">{ticket_id}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #333;">Movie</td><td style="padding: 8px; border-bottom: 1px solid #333;">{data['movie']}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #333;">Screen</td><td style="padding: 8px; border-bottom: 1px solid #333;">{data.get('screen', 'Screen 1')}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #333;">Show Time</td><td style="padding: 8px; border-bottom: 1px solid #333;">{data['show_time']}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #333;">Seats</td><td style="padding: 8px; border-bottom: 1px solid #333; color:#2ecc71; font-weight:bold;">{seats_str}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #333;">Total Paid</td><td style="padding: 8px; border-bottom: 1px solid #333; font-weight:bold; color:#ffcc00;">Rs. {total_price}</td></tr>
                </table>

                <div style="text-align: center; margin: 25px 0;">
                    <p style="margin-bottom:8px;">Scan this QR pass at the cinema entrance:</p>
                    <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={ticket_id}" 
                         alt="QR Code" width="200" height="200" style="border: 8px solid #fff; border-radius: 8px;">
                </div>
            </div>
            """

            payload = {
                "sender": {"name": "TJP Cinema", "email": BREVO_SENDER_EMAIL},
                "to": [{"email": data["email"], "name": data["name"]}],
                "subject": f"Tickets Confirmed: {ticket_id} - {data['movie']}",
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
    return render_template("confirmation.html", b=result.data[0])

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
            supabase.table("seats").update({"is_booked": False}).neq("id", 0).execute()
            flash("All bookings cleared and seats reset successfully!")
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

initialize_seats()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
