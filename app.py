from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "tjp-cinema-secret-2026"

ROWS = 16
COLS = 34

movie_list = [
    "Odyssey (IMAX)",
    "Avengers Doomsday (Pre booking)",
    "Spider-Man: BRAND NEW DAY",
    "Dune: Part THREE (IMAX) (Pre booking)"
]

times = ["10:00 AM", "01:30 PM", "04:00 PM", "07:30 PM"]

shows = []
bookings = []
ticket_counter = 1001

class Show:
    def __init__(self, movie, time):
        self.movie = movie
        self.time = time
        self.seats = [[False for _ in range(COLS)] for _ in range(ROWS)]

class FoodItem:
    def __init__(self, name, quantity, price):
        self.name = name
        self.quantity = quantity
        self.price = price

class Booking:
    def __init__(self):
        self.ticket_id = ""
        self.name = ""
        self.age = 0
        self.movie = ""
        self.show_time = ""
        self.rows = []
        self.cols = []
        self.foods = []
        self.ticket_total = 0.0
        self.food_total = 0.0
        self.total_price = 0.0

def initialize_shows():
    global shows
    shows = []
    for movie in movie_list:
        for time in times:
            shows.append(Show(movie, time))

initialize_shows()

def generate_ticket_id():
    global ticket_counter
    ticket_id = f"TJP{ticket_counter}"
    ticket_counter += 1
    return ticket_id

@app.route("/")
def index():
    return render_template("index.html", shows=shows)

@app.route("/seats/<int:show_id>")
def seats(show_id):
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

    show = shows[show_id]
    ticket_price = 650.0 if "IMAX" in show.movie else 250.0

    sel_rows = []
    sel_cols = []

    for seat in selected_seats:
        row_char = seat[0]
        col = int(seat[1:]) - 1
        row = ord(row_char) - 65

        if show.seats[row][col]:
            flash(f"Seat {seat} already booked")
            return redirect(url_for("seats", show_id=show_id))

        sel_rows.append(row)
        sel_cols.append(col)

    for r, c in zip(sel_rows, sel_cols):
        show.seats[r][c] = True

    ticket_total = len(sel_rows) * ticket_price

    session["booking"] = {
        "name": name,
        "age": age,
        "rows": sel_rows,
        "cols": sel_cols,
        "ticket_total": ticket_total,
        "movie": show.movie,
        "show_time": show.time
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
                name, price = menu[key]
                foods.append(FoodItem(name, qty, price))
                food_total += price * qty

        data = session["booking"]
        b = Booking()
        b.ticket_id = generate_ticket_id()
        b.name = data["name"]
        b.age = data["age"]
        b.movie = data["movie"]
        b.show_time = data["show_time"]
        b.rows = data["rows"]
        b.cols = data["cols"]
        b.foods = foods
        b.ticket_total = data["ticket_total"]
        b.food_total = food_total
        b.total_price = b.ticket_total + food_total

        bookings.append(b)
        session.pop("booking", None)

        return redirect(url_for("confirmation", ticket_id=b.ticket_id))

    return render_template("food.html", menu=menu)

@app.route("/confirmation/<ticket_id>")
def confirmation(ticket_id):
    booking = next((b for b in bookings if b.ticket_id == ticket_id), None)
    if not booking:
        flash("Ticket not found")
        return redirect(url_for("index"))
    return render_template("confirmation.html", b=booking)

@app.route("/bookings")
def view_bookings():
    return render_template("bookings.html", bookings=bookings)

@app.route("/scan", methods=["GET", "POST"])
def scan():
    result = None
    if request.method == "POST":
        tid = request.form.get("ticket_id", "").strip().upper()
        result = next((b for b in bookings if b.ticket_id.upper() == tid), None)
    return render_template("scan.html", result=result)
@app.route("/admin", methods=["GET", "POST"])
def admin():
    # Simple password protection
    password = "tjp123"   # ← Change this password to whatever you want

    if request.method == "POST":
        entered = request.form.get("password", "")
        if entered == password:
            session["admin_logged_in"] = True
        else:
            flash("Wrong password!")
            return redirect(url_for("admin"))

    if not session.get("admin_logged_in"):
        return render_template("admin_login.html")

    total_revenue = sum(b.total_price for b in bookings)

    return render_template("admin.html", bookings=bookings, total_revenue=total_revenue)
if __name__ == "__main__":
    app.run(debug=True)
