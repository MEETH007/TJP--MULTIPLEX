import os
import uuid
import requests
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from supabase import create_client, Client
from google import genai
from google.genai import types

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Initialize GenAI Client using the Authorization Key
gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
gemini_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

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
    
def send_customer_ticket_email(to_email, customer_name, booking_data):
    """Sends a luxury cinema boarding pass with notch stubs, poster card, and scannable pass."""
    if not BREVO_API_KEY or not BREVO_SENDER_EMAIL or not to_email or "@" not in to_email:
        print("Skipping Brevo customer email: Missing API key or invalid recipient.")
        return False

    ticket_id = booking_data.get("ticket_id", "TJP-PASS")
    movie_title = booking_data.get("movie", "Cinema Screening")
    show_time = booking_data.get("show_time", "")
    raw_seats = booking_data.get("seats", "")
    ticket_total = float(booking_data.get("ticket_total", 0.0))
    food_total = float(booking_data.get("food_total", 0.0))
    grand_total = float(booking_data.get("total_price", ticket_total + food_total))

    # Match poster and screen from catalog
    poster_url = "https://images.weserv.nl/?url=www.impawards.com/2026/posters/avengers_doomsday_ver4.jpg"
    screen_info = "Screen 1 • Laser Presentation"
    for m in MOVIES:
        if m["title"].strip().lower() == movie_title.strip().lower():
            poster_url = m.get("poster_url", poster_url)
            screen_info = m.get("screen", screen_info)
            break

    # Build stylized seat chips
    seat_chips = []
    if isinstance(raw_seats, list):
        seat_list = raw_seats
    else:
        seat_list = [s.strip() for s in str(raw_seats).split(",") if s.strip()]

    for s in seat_list:
        seat_chips.append(
            f'<span style="display: inline-block; background: #1e293b; color: #ffcc00; border: 1px solid #ffcc00; font-weight: 700; font-size: 13px; padding: 3px 9px; border-radius: 6px; margin: 2px 3px 2px 0;">{s}</span>'
        )
    rendered_seats_html = "".join(seat_chips) or f'<strong style="color: #ffcc00;">{raw_seats}</strong>'

    # High-density Scannable Turnstile QR Code
    qr_url = f"https://quickchart.io/qr?text={ticket_id}&size=260&margin=1"

    ticket_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TJP Cinema VIP Ticket</title>
    </head>
    <body style="margin: 0; padding: 28px 12px; background-color: #07090e; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 540px; margin: auto; background-color: #0f1523; border-radius: 20px; overflow: hidden; border: 1px solid #1e293b; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.85);">
            
            <!-- HEADER BRANDING -->
            <tr>
                <td style="padding: 24px 28px 18px 28px; background: linear-gradient(180deg, #161f33 0%, #0f1523 100%);">
                    <table width="100%" border="0" cellpadding="0" cellspacing="0">
                        <tr>
                            <td>
                                <span style="font-size: 11px; font-weight: 800; letter-spacing: 2px; color: #ffcc00; text-transform: uppercase;">PREMIUM PASS</span>
                                <h1 style="margin: 2px 0 0 0; font-size: 24px; font-weight: 900; color: #ffffff; letter-spacing: 0.5px;">🎬 TJP CINEMA</h1>
                            </td>
                            <td align="right">
                                <span style="display: inline-block; background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.4); color: #22c55e; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 50px;">CONFIRMED</span>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>

            <!-- POSTER HERO WITH FILM INFO -->
            <tr>
                <td style="padding: 10px 28px 24px 28px;">
                    <table width="100%" border="0" cellpadding="0" cellspacing="0">
                        <tr>
                            <td width="120" valign="top">
                                <img src="{poster_url}" alt="{movie_title}" width="120" style="display: block; border-radius: 12px; box-shadow: 0 12px 24px rgba(0,0,0,0.6); border: 1px solid #2a3850; object-fit: cover;">
                            </td>
                            <td valign="middle" style="padding-left: 20px;">
                                <span style="background: rgba(255, 204, 0, 0.12); color: #ffcc00; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; display: inline-block; margin-bottom: 8px;">{screen_info}</span>
                                <h2 style="color: #ffffff; font-size: 20px; font-weight: 800; margin: 0 0 6px 0; line-height: 1.25;">{movie_title}</h2>
                                <p style="color: #94a3b8; font-size: 13px; margin: 0 0 4px 0;">🕒 Show: <strong style="color: #ffffff;">{show_time}</strong></p>
                                <p style="color: #94a3b8; font-size: 13px; margin: 0;">Guest: <strong style="color: #ffffff;">{customer_name}</strong></p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>

            <!-- STUB PERFORATION CUTOUT -->
            <tr>
                <td style="padding: 0; position: relative;">
                    <table width="100%" border="0" cellpadding="0" cellspacing="0">
                        <tr>
                            <td width="16" height="32" style="background-color: #07090e; border-top-right-radius: 16px; border-bottom-right-radius: 16px; border-right: 1px solid #1e293b;"></td>
                            <td style="border-bottom: 2px dashed #243046;"></td>
                            <td width="16" height="32" style="background-color: #07090e; border-top-left-radius: 16px; border-bottom-left-radius: 16px; border-left: 1px solid #1e293b;"></td>
                        </tr>
                    </table>
                </td>
            </tr>

            <!-- BOOKING SUMMARY MATRIX -->
            <tr>
                <td style="padding: 20px 28px 12px 28px;">
                    <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse: collapse; font-size: 13px;">
                        <tr style="border-bottom: 1px solid #182234;">
                            <td style="color: #64748b; font-weight: 600; padding-left: 0;">Ticket Pass Code</td>
                            <td align="right" style="color: #ffcc00; font-family: monospace; font-size: 15px; font-weight: 800; padding-right: 0;">{ticket_id}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #182234;">
                            <td style="color: #64748b; font-weight: 600; padding-left: 0;">Allocated Seat(s)</td>
                            <td align="right" style="padding-right: 0;">
                                {rendered_seats_html}
                            </td>
                        </tr>
                        <tr style="border-bottom: 1px solid #182234;">
                            <td style="color: #64748b; font-weight: 600; padding-left: 0;">Box Office Admission</td>
                            <td align="right" style="color: #cbd5e1; font-weight: 600; padding-right: 0;">Rs. {ticket_total:,.2f}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #182234;">
                            <td style="color: #64748b; font-weight: 600; padding-left: 0;">Pure Veg Concessions</td>
                            <td align="right" style="color: #cbd5e1; font-weight: 600; padding-right: 0;">Rs. {food_total:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="color: #ffffff; font-size: 15px; font-weight: 800; padding-left: 0; padding-top: 14px;">Total Amount Paid</td>
                            <td align="right" style="color: #22c55e; font-size: 19px; font-weight: 900; padding-right: 0; padding-top: 14px;">Rs. {grand_total:,.2f}</td>
                        </tr>
                    </table>
                </td>
            </tr>

            <!-- TURNSTILE SCANNER QR STUB -->
            <tr>
                <td align="center" style="padding: 12px 28px 28px 28px;">
                    <div style="background: linear-gradient(180deg, #090d16 0%, #0d121e 100%); border: 1px solid #202b3e; border-radius: 16px; padding: 22px 20px; max-width: 320px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);">
                        <span style="color: #94a3b8; font-size: 11px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; display: block; margin-bottom: 14px;">
                            TURNSTILE ADMISSION PASS
                        </span>
                        
                        <!-- QR Image with white scan buffer -->
                        <div style="background: #ffffff; padding: 12px; display: inline-block; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.4); line-height: 0;">
                            <img src="{qr_url}" alt="Ticket Turnstile QR" width="160" height="160" style="display: block; border: 0;">
                        </div>

                        <p style="color: #475569; font-size: 11px; margin: 12px 0 0 0;">
                            Scan directly from your screen at Turnstile Gate or Box Office Kiosk
                        </p>
                    </div>
                </td>
            </tr>

            <!-- FOOTER -->
            <tr>
                <td align="center" style="padding: 16px 24px 22px 24px; background-color: #0a0e17; border-top: 1px solid #172132;">
                    <p style="color: #475569; font-size: 11px; margin: 0;">
                        TJP Cinema Multiplex &bull; Screenings &bull; Pure Veg Dining Experience
                    </p>
                </td>
            </tr>
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

    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }

    try:
        res = requests.post("https://api.brevo.com/v3/smtp/email", json=payload, headers=headers, timeout=15)
        print("Brevo Ticket Email Status:", res.status_code, res.text)
        return res.status_code in [200, 201, 202]
    except Exception as e:
        print("Brevo Ticket Email Error (non-fatal):", e)
        return False
        
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

    # Pull user details directly from the food/concessions form
    customer_name = request.form.get("name", "").strip() or active_hold.get("guest_name", "Guest")
    customer_email = request.form.get("email", "").strip() or active_hold.get("guest_email", "")
    customer_age = request.form.get("age", "").strip() or active_hold.get("guest_age", "")

    try:
        food_total = float(request.form.get("food_total", 0.0))
    except (ValueError, TypeError):
        food_total = 0.0

    total_price = ticket_total + food_total

    # Final conflict check against already-confirmed bookings
    booked = get_booked_seats(movie, show_time)
    if any(s in booked for s in selected_seats):
        flash("One or more of your selected seats was already reserved by another customer.")
        return redirect(url_for("index"))

    ticket_id = f"TJP-{uuid.uuid4().hex[:8].upper()}"

    booking_payload = {
        "ticket_id": ticket_id,
        "name": customer_name,
        "phone": customer_email,   # Saved into contact column
        "email": customer_email,
        "movie": movie,
        "show_time": show_time,
        "seats": ",".join(selected_seats),
        "ticket_total": ticket_total,
        "food_total": food_total,
        "total_price": total_price,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # 1. Save to Supabase
    try:
        supabase.table("bookings").insert(booking_payload).execute()
    except Exception as e:
        print("Primary Supabase insert failed:", repr(e))
        try:
            fallback_payload = {
                "ticket_id": ticket_id,
                "name": customer_name,
                "phone": customer_email,
                "movie": movie,
                "show_time": show_time,
                "seats": ",".join(selected_seats),
                "total_price": total_price
            }
            supabase.table("bookings").insert(fallback_payload).execute()
        except Exception as e2:
            print("Fallback Supabase insert failed:", repr(e2))
            flash(f"Database error finalizing ticket: {str(e2)}")
            return redirect(url_for("index"))

    # 2. Release temporary locks
    try:
        supabase.table("seat_locks").delete()\
            .eq("movie", movie)\
            .eq("show_time", show_time)\
            .eq("session_id", user_sid)\
            .execute()
    except Exception as lock_err:
        print("Seat lock cleanup warning:", lock_err)

    # 3. Fire customer ticket pass via Brevo
    if customer_email:
        email_sent = send_customer_ticket_email(customer_email, customer_name, booking_payload)
        if email_sent:
            flash(f"Digital pass dispatched to {customer_email}!")

    # 4. Clear active session hold
    session.pop("active_hold", None)

    return render_template(
        "confirmation.html",
        booking=booking_payload,
        b=booking_payload
    )

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
    # Read strictly from environment without exposing plain-text fallbacks
    view_password = (os.environ.get("BOOKINGS_PASSWORD") or "").strip()
    reset_password = (os.environ.get("ADMIN_RESET_PASSWORD") or "").strip()

    if request.method == "POST":
        action = request.form.get("action", "authenticate")
        entered_pass = (
            request.form.get("admin_pass") 
            or request.form.get("password") 
            or request.form.get("passcode") 
            or ""
        ).strip()

        if action == "authenticate":
            # Compare directly against the environment variable
            if view_password and entered_pass == view_password:
                session["admin_logged_in"] = True
                flash("Admin ledger unlocked successfully!")
            else:
                session["admin_logged_in"] = False
                flash("Incorrect admin passcode.")
            return redirect(url_for("view_bookings"))

        elif action == "reset_bookings":
            # Allow reset only if authenticated or if wipe password matches environment
            authorized = (
                (reset_password and entered_pass == reset_password)
                or (session.get("admin_logged_in") and reset_password and entered_pass == reset_password)
                or (session.get("admin_logged_in") and not entered_pass)
            )
            if authorized:
                try:
                    supabase.table("bookings").delete().neq("ticket_id", "0").execute()
                    supabase.table("seat_locks").delete().neq("session_id", "0").execute()
                    flash("All booking records and seat holds have been reset.")
                except Exception as e:
                    print("Supabase wipe error:", e)
                    flash("Failed to wipe database records.")
            else:
                flash("Incorrect reset passcode.")
            return redirect(url_for("view_bookings"))

        elif action == "send_report":
            try:
                send_daily_revenue_report()
                flash("Daily revenue briefing dispatched to owner email!")
            except Exception as e:
                flash(f"Report error: {e}")
            return redirect(url_for("view_bookings"))

    # Fetch ledger records if unlocked
    all_bookings = []
    is_authenticated = session.get("admin_logged_in", False)
    if is_authenticated:
        try:
            res = supabase.table("bookings").select("*").order("created_at", desc=True).execute()
            all_bookings = res.data or []
        except Exception as e:
            print("Supabase fetch error:", e)
            all_bookings = []

    return render_template(
        "bookings.html",
        bookings=all_bookings,
        is_authenticated=is_authenticated
    )

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
@app.route("/api/ai-concierge", methods=["POST"])
def ai_concierge():
    data = request.get_json() or {}
    user_query = data.get("message", "").strip()

    if not user_query:
        return jsonify({"reply": "How can I assist your TJP Cinema experience today?"})

    if not gemini_client:
        return jsonify({"reply": "The AI Concierge is currently offline. Please book your tickets directly below!"})

    # Assemble live catalog
    movie_context = []
    for m in MOVIES:
        movie_context.append(
            f"- {m['title']} | Hall: {m['screen']} | Admission: Rs. {m['price']} | Showtimes: {', '.join(m['times'])} | Link: /select-seats?movie_id={m['id']}"
        )

    system_instruction = f"""
You are "CineBot", the ultra-luxury VIP Cinema Concierge for TJP Cinema multiplex.
Tone: Warm, courteous, cinema-savvy, concise, and refined.

LIVE MOVIES & REAL-TIME INVENTORY:
{chr(10).join(movie_context)}

FOOD & BEVERAGES:
100% Pure Vegetarian menu. Items include Gourmet Caramel Popcorn, Truffle Butter Salted Popcorn, Loaded Cheese & Jalapeño Nachos, Artisan Cold Coffee, and Sparkling Mocktails.

CINEMA POLICIES:
- Active 7-minute seat hold during selection.
- Laser 4K projection & Dolby Atmos audio.
- Digital Boarding Pass with turnstile QR code delivered instantly on screen and to email.

INSTRUCTIONS:
1. Recommend movies, timings, or snacks strictly based on the live inventory above.
2. Whenever recommending a movie or timing, ALWAYS provide an HTML link so the user can click directly to book. Example: <a href="/select-seats?movie_id=1&time=09:00%20PM" style="color: #f59e0b; font-weight: bold; text-decoration: underline;">Book Now →</a>
3. Keep answers tight and helpful (typically 2 to 4 sentences).
"""

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_query,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                max_output_tokens=300
            )
        )
        reply_text = response.text or "I'm ready to assist with movies, showtimes, and snacks!"
        return jsonify({"reply": reply_text})

    except Exception as e:
        print("Gemini Concierge Error:", repr(e))
        return jsonify({"reply": "Our projectionists are fine-tuning the system. Feel free to explore our showtimes below or ask again in a moment!"})
        
# -------------------------------------------------------------
# Server Entrypoint
# -------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
