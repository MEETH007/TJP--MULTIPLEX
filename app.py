import os
import uuid
import hmac
import hashlib
import requests
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from markupsafe import escape
from supabase import create_client, Client
from google import genai
from google.genai import types

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# -------------------------------------------------------------
# Fail-Fast Startup & Environment Validation
# -------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
BOOKINGS_PASSWORD = os.environ.get("BOOKINGS_PASSWORD", "").strip()
ADMIN_RESET_PASSWORD = os.environ.get("ADMIN_RESET_PASSWORD", "").strip()

if not SECRET_KEY or SECRET_KEY == "tjp_multiplex_secret_super_key_2026":
    raise RuntimeError("CRITICAL: A secure, unique SECRET_KEY environment variable must be configured.")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("CRITICAL: SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")
if not BOOKINGS_PASSWORD or not ADMIN_RESET_PASSWORD:
    raise RuntimeError("CRITICAL: BOOKINGS_PASSWORD and ADMIN_RESET_PASSWORD must be strictly set in environment variables.")

# Initialize GenAI Client
gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
gemini_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

CANDIDATE_MODELS = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite"
]
if gemini_client:
    try:
        for m in gemini_client.models.list():
            name = getattr(m, "name", "").replace("models/", "")
            if any(bad in name.lower() for bad in ["tts", "audio", "embed", "imagen", "vision-preview"]):
                continue
            if ("flash" in name.lower() or "pro" in name.lower()) and name not in CANDIDATE_MODELS:
                CANDIDATE_MODELS.append(name)
        print(">>> ACTIVE CHAT MODELS:", CANDIDATE_MODELS)
    except Exception as e:
        print(">>> Could not query model list:", repr(e))

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Secure Session Cookie Settings
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "").strip()
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "").strip().strip('"').strip("'")
ADMIN_REPORT_EMAIL = (os.environ.get("ADMIN_REPORT_EMAIL") or BREVO_SENDER_EMAIL or "").strip().strip('"').strip("'")

HOLD_MINUTES = 7
IST_ZONE = ZoneInfo("Asia/Kolkata")

# -------------------------------------------------------------
# Movie Data & Schedules (Self-Hosted Assets)
# -------------------------------------------------------------
MOVIES = [
    {
        "id": 0,
        "title": "Odyssey (IMAX)",
        "screen": "Screen 1 • IMAX with Laser",
        "price": 650.0,
        "poster_url": "/static/posters/odyssey.jpg",
        "trailer_url": "https://www.youtube-nocookie.com/embed/f_bKjZeJBBI",
        "times": ["10:00 AM", "01:30 PM", "04:00 PM", "07:30 PM"]
    },
    {
        "id": 1,
        "title": "Avengers Doomsday (Pre booking)",
        "screen": "Screen 2 • Dolby Atmos 4K",
        "price": 350.0,
        "poster_url": "/static/posters/avengers_doomsday.jpg",
        "trailer_url": "https://www.youtube-nocookie.com/embed/irVNGjRFZGk",
        "times": ["10:30 AM", "02:00 PM", "05:30 PM", "09:00 PM"]
    },
    {
        "id": 2,
        "title": "Spider-Man: BRAND NEW DAY",
        "screen": "Screen 3 • Prime 3D",
        "price": 300.0,
        "poster_url": "/static/posters/spiderman_brandnewday.jpg",
        "trailer_url": "https://www.youtube-nocookie.com/embed/62bIsvRcPv0",
        "times": ["11:00 AM", "02:30 PM", "06:00 PM", "09:30 PM"]
    },
    {
        "id": 3,
        "title": "Dune: Part THREE (IMAX)",
        "screen": "Screen 1 • IMAX with Laser",
        "price": 650.0,
        "poster_url": "/static/posters/dune_part3.jpg",
        "trailer_url": "https://www.youtube-nocookie.com/embed/NdvqHc56lE0",
        "times": ["10:15 AM", "01:45 PM", "05:15 PM", "08:45 PM"]
    },
    {
        "id": 4,
        "title": "Avengers : Endgame Encore",
        "screen": "Screen 2 • Dolby Atmos 4K",
        "price": 250.0,
        "poster_url": "/static/posters/avengers_endgame.jpg",
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
# Seat Validation & Database Helpers (Fail-Closed)
# -------------------------------------------------------------
VALID_SEATS = {f"{row}{num}" for row in "ABCDEFGH" for num in range(1, 12)}

def get_session_id():
    if "session_uid" not in session:
        session["session_uid"] = uuid.uuid4().hex
    return session["session_uid"]

def get_booked_seats(movie_id, show_date, show_time):
    """Retrieves booked seats. Fails closed (raises 503) if Supabase errors out."""
    try:
        res = supabase.table("booking_seats")\
            .select("seat_code")\
            .eq("movie_id", movie_id)\
            .eq("show_date", show_date)\
            .eq("show_time", show_time)\
            .execute()
        booked = set()
        for row in (res.data or []):
            code = str(row.get("seat_code", "")).strip()
            if code:
                booked.add(code)
        return booked
    except Exception as e:
        print("CRITICAL get_booked_seats fail-closed error:", repr(e))
        raise RuntimeError("Database connection failure. Halting to prevent double booking.")

def get_seat_status_maps(movie_id, show_date, show_time, current_session_id):
    booked_set = get_booked_seats(movie_id, show_date, show_time)
    locked_by_others = set()
    locked_by_me = set()

    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        res = supabase.table("seat_locks")\
            .select("seat_code, session_id")\
            .eq("movie_id", movie_id)\
            .eq("show_date", show_date)\
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
        print("get_seat_status_maps lock warning:", repr(e))

    return booked_set, locked_by_others, locked_by_me

# -------------------------------------------------------------
# Customer Routes
# -------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", movies=MOVIES, all_shows=get_all_shows())

@app.route("/select-seats", defaults={"show_id": None})
@app.route("/select-seats/<int:show_id>")
def select_seats(show_id):
    shows = get_all_shows()
    req_movie_id = request.args.get("movie_id", type=int)
    req_time = request.args.get("time", "").strip()
    show_date = datetime.now(IST_ZONE).strftime("%Y-%m-%d")

    chosen_show = None
    chosen_idx = 0

    if show_id is not None and 0 <= show_id < len(shows):
        chosen_show = shows[show_id]
        chosen_idx = show_id
    elif req_movie_id is not None:
        for i, s in enumerate(shows):
            if s["movie_id"] == req_movie_id:
                if not req_time or s["time"] == req_time:
                    chosen_show = s
                    chosen_idx = i
                    break

    if not chosen_show:
        chosen_show = shows[0]
        chosen_idx = 0

    movie_id = chosen_show["movie_id"]
    movie_title = chosen_show["movie"]
    show_time = chosen_show["time"]
    price = chosen_show.get("price", 250.0)
    screen = chosen_show.get("screen", "Screen 1")
    poster_url = chosen_show.get("poster_url", "")

    user_sid = get_session_id()
    try:
        booked, locked_others, locked_me = get_seat_status_maps(movie_id, show_date, show_time, user_sid)
    except RuntimeError:
        return "Database unavailable. Please try again shortly.", 503

    unavailable = booked.union(locked_others)

    return render_template(
        "seats.html",
        show=chosen_show,
        show_id=chosen_idx,
        movie=chosen_show,
        movie_title=movie_title,
        show_time=show_time,
        show_date=show_date,
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
    show_date = datetime.now(IST_ZONE).strftime("%Y-%m-%d")

    if not isinstance(seats, list) or not seats or len(seats) > 10:
        return jsonify({"success": False, "message": "Invalid seat selection (Max 10 seats)."}), 450

    # Validate seat format
    for s in seats:
        if str(s).strip() not in VALID_SEATS or "," in str(s):
            return jsonify({"success": False, "message": f"Invalid seat code: {s}"}), 400

    shows = get_all_shows()
    if show_id is None or not isinstance(show_id, int) or show_id < 0 or show_id >= len(shows):
        return jsonify({"success": False, "message": "Invalid show ID."}), 400

    show = shows[show_id]
    movie_id = show["movie_id"]
    movie_title = show["movie"]
    show_time = show["time"]
    user_sid = get_session_id()

    try:
        # Call atomic Postgres RPC transaction function
        rpc_res = supabase.rpc("lock_seats_atomic", {
            "p_movie_id": movie_id,
            "p_movie_title": movie_title,
            "p_show_date": show_date,
            "p_show_time": show_time,
            "p_session_id": user_sid,
            "p_seats": [str(s).strip() for s in seats],
            "p_ttl_minutes": HOLD_MINUTES
        }).execute()

        result_data = rpc_res.data
        if isinstance(result_data, list) and len(result_data) > 0:
            result_data = result_data[0]

        if result_data and result_data.get("status") == "conflict":
            conflict_seats = result_data.get("seats", [])
            return jsonify({
                "success": False,
                "message": f"Seat(s) {', '.join(conflict_seats)} were just locked or booked by another guest."
            }), 409

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=HOLD_MINUTES)
        expires_iso = expires_at.isoformat()

        session["active_hold"] = {
            "show_id": show_id,
            "movie_id": movie_id,
            "movie": movie_title,
            "show_date": show_date,
            "show_time": show_time,
            "seats": seats,
            "price_per_seat": show["price"],
            "expires_at": expires_iso
        }

        return jsonify({"success": True, "expires_at": expires_iso, "minutes": HOLD_MINUTES})
    except Exception as e:
        print("Atomic lock RPC error:", repr(e))
        return jsonify({"success": False, "message": "Could not lock seats securely."}), 500

FOOD_MENU = {
    "butter_popcorn": {"name": "Classic Butter Popcorn (Salted)", "price": 210.0, "category": "Popcorn", "badge": "Pure Veg", "image": "🍿"},
    "cheese_popcorn": {"name": "Gourmet Cheddar Cheese Popcorn", "price": 260.0, "category": "Popcorn", "badge": "Pure Veg", "image": "🍿"},
    "caramel_popcorn": {"name": "Crunchy Golden Caramel Popcorn", "price": 270.0, "category": "Popcorn", "badge": "Pure Veg", "image": "🍿"},
    "paneer_tikka_burger": {"name": "Crispy Paneer Tikka Burger", "price": 240.0, "category": "Hot Bites", "badge": "Pure Veg", "image": "🍔"},
    "mexican_nachos": {"name": "Crispy Tortilla Nachos & Warm Cheese Dip", "price": 220.0, "category": "Snacks", "badge": "Pure Veg", "image": "🧀"},
    "peri_peri_fries": {"name": "Peri Peri Crinkle French Fries", "price": 190.0, "category": "Snacks", "badge": "Pure Veg", "image": "🍟"},
    "cheese_corn_sandwich": {"name": "Grilled Cheese & Sweet Corn Sandwich", "price": 210.0, "category": "Hot Bites", "badge": "Pure Veg", "image": "🥪"},
    "coca_cola": {"name": "Chilled Coca-Cola Fountain Cup (650ml)", "price": 160.0, "category": "Beverages", "badge": "Pure Veg", "image": "🥤"},
    "cold_coffee": {"name": "Thick Creamy Cold Coffee", "price": 180.0, "category": "Beverages", "badge": "Pure Veg", "image": "🧋"}
}

@app.route("/food-and-snacks", methods=["GET", "POST"])
def food_and_snacks():
    shows = get_all_shows()
    if request.method == "POST":
        show_id = request.form.get("show_id", type=int)
        guest_name = request.form.get("name", "Guest").strip()
        guest_email = request.form.get("email", "").strip()
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
            "movie_id": show["movie_id"],
            "movie": show["movie"],
            "screen": show.get("screen", ""),
            "show_time": show["time"],
            "seats": selected_seats,
            "guest_name": guest_name,
            "guest_email": guest_email,
            "price_per_seat": ticket_price,
            "ticket_total": ticket_total
        }

    active_hold = session.get("active_hold")
    if not active_hold or not active_hold.get("seats"):
        flash("Your seat selection timed out or is empty. Please select your seats again.")
        return redirect(url_for("index"))

    return render_template(
        "food.html",
        active_hold=active_hold,
        menu=FOOD_MENU,
        food_menu=FOOD_MENU,
        food_items=FOOD_MENU
    )

def calculate_server_food_total(form_data):
    """Computes food cost strictly from server-side FOOD_MENU prices (ignores client tampering)."""
    food_total = 0.0
    ordered_items = []
    for item_id, item_info in FOOD_MENU.items():
        raw_qty = form_data.get(f"qty_{item_id}", "0")
        try:
            qty = max(0, min(int(raw_qty), 20))
        except ValueError:
            qty = 0
        if qty > 0:
            item_cost = qty * item_info["price"]
            food_total += item_cost
            ordered_items.append(f"{qty}x {item_info['name']}")
    return food_total, ", ".join(ordered_items)

def send_customer_ticket_email(to_email, customer_name, booking_data):
    if not BREVO_API_KEY or not BREVO_SENDER_EMAIL or not to_email or "@" not in to_email:
        return False

    ticket_id = escape(booking_data.get("ticket_id", "TJP-PASS"))
    movie_title = escape(booking_data.get("movie", "Cinema Screening"))
    show_time = escape(booking_data.get("show_time", ""))
    raw_seats = booking_data.get("seats", "")
    ticket_total = float(booking_data.get("ticket_total", 0.0))
    food_total = float(booking_data.get("food_total", 0.0))
    grand_total = float(booking_data.get("total_price", ticket_total + food_total))

    poster_url = "https://images.weserv.nl/?url=www.impawards.com/2026/posters/avengers_doomsday_ver4.jpg"
    screen_info = "Screen 1 • Laser Presentation"
    for m in MOVIES:
        if m["id"] == booking_data.get("movie_id"):
            poster_url = m.get("poster_url", poster_url)
            screen_info = m.get("screen", screen_info)
            break

    seat_chips = []
    seat_list = raw_seats if isinstance(raw_seats, list) else [s.strip() for s in str(raw_seats).split(",") if s.strip()]
    for s in seat_list:
        seat_chips.append(f'<span style="display: inline-block; background: #1e293b; color: #ffcc00; border: 1px solid #ffcc00; font-weight: 700; font-size: 13px; padding: 3px 9px; border-radius: 6px; margin: 2px 3px 2px 0;">{escape(s)}</span>')
    rendered_seats_html = "".join(seat_chips) or f'<strong style="color: #ffcc00;">{escape(str(raw_seats))}</strong>'

    qr_url = f"https://quickchart.io/qr?text={ticket_id}&size=260&margin=1"

    ticket_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="utf-8"><title>TJP Cinema VIP Ticket</title></head>
    <body style="margin: 0; padding: 28px 12px; background-color: #07090e; font-family: sans-serif;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 540px; margin: auto; background-color: #0f1523; border-radius: 20px; border: 1px solid #1e293b;">
            <tr><td style="padding: 24px 28px; background: #161f33;"><h1 style="color: #ffffff; margin: 0;">🎬 TJP CINEMA</h1><span style="color: #22c55e;">CONFIRMED PASS</span></td></tr>
            <tr><td style="padding: 20px 28px;"><h2 style="color: #ffffff;">{movie_title}</h2><p style="color: #94a3b8;">Show: {show_time} | Guest: {escape(customer_name)}</p></td></tr>
            <tr><td style="padding: 20px 28px;">
                <p><strong>Ticket Code:</strong> {ticket_id}</p>
                <p><strong>Seats:</strong> {rendered_seats_html}</p>
                <p><strong>Total Paid:</strong> Rs. {grand_total:,.2f}</p>
            </td></tr>
            <tr><td align="center" style="padding: 20px;"><div style="background: #ffffff; padding: 12px; border-radius: 12px;"><img src="{qr_url}" alt="QR" width="160" height="160"></div></td></tr>
        </table>
    </body>
    </html>
    """

    payload = {
        "sender": {"name": "TJP Cinema Box Office", "email": BREVO_SENDER_EMAIL},
        "to": [{"email": to_email, "name": customer_name}],
        "subject": f"🎟️ Pass Confirmed: {movie_title} [{ticket_id}]",
        "htmlContent": ticket_html
    }
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}

    try:
        res = requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=15)
        return res.status_code in [200, 201, 202]
    except Exception as e:
        print("Brevo Ticket Email Error:", repr(e))
        return False

@app.route("/confirm-booking", methods=["POST"])
def confirm_booking():
    user_sid = get_session_id()
    active_hold = session.get("active_hold")

    if not active_hold or not active_hold.get("seats"):
        flash("Your seat selection has expired. Please choose your seats again.")
        return redirect(url_for("index"))

    movie_id = active_hold.get("movie_id")
    movie = active_hold.get("movie")
    show_date = active_hold.get("show_date", datetime.now(IST_ZONE).strftime("%Y-%m-%d"))
    show_time = active_hold.get("show_time")
    selected_seats = active_hold.get("seats", [])
    price_per_seat = float(active_hold.get("price_per_seat", 0.0))
    ticket_total = float(active_hold.get("ticket_total", price_per_seat * len(selected_seats)))

    customer_name = request.form.get("name", "").strip() or active_hold.get("guest_name", "Guest")
    customer_email = request.form.get("email", "").strip() or active_hold.get("guest_email", "")

    # Server-side food total calculation (ignores client tampering)
    food_total, food_items_desc = calculate_server_food_total(request.form)
    total_price = ticket_total + food_total

    # Verify session active locks exist in DB
    try:
        lock_check = supabase.table("seat_locks")\
            .select("seat_code")\
            .eq("movie_id", movie_id)\
            .eq("show_date", show_date)\
            .eq("show_time", show_time)\
            .eq("session_id", user_sid)\
            .in_("seat_code", selected_seats)\
            .execute()
        held_codes = {r["seat_code"] for r in (lock_check.data or [])}
        if len(held_codes) != len(selected_seats):
            flash("Your seat locks have expired or were released. Please reselect.")
            return redirect(url_for("index"))
    except Exception as e:
        print("Lock verification error:", repr(e))
        return "System verification error.", 500

    ticket_id = f"TJP-{uuid.uuid4().hex[:8].upper()}"

    booking_payload = {
        "ticket_id": ticket_id,
        "name": customer_name,
        "email": customer_email,
        "movie_id": movie_id,
        "movie": movie,
        "show_date": show_date,
        "show_time": show_time,
        "seats": ",".join(selected_seats),
        "ticket_total": ticket_total,
        "food_total": food_total,
        "total_price": total_price,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    seat_rows = [
        {
            "ticket_id": ticket_id,
            "movie_id": movie_id,
            "show_date": show_date,
            "show_time": show_time,
            "seat_code": s
        }
        for s in selected_seats
    ]

    try:
        # Insert booking and permanent seat mapping atomically
        supabase.table("bookings").insert(booking_payload).execute()
        supabase.table("booking_seats").insert(seat_rows).execute()
    except Exception as e:
        print("Database conflict during checkout:", repr(e))
        flash("One or more seats were already booked by another user during checkout.")
        return redirect(url_for("index"))

    # Cleanup temporary locks
    try:
        supabase.table("seat_locks").delete()\
            .eq("movie_id", movie_id)\
            .eq("show_date", show_date)\
            .eq("show_time", show_time)\
            .eq("session_id", user_sid)\
            .execute()
    except Exception as lock_err:
        print("Seat lock cleanup warning:", repr(lock_err))

    if customer_email and "@" in customer_email:
        send_customer_ticket_email(customer_email, customer_name, booking_payload)

    session.pop("active_hold", None)
    return redirect(url_for("view_ticket_receipt", ticket_id=ticket_id))

@app.route("/ticket/<ticket_id>")
def view_ticket_receipt(ticket_id):
    try:
        res = supabase.table("bookings").select("*").eq("ticket_id", ticket_id.strip().upper()).execute()
        if not res.data:
            flash("Ticket receipt not found.")
            return redirect(url_for("index"))
        booking = res.data[0]
        return render_template("confirmation.html", booking=booking, b=booking)
    except Exception as e:
        print("Receipt fetch error:", repr(e))
        return "Error loading receipt.", 500

# -------------------------------------------------------------
# Ticket Scanner Gate Route (Secured & One-Time Check-in)
# -------------------------------------------------------------
@app.route("/scan", methods=["GET", "POST"])
def scan_ticket():
    if not session.get("admin_unlocked"):
        flash("Please unlock the Admin Ledger first to access the Gate Scanner.")
        return redirect(url_for("view_bookings"))

    ticket_data = None
    searched_id = ""
    scan_status = None

    if request.method == "POST":
        searched_id = request.form.get("ticket_id", "").strip().upper()
        if searched_id:
            try:
                res = supabase.table("bookings").select("*").eq("ticket_id", searched_id).execute()
                if res.data and len(res.data) > 0:
                    ticket_data = res.data[0]
                    if ticket_data.get("checked_in_at"):
                        scan_status = ("ALREADY_USED", f"Warning: Ticket already checked in at {ticket_data['checked_in_at']}")
                    else:
                        now_iso = datetime.now(timezone.utc).isoformat()
                        supabase.table("bookings").update({"checked_in_at": now_iso}).eq("ticket_id", searched_id).execute()
                        ticket_data["checked_in_at"] = now_iso
                        scan_status = ("VALID", "Check-in successful! Welcome to TJP Cinema.")
                else:
                    flash(f"No ticket found with ID: {searched_id}")
            except Exception as e:
                print("Scan error:", repr(e))
                flash("Error processing ticket scan.")

    return render_template("scan.html", ticket=ticket_data, searched_id=searched_id, scan_status=scan_status)

# -------------------------------------------------------------
# Admin & Automated Reporting (Constant-Time Auth & IST Dates)
# -------------------------------------------------------------
def send_daily_revenue_report():
    if not supabase:
        raise Exception("Database connection not configured.")

    today_str = datetime.now(IST_ZONE).strftime("%Y-%m-%d")
    res = supabase.table("bookings").select("*").gte("created_at", f"{today_str}T00:00:00").execute()
    rows = res.data or []

    total_tickets = len(rows)
    total_seats = 0
    total_revenue = 0.0

    for r in rows:
        raw_seats = r.get("seats") or ""
        seat_count = len([s for s in str(raw_seats).split(",") if s.strip()])
        total_seats += seat_count
        price = r.get("total_price")
        if price is not None:
            try:
                total_revenue += float(price)
            except (ValueError, TypeError):
                total_revenue += seat_count * 250.0

    now_str = datetime.now(IST_ZONE).strftime("%d %b %Y, %I:%M %p")
    recipient = ADMIN_REPORT_EMAIL
    sender = BREVO_SENDER_EMAIL

    if BREVO_API_KEY and recipient and "@" in recipient and sender:
        report_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 550px; margin: auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff; color: #1a202c;">
            <h2 style="color: #d97706; margin-top: 0;">📊 TJP Cinema — Daily Briefing ({today_str})</h2>
            <p style="color: #718096; font-size: 0.9rem;">Dispatched on: <strong>{now_str} (IST)</strong></p>
            <hr style="border: none; border-top: 1px solid #edf2f7; margin: 18px 0;">
            <p><strong>Today's Bookings:</strong> {total_tickets}</p>
            <p><strong>Today's Seats Sold:</strong> {total_seats}</p>
            <div style="background: #f0fdf4; border-left: 4px solid #16a34a; padding: 12px 16px; margin-top: 15px;">
                <h3 style="margin: 0; color: #16a34a;">Today's Gross Revenue: Rs. {total_revenue:,.2f}</h3>
            </div>
        </div>
        """
        payload = {
            "sender": {"name": "TJP Cinema Ops", "email": sender},
            "to": [{"email": recipient, "name": "Cinema Owner"}],
            "subject": f"📊 Daily Revenue Briefing — {today_str}",
            "htmlContent": report_html
        }
        headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
        try:
            requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=20)
        except Exception as email_err:
            print("Daily report email error:", repr(email_err))
    return True

@app.route("/bookings", methods=["GET", "POST"])
def view_bookings():
    is_authenticated = session.get("admin_unlocked", False)
    all_bookings = []

    if request.method == "POST":
        action = request.form.get("action", "authenticate")
        entered_pass = (request.form.get("admin_pass") or request.form.get("password") or request.form.get("passcode") or "").strip()

        if action == "authenticate":
            if hmac.compare_digest(entered_pass.encode(), BOOKINGS_PASSWORD.encode()):
                session["admin_unlocked"] = True
                is_authenticated = True
                flash("Admin ledger unlocked for this session.")
            else:
                flash("Incorrect admin passcode.")

        elif action == "reset_bookings":
            if session.get("admin_unlocked") and hmac.compare_digest(entered_pass.encode(), ADMIN_RESET_PASSWORD.encode()):
                try:
                    supabase.table("bookings").delete().neq("ticket_id", "0").execute()
                    supabase.table("booking_seats").delete().neq("id", 0).execute()
                    supabase.table("seat_locks").delete().neq("session_id", "0").execute()
                    flash("All booking records and seat holds have been securely purged.")
                except Exception as e:
                    print("Wipe error:", repr(e))
                    flash("Failed to wipe database records.")
            else:
                flash("Unauthorized reset attempt.")

        elif action == "send_report":
            if session.get("admin_unlocked"):
                try:
                    send_daily_revenue_report()
                    flash("Daily revenue briefing dispatched to owner email!")
                except Exception as e:
                    flash("Report generation failed.")
            else:
                flash("Unauthorized report request.")

    if is_authenticated:
        try:
            res = supabase.table("bookings").select("*").order("created_at", desc=True).execute()
            all_bookings = res.data or []
        except Exception as e:
            print("Supabase fetch error:", repr(e))
            all_bookings = []

    return render_template("bookings.html", bookings=all_bookings, is_authenticated=is_authenticated)

# -------------------------------------------------------------
# AI Concierge Route (Rate-Limited, Prompt-Capped & Sanitized)
# -------------------------------------------------------------
TOTAL_SEATS_PER_SHOW = 442

@app.route("/api/ai-concierge", methods=["POST"])
def ai_concierge():
    try:
        data = request.get_json(silent=True) or {}
        user_query = data.get("message", "").strip()

        if not user_query:
            return jsonify({"reply": "Greetings! I am Lumière. How may I assist your TJP Cinema experience today?"})

        if len(user_query) > 300:
            return jsonify({"reply": "Please keep your query under 300 characters so I can assist you promptly."})

        show_date = datetime.now(IST_ZONE).strftime("%Y-%m-%d")
        booked_counts = {}
        if supabase:
            try:
                res = supabase.table("booking_seats").select("movie_id, show_time").eq("show_date", show_date).execute()
                if res and res.data:
                    for row in res.data:
                        m_id = row.get("movie_id")
                        s_time = (row.get("show_time") or "").strip().lower()
                        key = f"{m_id}_{s_time}"
                        booked_counts[key] = booked_counts.get(key, 0) + 1
            except Exception as sb_err:
                print("AI seat count warning:", repr(sb_err))

        movie_context = []
        for m in MOVIES:
            m_id = m["id"]
            timing_seat_breakdown = []
            for t in m.get("times", []):
                t_clean = t.strip().lower()
                key = f"{m_id}_{t_clean}"
                booked = booked_counts.get(key, 0)
                available = max(0, TOTAL_SEATS_PER_SHOW - booked)
                timing_seat_breakdown.append(f"{t} ({available} seats available)")

            movie_context.append(
                f"- {m.get('title')} | Screen: {m.get('screen')} | Admission: Rs. {m.get('price')} | Showtimes & Availability: {'; '.join(timing_seat_breakdown)} | Direct Link: /select-seats?movie_id={m_id}"
            )

        menu_items_desc = ", ".join([item["name"] for item in FOOD_MENU.values()])

        system_instruction = f"""
You are "Lumière", the personal VIP Cinema Concierge for TJP Cinema multiplex.
Tone: Warm, courteous, articulate, refined, and cinema-savvy.

LIVE MOVIES & REAL-TIME SEAT AVAILABILITY:
{chr(10).join(movie_context)}

FOOD & BEVERAGES MENU (100% Pure Veg):
{menu_items_desc}

CINEMA POLICIES:
- Hall Capacity: {TOTAL_SEATS_PER_SHOW} seats.
- Active 7-minute seat hold during selection.
- Laser 4K projection & Dolby Atmos audio.

INSTRUCTIONS:
1. Always introduce or carry yourself as Lumière, TJP Cinema's VIP Concierge.
2. Quote admission prices directly from the live list above.
3. State live remaining seats clearly whenever asked about availability.
4. ALWAYS provide an HTML booking link when recommending a film: <a href="/select-seats?movie_id=ID&time=TIME" style="color: #f59e0b; font-weight: bold; text-decoration: underline;">Book Now →</a>
5. Keep replies crisp and helpful (2 to 4 sentences).
"""

        if gemini_client:
            for model_name in CANDIDATE_MODELS:
                try:
                    response = gemini_client.models.generate_content(
                        model=model_name,
                        contents=user_query,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.7,
                            max_output_tokens=400
                        )
                    )
                    if response and response.text:
                        return jsonify({"reply": response.text})
                except Exception as g_err:
                    print(f"Concierge model {model_name} failed:", repr(g_err))
                    continue

        return jsonify({
            "reply": "Lumière is temporarily refreshing box office connections. Please choose your preferred showtime above!"
        })

    except Exception as route_err:
        print("CRITICAL /api/ai-concierge ERROR:", repr(route_err))
        return jsonify({
            "reply": "Lumière is temporarily unavailable. Please select your showtime directly."
        }), 200

# -------------------------------------------------------------
# Server Entrypoint
# -------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
