from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import json

app = Flask(__name__)
app.secret_key = "tjp-cinema-secret-2026"

# ========== PASTE YOUR SUPABASE KEYS HERE ==========
SUPABASE_URL = "https://dkrouadnjzwztcsytlff.supabase.co/rest/v1/"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRrcm91YWRuanp3enRjc3l0bGZmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgwMDQ2MzEsImV4cCI6MjEwMzU4MDYzMX0.pv24V4QMbvrtf8KvO8jWh6ZHQnWSaFYR0XhenpixO5Q"
# ==================================================

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

def initialize_seats_if_needed():
    """Create all seats in database if they don't exist"""
    result = supabase.table("seats").select("id").limit(1).execute()
    if not result.data:
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
        # Insert in batches
        for i in range(0, len(seats_to_insert), 500):
            supabase.table("seats").insert(seats_to_insert[i:i+500]).execute()

def get_seats_for_show(movie, time):
    show_key = get_show_key(movie, time)
    result = supabase.table("seats").select("row, col, is_booked").eq("show_key", show_key).execute()
    
    seats = [[False for _ in range(COLS)] for _ in range(ROWS)]
    for item in result.data:
        seats[item["row"]][item["col"]] = item["is_booked"]
    return seats

def get_all_shows():
    shows = []
    for movie in movie_list:
        for time in times:
            seats = get_seats_for_show(movie, time)
            shows.append({
                "movie": movie,
                "time": time,
                "seats": seats
            })
    return shows

@app.route("/")
def index():
    shows = get_all_shows()
    return render_template("index.html", shows=shows)

@app.route("/seats/<int:show_id>")
def seats(show_id):
    shows = get_all_shows()
    if show_id < 0 or show_id >= len(shows):
        flash("Invalid show")
        return redirect(url_for("index"))
    
    show = shows[show_id]
    return render_template("seats.html", show=show, show_id=show_id, rows=ROWS, cols=COLS)

@app.route("/book", methods=["POST"])
def book():
    show_id = int(request.form.get("show_id"))
    name = request.form.get("name", "").strip()
    age = request.form.get("age", "0")
    selected_seats = request.form.getlist("seats")

    shows = get_all_shows()
    if show_id < 0 or show_id >= len(shows):
        flash("Invalid show")
        return redirect(url_for("index"))

    show = shows[show_id]

    if not name or not selected_seats:
        flash("Please enter name and select seats")
        return redirect(url_for("seats", show_id=show_id))

    try:
        age = int(age)
        if age < 1 or age > 120:
            raise ValueError
    except:
        flash("Invalid age")
        return redirect(url_for("seats", show_id=show_id))

    ticket_price = 650.0 if "IMAX" in show["movie"] else 250.0
    sel_rows = []
    sel_cols = []

    for seat in selected_seats:
        row_char = seat[0]
        col = int(seat[1:]) - 1
        row = ord(row_char) - 65

        if show["seats"][row][col]:
            flash(f"Seat {seat} already booked")
            return redirect(url_for("seats", show_id=show_id))

        sel_rows.append(row)
        sel_cols.append(col)

    # Mark seats as booked in database
    show_key = get_show_key(show["movie"], show["time"])
    for r, c in zip(sel_rows, sel_cols):
        supabase.table("seats").update({"is_booked": True}).eq("show_key", show_key).eq("row", r).eq("col", c).execute()

    ticket_total = len(sel_rows) * ticket_price

    session["booking"] = {
        "name": name,
        "age": age,
        "rows": sel_rows,
        "cols": sel_cols,
        "ticket_total": ticket_total,
        "movie": show["movie"],
        "show_time": show["time"]
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
                name_food, price = menu[key]
                foods.append({"name": name_food, "quantity": qty, "price": price})
                food_total += price * qty

        data = session["booking"]
        
        # Generate ticket ID
        result = supabase.table("bookings").select("id").order("id", desc=True).limit(1).execute()
        next_id = 1001
        if result.data:
            next_id = 1001 + result.data[0]["id"]

        ticket_id = f"TJP{next_id}"

        # Save booking to database
        seats_str = ", ".join([f"{chr(65+r)}{c+1}" for r, c in zip(data["rows"], data["cols"])])
        foods_str = json.dumps(foods)

        supabase.table("bookings").insert({
            "ticket_id": ticket_id,
            "name": data["name"],
            "age": data["age"],
            "movie": data["movie"],
            "show_time": data["show_time"],
            "seats": seats_str,
            "ticket_total": data["ticket_total"],
            "food_total": food_total,
            "total_price": data["ticket_total"] + food_total,
            "foods": foods_str
        }).execute()

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
    return render_template("confirmation.html", b=b)

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

# Initialize seats when app starts
initialize_seats_if_needed()

if __name__ == "__main__":
    app.run(debug=True)
