import os
import uuid
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from supabase import create_client, Client

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tjp_multiplex_secret_super_key_2026")

# -------------------------------------------------------------
# Supabase Configuration
# -------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: SUPABASE_URL or SUPABASE_KEY is missing from environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------------------------------------
# Environment & Admin Configuration
# -------------------------------------------------------------
BOOKINGS_PASSWORD = os.environ.get("BOOKINGS_PASSWORD", "admin123").strip()
ADMIN_RESET_PASSWORD = os.environ.get("ADMIN_RESET_PASSWORD", "reset123").strip()
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "").strip()
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "").strip().strip('"').strip("'")
ADMIN_REPORT_EMAIL = (os.environ.get("ADMIN_REPORT_EMAIL") or BREVO_SENDER_EMAIL or "").strip().strip('"').strip("'")

HOLD_MINUTES = 7

# -------------------------------------------------------------
# Movie Data & Schedules
# -------------------------------------------------------------
MOVIES = [
    {
        "id": 0,
        "title": "Odyssey (IMAX)",
        "screen": "Screen 1 • IMAX with Laser",
        "price": 650.0,
        "poster_url": "https://dx35vtwkllhj9.cloudfront.net/universalstudios/the-odyssey/images/regions/ca/onesheet.jpg",
        "trailer_url": "https://www.youtube-nocookie.com/embed/f_bKjZeJBBI",
        "times": ["10:00 AM", "01:30 PM", "04:00 PM", "07:30 PM"]
    },
    {
        "id": 1,
        "title": "Avengers Doomsday (Pre booking)",
        "screen": "Screen 2 • Dolby Atmos 4K",
        "price": 350.0,
        "poster_url": "https://images.weserv.nl/?url=www.impawards.com/2026/posters/avengers_doomsday_ver4.jpg",
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
    show_list = []
    for m in MOVIES:
        for t in m["times"]:
            show_list.append({
                "movie_id": m["id"],
                "movie": m["title"],
                "screen": m["screen"],
                "price": m["price"],
                "time": t,
                "poster_url": m["poster_url"],
                "trailer_url": m["trailer_url"]
            })
    return show_list

# -------------------------------------------------------------
# Seat Locking & Availability Helpers
# -------------------------------------------------------------
def get_session_id():
    if "session_uid" not in session:
        session["session_uid"] = uuid.uuid4().hex
    return session["session_uid"]

def clean_expired_locks():
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        supabase.table("seat_locks").delete().lt("expires_at", now_iso).execute()
    except Exception as e:
        print("clean_expired_locks error:", e)

def get_booked_seats(movie, show_time):
    try:
        res = supabase.table("bookings")\
            .select("seats")\
            .eq("movie", movie)\
            .eq("show_time", show_time)\
            .execute()
        booked = set()
        for row in (res.data or []):
            raw = row.get("seats", "")
            if isinstance(raw, list):
                booked.update([str(s).strip() for s in raw])
            elif isinstance(raw, str):
                booked.update([s.strip() for s in raw.split(",") if s.strip()])
        return booked
    except Exception as e:
        print("get_booked_seats error:", e)
        return set()

def get_seat_status_maps(movie, show_time, current_session_id):
    clean_expired_locks()
    booked_set = get_booked_seats(movie, show_time)

    locked_by_others = set()
    locked_by_me = set()

    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        res = supabase.table("seat_locks")\
            .select("seat_code, session_id")\
            .eq("movie", movie)\
            .eq("show_time", show_time)\
            .gt("expires_at", now_iso)\
            .execute()

        for lock in (res.data or []):
            code = lock.get("seat_code", "").strip()
            if code in booked_set:
                continue
            if lock.get("session_id") == current_session_id:
                locked_by_me.add(code)
            else:
                locked_by_others.add(code)
    except Exception as e:
        print("get_seat_status_maps error:", e)

    return booked_set, locked_by_others, locked_by_me

# -------------------------------------------------------------
# Customer Routes
# -------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", movies=MOVIES, all_shows=get_all_shows())

# Multi-route adapter: prevents URL BuildErrors regardless of what parameters index.html passes
@app.route("/select-seats", defaults={"show_id": None})
@app.route("/select-seats/<int:show_id>")
def select_seats(show_id):
    shows = get_all_shows()
    
    # 1. Parse show selection from route param or query parameters
    req_movie_id = request.args.get("movie_id", type=int)
    req_time = request.args.get("time", "").strip()

    chosen_show = None
    chosen_idx = 0

    if show_id is not None and 0 <= show_id < len(shows):
        chosen_show = shows[show_id]
        chosen_idx = show_id
    elif req_movie_id is not None:
        # Match movie ID and time if provided
        for i, s in enumerate(shows):
            if s["movie_id"] == req_movie_id:
                if not req_time or s["time"] == req_time:
                    chosen_show = s
                    chosen_idx = i
                    break

    if not chosen_show:
        chosen_show = shows[0]
        chosen_idx = 0

    # 2. Extract movie information
    movie_title = chosen_show["movie"]
    show_time = chosen_show["time"]
    price = chosen_show.get("price", 250.0)
    screen = chosen_show.get("screen", "Screen 1")
    poster_url = chosen_show.get("poster_url", "")

    # 3. Retrieve locked and booked seats
    user_sid = get_session_id()
    booked, locked_others, locked_me = get_seat_status_maps(movie_title, show_time, user_sid)
    unavailable = booked.union(locked_others)

    # 4. Render template with both modern and legacy variable aliases
    return render_template(
        "seats.html",
        show=chosen_show,
        show_id=chosen_idx,
        movie=chosen_show,
        movie_title=movie_title,
        show_time=show_time,
        price=price,
        screen=screen,
        poster_url=poster_url,
        unavailable_seats=list(unavailable),
        my_locked_seats=list(locked_me),
        hold_minutes=HOLD_MINUTES
    )

@app.route("/api/lock-seats", methods=["POST"])
def api_lock_seats():
    data = request.get_json() or {}
    show_id = data.get("show_id")
    seats = data.get("seats", [])

    if not isinstance(seats, list) or not seats:
        return jsonify({"success": False, "message": "No seats selected."}), 400

    shows = get_all_shows()
    if show_id is None or show_id < 0 or show_id >= len(shows):
        return jsonify({"success": False, "message": "Invalid show ID."}), 400

    show = shows[show_id]
    movie = show["movie"]
    show_time = show["time"]
    user_sid = get_session_id()

    booked, locked_others, _ = get_seat_status_maps(movie, show_time, user_sid)
    conflict = [s for s in seats if s in booked or s in locked_others]

    if conflict:
        return jsonify({
            "success": False,
            "message": f"Seat(s) {', '.join(conflict)} were just held by another guest. Please pick other seats."
        }), 409

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=HOLD_MINUTES)
    expires_iso = expires_at.isoformat()

    try:
        supabase.table("seat_locks").delete()\
            .eq("movie", movie)\
            .eq("show_time", show_time)\
            .eq("session_id", user_sid)\
            .execute()

        rows = [
            {
                "movie": movie,
                "show_time": show_time,
                "seat_code": s.strip(),
                "session_id": user_sid,
                "expires_at": expires_iso
            }
            for s in seats
        ]
        supabase.table("seat_locks").insert(rows).execute()

        session["active_hold"] = {
            "movie": movie,
            "show_time": show_time,
            "seats": seats,
            "price_per_seat": show["price"],
            "expires_at": expires_iso
        }

        return jsonify({"success": True, "expires_at": expires_iso, "minutes": HOLD_MINUTES})
    except Exception as e:
        print("Failed to acquire lock:", e)
        return jsonify({"success": False, "message": "Could not lock seats. Please try again."}), 500
        
FOOD_MENU = {
    "butter_popcorn": {
        "name": "Classic Butter Popcorn (Salted)",
        "price": 210.0,
        "category": "Popcorn",
        "badge": "Pure Veg",
        "image": "🍿"
    },
    "cheese_popcorn": {
        "name": "Gourmet Cheddar Cheese Popcorn",
        "price": 260.0,
        "category": "Popcorn",
        "badge": "Pure Veg",
        "image": "🍿"
    },
    "caramel_popcorn": {
        "name": "Crunchy Golden Caramel Popcorn",
        "price": 270.0,
        "category": "Popcorn",
        "badge": "Pure Veg",
        "image": "🍿"
    },
    "paneer_tikka_burger": {
        "name": "Crispy Paneer Tikka Burger",
        "price": 240.0,
        "category": "Hot Bites",
        "badge": "Pure Veg",
        "image": "🍔"
    },
    "mexican_nachos": {
        "name": "Crispy Tortilla Nachos & Warm Cheese Dip",
        "price": 220.0,
        "category": "Snacks",
        "badge": "Pure Veg",
        "image": "🧀"
    },
    "peri_peri_fries": {
        "name": "Peri Peri Crinkle French Fries",
        "price": 190.0,
        "category": "Snacks",
        "badge": "Pure Veg",
        "image": "🍟"
    },
    "cheese_corn_sandwich": {
        "name": "Grilled Cheese & Sweet Corn Sandwich",
        "price": 210.0,
        "category": "Hot Bites",
        "badge": "Pure Veg",
        "image": "🥪"
    },
    "coca_cola": {
        "name": "Chilled Coca-Cola Fountain Cup (650ml)",
        "price": 160.0,
        "category": "Beverages",
        "badge": "Pure Veg",
        "image": "🥤"
    },
    "cold_coffee": {
        "name": "Thick Creamy Cold Coffee",
        "price": 180.0,
        "category": "Beverages",
        "badge": "Pure Veg",
        "image": "🧋"
    }
}

@app.route("/food-and-snacks", methods=["GET", "POST"])
def food_and_snacks():
    shows = get_all_shows()

    if request.method == "POST":
        show_id = request.form.get("show_id", type=int)
        guest_name = request.form.get("name", "Guest").strip()
        guest_email = request.form.get("email", "").strip()
        guest_age = request.form.get("age", "").strip()
        selected_seats = request.form.getlist("seats")

        if not selected_seats and request.form.get("seats"):
            selected_seats = [s.strip() for s in request.form.get("seats").split(",") if s.strip()]

        if show_id is not None and 0 <= show_id < len(shows):
            show = shows[show_id]
        else:
            show = shows[0]

        ticket_price = float(show.get("price", 250.0))
        ticket_total = len(selected_seats) * ticket_price

        session["active_hold"] = {
            "show_id": show_id,
            "movie": show["movie"],
            "screen": show.get("screen", ""),
            "show_time": show["time"],
            "seats": selected_seats,
            "guest_name": guest_name,
            "guest_email": guest_email,
            "guest_age": guest_age,
            "price_per_seat": ticket_price,
            "ticket_total": ticket_total
        }

    active_hold = session.get("active_hold")
    if not active_hold or not active_hold.get("seats"):
        flash("Your seat selection timed out or is empty. Please select your seats again.")
        return redirect(url_for("index"))

    # Pass menu, food_items, and active_hold so food.html renders properly
    return render_template(
        "food.html",
        active_hold=active_hold,
        menu=FOOD_MENU,
        food_menu=FOOD_MENU,
        food_items=FOOD_MENU
    )
    
@app.route("/confirm-booking", methods=["POST"])
def confirm_booking():
    user_sid = get_session_id()
    active_hold = session.get("active_hold")

    if not active_hold or not active_hold.get("seats"):
        flash("Your seat selection has expired. Please choose your seats again.")
        return redirect(url_for("index"))

    movie = active_hold.get("movie")
    show_time = active_hold.get("show_time")
    selected_seats = active_hold.get("seats", [])
    ticket_total = float(active_hold.get("ticket_total", 0.0))
    guest_name = active_hold.get("guest_name", "Guest")
    guest_email = active_hold.get("guest_email", "")

    # Calculate food total from form submission
    food_total = float(request.form.get("food_total", 0.0))
    total_price = ticket_total + food_total

    # Verify seats are still available in bookings table
    booked = get_booked_seats(movie, show_time)
    if any(s in booked for s in selected_seats):
        flash("One or more of your chosen seats was already confirmed by someone else.")
        return redirect(url_for("index"))

    ticket_id = f"TJP-{uuid.uuid4().hex[:8].upper()}"

    booking_payload = {
        "ticket_id": ticket_id,
        "name": guest_name,
        "phone": guest_email,  # Stores email/contact
        "movie": movie,
        "show_time": show_time,
        "seats": ",".join(selected_seats),
        "ticket_total": ticket_total,
        "food_total": food_total,
        "total_price": total_price,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        supabase.table("bookings").insert(booking_payload).execute()

        # Delete the temporary hold in seat_locks
        supabase.table("seat_locks").delete()\
            .eq("movie", movie)\
            .eq("show_time", show_time)\
            .eq("session_id", user_sid)\
            .execute()

        # Clear active hold session
        session.pop("active_hold", None)
        return render_template("confirmation.html", booking=booking_payload)
    except Exception as e:
        print("Booking confirmation failure:", e)
        flash("There was an issue finalizing your ticket. Please contact support.")
        return redirect(url_for("index"))

# -------------------------------------------------------------
# Ticket Scanner Gate Route
# -------------------------------------------------------------
@app.route("/scan", methods=["GET", "POST"])
def scan_ticket():
    ticket_data = None
    searched_id = ""

    if request.method == "POST":
        searched_id = request.form.get("ticket_id", "").strip().upper()
        if searched_id:
            try:
                res = supabase.table("bookings").select("*").eq("ticket_id", searched_id).execute()
                if res.data and len(res.data) > 0:
                    ticket_data = res.data[0]
                else:
                    flash(f"No ticket found with ID: {searched_id}")
            except Exception as e:
                flash(f"Error querying ticket: {e}")

    return render_template("scan.html", ticket=ticket_data, searched_id=searched_id)

# -------------------------------------------------------------
# Admin & Automated Reporting Routes
# -------------------------------------------------------------
@app.route("/bookings", methods=["GET", "POST"])
def view_bookings():
    is_authenticated = session.get("admin_logged_in", False)

    if request.method == "POST":
        entered_key = request.form.get("password", "").strip()
        if entered_key in [BOOKINGS_PASSWORD, ADMIN_RESET_PASSWORD]:
            session["admin_logged_in"] = True
            is_authenticated = True
        else:
            flash("Incorrect admin password!")

    all_bookings = []
    if is_authenticated:
        try:
            res = supabase.table("bookings").select("*").order("created_at", desc=True).execute()
            all_bookings = res.data or []
        except Exception as e:
            flash(f"Error loading bookings: {e}")

    return render_template("bookings.html", authenticated=is_authenticated, bookings=all_bookings)

@app.route("/admin/send-report", methods=["POST"])
def send_daily_report():
    entered_key = request.form.get("admin_key", "").strip()
    if entered_key not in [ADMIN_RESET_PASSWORD, BOOKINGS_PASSWORD]:
        flash("Unauthorized key for revenue report!")
        return redirect(url_for("view_bookings"))

    recipient = (os.environ.get("ADMIN_REPORT_EMAIL") or BREVO_SENDER_EMAIL or "").strip().strip('"').strip("'")
    sender = (BREVO_SENDER_EMAIL or "").strip().strip('"').strip("'")

    if not recipient or "@" not in recipient:
        flash(f"Error: Invalid recipient email '{recipient}'. Check ADMIN_REPORT_EMAIL in Render.")
        return redirect(url_for("view_bookings"))

    try:
        res = supabase.table("bookings").select("*").execute()
        all_bookings = res.data or []

        total_tickets = len(all_bookings)
        ticket_rev = sum(float(b.get("ticket_total") or 0.0) for b in all_bookings)
        food_rev = sum(float(b.get("food_total") or 0.0) for b in all_bookings)
        grand_total = sum(float(b.get("total_price") or 0.0) for b in all_bookings)

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
            "sender": {"name": "TJP Cinema Ops", "email": sender},
            "to": [{"email": recipient, "name": "Cinema Owner"}],
            "subject": f"📊 Daily Revenue Briefing — {now_str}",
            "htmlContent": report_html
        }

        headers = {
            "accept": "application/json",
            "api-key": (BREVO_API_KEY or "").strip(),
            "content-type": "application/json"
        }

        response = requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=25)
        print("Brevo Status:", response.status_code, response.text)

        if response.status_code in [200, 201, 202]:
            flash(f"Daily revenue briefing dispatched to {recipient}!")
        else:
            flash(f"Brevo rejected email: {response.text}")
    except Exception as e:
        print("Report failed:", str(e))
        flash(f"Failed to generate report: {str(e)}")

    return redirect(url_for("view_bookings"))

# -------------------------------------------------------------
# Server Entrypoint
# -------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
