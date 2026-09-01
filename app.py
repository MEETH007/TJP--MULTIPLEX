from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import resend
import json
import os

app = Flask(__name__)
app.secret_key = "tjp-cinema-secret-2026"

# ========== Your Supabase Keys ==========
SUPABASE_URL = "https://dkrouadnjzwztcsytlff.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRrcm91YWRuanp3enRjc3l0bGZmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgwMDQ2MzEsImV4cCI6MjEwMzU4MDYzMX0.pv24V4QMbvrtf8KvO8jWh6ZHQnWSaFYR0XhenpixO5Q"
# =======================================

# ========== Resend Email Key ==========
resend.api_key = os.environ.get("RESEND_API_KEY")   # ← Paste your Resend API key here
# =====================================

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ROWS = 16
COLS = 34

movie_list = [
    "Odyssey (IMAX)",
    "Avengers Doomsday (Pre booking)",
    "Spider-Man: BRAND NEW DAY",
    "Dune: Part THREE (IMAX) (Pre booking)"
]

times = ["10:00 AM", "01:30 PM", "04:00 PM", "07:30 PM"]

def get_show_key(movie, time):
    return f"{movie}|{time}"

def initialize_seats():
    try:
        result = supabase.table("seats").select("id").limit(1).execute()
        if result.data:
            return

        print("Initializing seats...")
        seats_to_insert = []
        for movie in movie_list:
            for time in times:
                show_key = get_show_key(movie, time)
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
        print("Seats initialized!")
    except Exception as e:
        print("Init error:", str(e))

def get_available_count(movie, time):
    show_key = get_show_key(movie, time)
    result = supabase.table("seats")\
        .select("id", count="exact")\
        .eq("show_key", show_key)\
        .eq("is_booked", False)\
        .execute()
    return result.count or 0

def get_seats_for_show(movie, time):
    show_key = get_show_key(movie, time)
    result = supabase.table("seats")\
        .select("row, col, is_booked")\
        .eq("show_key", show_key)\
        .execute()
    
    seats = [[False for _ in range(COLS)] for _ in range(ROWS)]
    for item in result.data:
        seats[item["row"]][item["col"]] = item["is_booked"]
    return seats

@app.route("/")
def index():
    shows = []
    for movie in movie_list:
        for time in times:
            available = get_available_count(movie, time)
            shows.append({
                "movie": movie,
                "time": time,
                "available": available
            })
    return render_template("index.html", shows=shows)

@app.route("/seats/<int:show_id>")
def seats(show_id):
    all_shows = []
    for movie in movie_list:
        for time in times:
            all_shows.append({"movie": movie, "time": time})

    if show_id < 0 or show_id >= len(all_shows):
        flash("Invalid show")
        return redirect(url_for("index"))

    show_info = all_shows[show_id]
    seats_data = get_seats_for_show(show_info["movie"], show_info["time"])

    show = {
        "movie": show_info["movie"],
        "time": show_info["time"],
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

    all_shows = []
    for movie in movie_list:
        for time in times:
            all_shows.append({"movie": movie, "time": time})

    if show_id < 0 or show_id >= len(all_shows):
        flash("Invalid show")
        return redirect(url_for("index"))

    show_info = all_shows[show_id]
    current_seats = get_seats_for_show(show_info["movie"], show_info["time"])

    if not name or not email or not selected_seats:
        flash("Please enter name, email and select seats")
        return redirect(url_for("seats", show_id=show_id))

    try:
        age = int(age)
        if age < 1 or age > 120:
            raise ValueError
    except:
        flash("Invalid age")
        return redirect(url_for("seats", show_id=show_id))

    ticket_price = 650.0 if "IMAX" in show_info["movie"] else 250.0
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

    # Mark seats as booked
    show_key = get_show_key(show_info["movie"], show_info["time"])
    for r, c in zip(sel_rows, sel_cols):
        supabase.table("seats").update({"is_booked": True})\
            .eq("show_key", show_key).eq("row", r).eq("col", c).execute()

    ticket_total = len(sel_rows) * ticket_price

    session["booking"] = {
        "name": name,
        "email": email,
        "age": age,
        "rows": sel_rows,
        "cols": sel_cols,
        "ticket_total": ticket_total,
        "movie": show_info["movie"],
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

        # Save booking to Supabase
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

        # ===== Send Email using Resend =====
        try:
            email_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
                <h2 style="color: #ffcc00;">TJP Cinema - Booking Confirmation</h2>
                <p>Dear {data['name']},</p>
                <p>Your ticket has been successfully booked!</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Ticket ID</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{ticket_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Movie</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{data['movie']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Show Time</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{data['show_time']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Seats</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{seats_str}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Total Paid</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">Rs. {total_price}</td>
                    </tr>
                </table>

                <p>Please show this email or the QR code at the entrance.</p>
                <p>Thank you for booking with <strong>TJP Cinema</strong>!</p>
            </div>
            """

            resend.Emails.send({
                "from": "TJP Cinema <onboarding@resend.dev>",
                "to": [data["email"]],
                "subject": f"Your Ticket - {ticket_id} | TJP Cinema",
                "html": email_html
            })
            print("Email sent successfully to", data["email"])
        except Exception as e:
            print("Email sending failed:", str(e))
        # ==================================

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

@app.route("/bookings")
def view_bookings():
    result = supabase.table("bookings").select("*").order("id", desc=True).execute()
    return render_template("bookings.html", bookings=result.data)

@app.route("/scan", methods=["GET", "POST"])
def scan():
    result = None
    if request.method == "POST":
        tid = request.form.get("ticket_id", "").strip().upper()
        res = supabase.table("bookings").select("*").eq("ticket_id", tid).execute()
        if res.data:
            result = res.data[0]
    return render_template("scan.html", result=result)

# Initialize seats
initialize_seats()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
