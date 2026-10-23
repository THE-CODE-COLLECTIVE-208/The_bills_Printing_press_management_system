"""Printing Shop Management System.

A Flask + SQLite web app for a small printing shop, built from the DCIT 216
Assignment 2 design. Three kinds of users:

* Customers  - self check-in, queue ticket, live order tracking + "ready" alert
* Attendants - live queue, record orders and payments, update status, search
* Managers   - everything attendants can do, plus sales dashboard, services
               and price list, and staff accounts

Run:  python app.py      then open http://127.0.0.1:5000
"""

import functools
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CURRENCY = "GH₵"
TS_FMT = "%Y-%m-%d %H:%M:%S"
STATUSES = ["Waiting", "In Progress", "Ready", "Completed"]
ACTIVE_STATUSES = ("Waiting", "In Progress", "Ready")
STATUS_TS = {"In Progress": "processing_at", "Ready": "ready_at",
             "Completed": "completed_at"}
PAYMENT_METHODS = ["Cash", "Mobile Money", "Card"]
STALE_MINUTES = 30  # remind staff about orders not updated for this long

DEFAULT_SERVICES = [
    ("Printing (B&W)", 1.00, "🖨️"),
    ("Colour Printing", 3.00, "🎨"),
    ("Photocopy", 0.50, "📄"),
    ("Lamination", 5.00, "🗂️"),
    ("Scanning", 2.00, "📠"),
    ("Binding", 10.00, "📚"),
]
# Demo accounts created on first run; see README.md.
DEFAULT_USERS = [
    ("attendant", "Ama Mensah", "attendant123", "attendant"),
    ("manager", "Shop Manager", "manager123", "manager"),
]


def hash_password(password):
    # PBKDF2 works on every Python build (macOS system Python lacks scrypt).
    return generate_password_hash(password, method="pbkdf2:sha256")


def _load_secret_key():
    path = os.path.join(BASE_DIR, ".secret_key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


app = Flask(__name__)
app.config.update(
    DATABASE=os.environ.get("PRINTSHOP_DB", os.path.join(BASE_DIR, "printshop.db")),
    SECRET_KEY=os.environ.get("PRINTSHOP_SECRET") or _load_secret_key(),
)


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    rows = get_db().execute(sql, args).fetchall()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def init_db():
    db = get_db()
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
        db.executescript(f.read())
    if not query("SELECT 1 FROM services LIMIT 1"):
        db.executemany("INSERT INTO services (name, unit_price, icon) VALUES (?, ?, ?)",
                       DEFAULT_SERVICES)
    if not query("SELECT 1 FROM users LIMIT 1"):
        db.executemany(
            "INSERT INTO users (username, full_name, password_hash, role) VALUES (?, ?, ?, ?)",
            [(u, n, hash_password(p), r) for u, n, p, r in DEFAULT_USERS])
    db.commit()


@app.cli.command("init-db")
def init_db_command():
    """Create the tables and demo data."""
    init_db()
    print("Database ready:", app.config["DATABASE"])


def now():
    return datetime.now().strftime(TS_FMT)


def today():
    return date.today().isoformat()


def minutes_since(ts):
    if not ts:
        return 0
    return int((datetime.now() - datetime.strptime(ts, TS_FMT)).total_seconds() // 60)


def clean_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    return digits or None


# --------------------------------------------------------------------------
# Auth, CSRF and template helpers
# --------------------------------------------------------------------------

@app.before_request
def before_request():
    g.user = None
    if session.get("user_id"):
        g.user = query("SELECT * FROM users WHERE id = ? AND active = 1",
                       (session["user_id"],), one=True)
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method == "POST" and request.form.get("csrf") != session["csrf"]:
        abort(400, "Your form expired. Go back, refresh the page and try again.")


def login_required(*roles):
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login", next=request.path))
            if roles and g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


staff_required = login_required("attendant", "manager")
manager_required = login_required("manager")


@app.context_processor
def inject_globals():
    return {"user": g.get("user"),
            "STATUSES": STATUSES, "PAYMENT_METHODS": PAYMENT_METHODS,
            "minutes_since": minutes_since, "STALE_MINUTES": STALE_MINUTES,
            "today_str": today()}


@app.template_global()
def csrf_token():
    # A global (not a context variable) so imported macros can use it too.
    return session.get("csrf", "")


@app.template_filter("money")
def money(value):
    return f"{CURRENCY} {float(value or 0):,.2f}"


@app.template_filter("hm")
def hm(ts):
    return ts[11:16] if ts else ""


@app.template_filter("qno")
def qno(n):
    return f"{n:03d}"


@app.template_filter("slug")
def slug(status):
    return status.lower().replace(" ", "-")


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
def http_error(err):
    return render_template("error.html", error=err), err.code


# --------------------------------------------------------------------------
# Order helpers
# --------------------------------------------------------------------------

ORDER_SELECT = """
    SELECT o.*, c.name AS customer_name, c.phone AS customer_phone,
           s.name AS service_name, s.icon AS service_icon,
           u.full_name AS created_by_name,
           COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.order_id = o.id), 0) AS paid
    FROM orders o
    JOIN customers c ON c.id = o.customer_id
    JOIN services s ON s.id = o.service_id
    LEFT JOIN users u ON u.id = o.created_by
"""


def get_order(order_id):
    order = query(ORDER_SELECT + " WHERE o.id = ?", (order_id,), one=True)
    if order is None:
        abort(404)
    return order


def balance(order):
    return round(order["amount"] - order["paid"], 2)


app.jinja_env.globals["balance"] = balance


def find_or_create_customer(name, phone):
    phone = clean_phone(phone)
    if phone:
        existing = query("SELECT id FROM customers WHERE phone = ?", (phone,), one=True)
        if existing:
            execute("UPDATE customers SET name = ? WHERE id = ?", (name, existing["id"]))
            return existing["id"]
    return execute("INSERT INTO customers (name, phone, created_at) VALUES (?, ?, ?)",
                   (name, phone, now()))


def create_order(customer_id, service_id, quantity, notes, source, user_id=None):
    service = query("SELECT * FROM services WHERE id = ? AND active = 1",
                    (service_id,), one=True)
    if service is None:
        raise ValueError("Please choose a service.")
    db = get_db()
    ts = now()
    for _ in range(5):  # retry if two orders grab the same queue number
        queue_no = query("SELECT COALESCE(MAX(queue_no), 0) + 1 AS n FROM orders "
                         "WHERE queue_date = ?", (today(),), one=True)["n"]
        try:
            cur = db.execute(
                """INSERT INTO orders (queue_date, queue_no, track_code, customer_id,
                       service_id, quantity, unit_price, amount, notes, status, source,
                       created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Waiting', ?, ?, ?, ?)""",
                (today(), queue_no, secrets.token_hex(3).upper(), customer_id, service_id,
                 quantity, service["unit_price"], round(service["unit_price"] * quantity, 2),
                 notes, source, user_id, ts, ts))
            db.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            db.rollback()
    raise RuntimeError("Could not allocate a queue number, please try again.")


def record_payment(order_id, amount, method, user_id):
    execute("INSERT INTO payments (order_id, amount, method, received_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)", (order_id, round(amount, 2), method, user_id, now()))
    execute("UPDATE orders SET updated_at = ? WHERE id = ?", (now(), order_id))


def set_status(order, target):
    """Move an order forward to `target`. Returns an error message or None."""
    if order["status"] == "Cancelled":
        return "This order was cancelled."
    if target not in STATUSES or STATUSES.index(target) <= STATUSES.index(order["status"]):
        return f"Order is already {order['status']}."
    if target == "Completed" and balance(order) > 0.004:
        return (f"Record the payment of {money(balance(order))} before completing "
                f"order {order['queue_no']:03d}.")
    ts = now()
    sets, args = ["status = ?", "updated_at = ?"], [target, ts]
    # Fill in timestamps for this step and any steps that were skipped.
    for step in STATUSES[STATUSES.index(order["status"]) + 1: STATUSES.index(target) + 1]:
        sets.append(f"{STATUS_TS[step]} = ?")
        args.append(ts)
    execute(f"UPDATE orders SET {', '.join(sets)} WHERE id = ?", (*args, order["id"]))
    return None


def parse_int(value, default=None, minimum=1):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n >= minimum else default


def parse_money(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Public pages: home, customer check-in, ticket, tracking
# --------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/checkin", methods=["GET", "POST"])
def checkin():
    services = query("SELECT * FROM services WHERE active = 1 ORDER BY id")
    form = request.form
    if request.method == "POST":
        name = form.get("name", "").strip()
        if not name:
            flash("Please enter your name.", "error")
        elif not parse_int(form.get("service_id")):
            flash("Please tap the service you need.", "error")
        else:
            try:
                customer_id = find_or_create_customer(name, form.get("phone"))
                order_id = create_order(customer_id, int(form["service_id"]), 1,
                                        form.get("notes", "").strip(), "Check-in")
            except ValueError as e:
                flash(str(e), "error")
            else:
                order = get_order(order_id)
                return redirect(url_for("ticket", code=order["track_code"]))
    return render_template("checkin.html", services=services, form=form)


def order_by_code(code):
    order = query(ORDER_SELECT + " WHERE o.track_code = ?", ((code or "").upper(),), one=True)
    if order is None:
        abort(404)
    return order


def people_ahead(order):
    return query("SELECT COUNT(*) AS n FROM orders WHERE queue_date = ? AND queue_no < ? "
                 "AND status IN ('Waiting', 'In Progress')",
                 (order["queue_date"], order["queue_no"]), one=True)["n"]


@app.route("/ticket/<code>")
def ticket(code):
    order = order_by_code(code)
    return render_template("ticket.html", order=order, ahead=people_ahead(order))


@app.route("/track", methods=["GET", "POST"])
def track_lookup():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        if query("SELECT 1 FROM orders WHERE track_code = ?", (code,), one=True):
            return redirect(url_for("track", code=code))
        flash("We couldn't find that tracking code. Check your ticket and try again.", "error")
    return render_template("track_lookup.html")


@app.route("/track/<code>")
def track(code):
    order = order_by_code(code)
    return render_template("track.html", order=order, ahead=people_ahead(order))


@app.route("/api/track/<code>")
def api_track(code):
    order = order_by_code(code)
    return jsonify(status=order["status"], queue_no=order["queue_no"],
                   ahead=people_ahead(order), updated_at=order["updated_at"])


@app.route("/display")
def display():
    """Public 'now serving' board for a TV or screen in the waiting area."""
    orders = query(ORDER_SELECT + " WHERE o.queue_date = ? AND o.status IN "
                   "('Waiting', 'In Progress', 'Ready') ORDER BY o.queue_no", (today(),))
    return render_template("display.html", orders=orders)


# --------------------------------------------------------------------------
# Staff login
# --------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = query("SELECT * FROM users WHERE username = ? AND active = 1",
                     (request.form.get("username", "").strip().lower(),), one=True)
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome, {user['full_name']}.", "success")
            nxt = request.args.get("next", "")
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(url_for("dashboard" if user["role"] == "manager" else "queue"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# --------------------------------------------------------------------------
# Attendant: queue, orders, payments
# --------------------------------------------------------------------------

@app.route("/queue")
@staff_required
def queue():
    tab = request.args.get("tab", "queue")
    if tab == "completed":
        orders = query(ORDER_SELECT + " WHERE o.queue_date = ? AND o.status IN "
                       "('Completed', 'Cancelled') ORDER BY o.queue_no DESC", (today(),))
    else:
        tab = "queue"
        orders = query(ORDER_SELECT + " WHERE o.status IN ('Waiting', 'In Progress', 'Ready') "
                       "ORDER BY o.queue_date, o.queue_no")
    active = query(ORDER_SELECT + " WHERE o.status IN ('Waiting', 'In Progress', 'Ready')")
    stale = [o for o in active
             if o["status"] != "Ready" and minutes_since(o["updated_at"]) >= STALE_MINUTES]
    ready_unpaid = [o for o in active if o["status"] == "Ready" and balance(o) > 0.004]
    counts = {s: sum(1 for o in active if o["status"] == s) for s in ACTIVE_STATUSES}
    counts["Completed"] = query("SELECT COUNT(*) AS n FROM orders WHERE queue_date = ? "
                                "AND status = 'Completed'", (today(),), one=True)["n"]
    return render_template("queue.html", orders=orders, tab=tab, stale=stale,
                           ready_unpaid=ready_unpaid, counts=counts)


@app.route("/orders")
@staff_required
def orders():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    where, args = [], []
    if q:
        like = f"%{q}%"
        where.append("(c.name LIKE ? OR c.phone LIKE ? OR o.track_code = ? OR s.name LIKE ? "
                     "OR o.notes LIKE ? OR printf('%03d', o.queue_no) = ?)")
        args += [like, f"%{clean_phone(q) or q}%", q.upper(), like, like, q.zfill(3)]
    if status in STATUSES + ["Cancelled"]:
        where.append("o.status = ?")
        args.append(status)
    if start:
        where.append("o.queue_date >= ?")
        args.append(start)
    if end:
        where.append("o.queue_date <= ?")
        args.append(end)
    sql = ORDER_SELECT + (" WHERE " + " AND ".join(where) if where else "")
    rows = query(sql + " ORDER BY o.queue_date DESC, o.queue_no DESC LIMIT 200", args)
    return render_template("orders.html", orders=rows, q=q, status=status,
                           start=start, end=end)


@app.route("/orders/new", methods=["GET", "POST"])
@staff_required
def order_new():
    services = query("SELECT * FROM services WHERE active = 1 ORDER BY id")
    form = request.form
    if request.method == "POST":
        name = form.get("name", "").strip()
        quantity = parse_int(form.get("quantity"))
        if not name:
            flash("Enter the customer's name.", "error")
        elif not quantity:
            flash("Quantity must be a whole number of at least 1.", "error")
        else:
            try:
                customer_id = find_or_create_customer(name, form.get("phone"))
                order_id = create_order(customer_id, parse_int(form.get("service_id")),
                                        quantity, form.get("notes", "").strip(),
                                        "Counter", g.user["id"])
            except ValueError as e:
                flash(str(e), "error")
            else:
                order = get_order(order_id)
                msg = f"Order {order['queue_no']:03d} saved for {name} ({money(order['amount'])})."
                if form.get("paid_now"):
                    method = form.get("method") if form.get("method") in PAYMENT_METHODS else "Cash"
                    record_payment(order_id, order["amount"], method, g.user["id"])
                    msg += f" Payment of {money(order['amount'])} recorded."
                flash(msg, "success")
                return redirect(url_for("order_detail", order_id=order_id))
    return render_template("order_new.html", services=services, form=form)


@app.route("/orders/<int:order_id>")
@staff_required
def order_detail(order_id):
    order = get_order(order_id)
    payments = query("SELECT p.*, u.full_name AS received_by_name FROM payments p "
                     "LEFT JOIN users u ON u.id = p.received_by WHERE p.order_id = ? "
                     "ORDER BY p.id", (order_id,))
    services = query("SELECT * FROM services WHERE active = 1 OR id = ? ORDER BY id",
                     (order["service_id"],))
    history = query(ORDER_SELECT + " WHERE o.customer_id = ? AND o.id != ? "
                    "ORDER BY o.id DESC LIMIT 5", (order["customer_id"], order_id))
    return render_template("order_detail.html", order=order, payments=payments,
                           services=services, history=history)


@app.route("/orders/<int:order_id>/status", methods=["POST"])
@staff_required
def order_status(order_id):
    order = get_order(order_id)
    error = set_status(order, request.form.get("status", ""))
    if error:
        flash(error, "error")
        if request.form.get("back") == "queue":
            return redirect(url_for("order_detail", order_id=order_id))
    else:
        flash(f"Order {order['queue_no']:03d} is now {request.form['status']}.", "success")
    if request.form.get("back") == "queue":
        return redirect(url_for("queue"))
    return redirect(url_for("order_detail", order_id=order_id))


@app.route("/orders/<int:order_id>/edit", methods=["POST"])
@staff_required
def order_edit(order_id):
    order = get_order(order_id)
    if order["status"] in ("Completed", "Cancelled"):
        flash("Completed or cancelled orders can't be changed.", "error")
        return redirect(url_for("order_detail", order_id=order_id))
    quantity = parse_int(request.form.get("quantity"))
    service_id = parse_int(request.form.get("service_id"))
    service = query("SELECT * FROM services WHERE id = ?", (service_id,), one=True)
    if not quantity or service is None:
        flash("Choose a service and a quantity of at least 1.", "error")
        return redirect(url_for("order_detail", order_id=order_id))
    unit_price = order["unit_price"] if service_id == order["service_id"] else service["unit_price"]
    amount = round(unit_price * quantity, 2)
    if amount < order["paid"] - 0.004:
        flash(f"The new total ({money(amount)}) is less than what has already been paid "
              f"({money(order['paid'])}).", "error")
        return redirect(url_for("order_detail", order_id=order_id))
    execute("UPDATE orders SET service_id = ?, quantity = ?, unit_price = ?, amount = ?, "
            "notes = ?, updated_at = ? WHERE id = ?",
            (service_id, quantity, unit_price, amount,
             request.form.get("notes", "").strip(), now(), order_id))
    flash(f"Order updated. New total: {money(amount)}.", "success")
    return redirect(url_for("order_detail", order_id=order_id))


@app.route("/orders/<int:order_id>/payment", methods=["POST"])
@staff_required
def order_payment(order_id):
    order = get_order(order_id)
    amount = parse_money(request.form.get("amount"))
    method = request.form.get("method")
    due = balance(order)
    if order["status"] == "Cancelled":
        flash("This order was cancelled.", "error")
    elif amount is None or amount <= 0:
        flash("Enter a payment amount greater than zero.", "error")
    elif amount > due + 0.004:
        flash(f"That is more than the balance due ({money(due)}).", "error")
    elif method not in PAYMENT_METHODS:
        flash("Choose how the customer paid.", "error")
    else:
        record_payment(order_id, amount, method, g.user["id"])
        left = round(due - amount, 2)
        flash(f"Payment of {money(amount)} ({method}) recorded. "
              + ("Order fully paid." if left <= 0.004 else f"Balance left: {money(left)}."),
              "success")
    return redirect(url_for("order_detail", order_id=order_id))


@app.route("/orders/<int:order_id>/cancel", methods=["POST"])
@manager_required
def order_cancel(order_id):
    order = get_order(order_id)
    if order["status"] in ("Completed", "Cancelled"):
        flash(f"Order is already {order['status']}.", "error")
    elif order["paid"] > 0:
        flash("This order has payments recorded, so it can't be cancelled.", "error")
    else:
        execute("UPDATE orders SET status = 'Cancelled', cancelled_at = ?, updated_at = ? "
                "WHERE id = ?", (now(), now(), order_id))
        flash(f"Order {order['queue_no']:03d} cancelled.", "info")
    return redirect(url_for("order_detail", order_id=order_id))


@app.route("/api/customers")
@staff_required
def api_customer_lookup():
    """Autofill the customer's name from their phone so it isn't typed twice."""
    phone = clean_phone(request.args.get("phone"))
    customer = phone and query("SELECT * FROM customers WHERE phone = ?", (phone,), one=True)
    if not customer:
        return jsonify(found=False)
    count = query("SELECT COUNT(*) AS n FROM orders WHERE customer_id = ?",
                  (customer["id"],), one=True)["n"]
    return jsonify(found=True, name=customer["name"], orders=count)


# --------------------------------------------------------------------------
# Manager: dashboard, services, staff
# --------------------------------------------------------------------------

@app.route("/manager")
@manager_required
def dashboard():
    start = request.args.get("start") or today()
    end = request.args.get("end") or today()
    if end < start:
        start, end = end, start
    rng = (start, end)
    collected = query("SELECT COALESCE(SUM(amount), 0) AS v, COUNT(*) AS n FROM payments "
                      "WHERE date(created_at) BETWEEN ? AND ?", rng, one=True)
    order_stats = query("SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS v FROM orders "
                        "WHERE queue_date BETWEEN ? AND ? AND status != 'Cancelled'",
                        rng, one=True)
    pending = query("SELECT COUNT(*) AS n FROM orders WHERE status IN "
                    "('Waiting', 'In Progress', 'Ready')", one=True)["n"]
    unpaid = [o for o in query(ORDER_SELECT + " WHERE o.status != 'Cancelled' "
                                              "ORDER BY o.id DESC")
              if balance(o) > 0.004]
    by_service = query(
        "SELECT s.name, s.icon, COUNT(o.id) AS n, COALESCE(SUM(o.quantity), 0) AS qty, "
        "COALESCE(SUM(o.amount), 0) AS value FROM services s LEFT JOIN orders o "
        "ON o.service_id = s.id AND o.queue_date BETWEEN ? AND ? AND o.status != 'Cancelled' "
        "GROUP BY s.id ORDER BY value DESC, s.name", rng)
    by_method = query("SELECT method, COUNT(*) AS n, SUM(amount) AS total FROM payments "
                      "WHERE date(created_at) BETWEEN ? AND ? GROUP BY method "
                      "ORDER BY total DESC", rng)
    by_staff = query(
        "SELECT COALESCE(u.full_name, 'Customer self check-in') AS name, COUNT(o.id) AS n, "
        "SUM(o.amount) AS value FROM orders o LEFT JOIN users u ON u.id = o.created_by "
        "WHERE o.queue_date BETWEEN ? AND ? AND o.status != 'Cancelled' "
        "GROUP BY o.created_by ORDER BY n DESC", rng)
    end_day = date.fromisoformat(end)
    daily = []
    for i in range(6, -1, -1):
        d = (end_day - timedelta(days=i)).isoformat()
        v = query("SELECT COALESCE(SUM(amount), 0) AS v FROM payments "
                  "WHERE date(created_at) = ?", (d,), one=True)["v"]
        daily.append({"date": d, "label": date.fromisoformat(d).strftime("%a"), "value": v})
    recent = query("SELECT p.*, o.queue_no, o.id AS oid, c.name AS customer_name, "
                   "u.full_name AS received_by_name FROM payments p "
                   "JOIN orders o ON o.id = p.order_id JOIN customers c ON c.id = o.customer_id "
                   "LEFT JOIN users u ON u.id = p.received_by ORDER BY p.id DESC LIMIT 10")
    return render_template(
        "dashboard.html", start=start, end=end, collected=collected, order_stats=order_stats,
        pending=pending, unpaid=unpaid, outstanding=sum(balance(o) for o in unpaid),
        by_service=by_service, by_method=by_method, by_staff=by_staff, daily=daily,
        daily_max=max([d["value"] for d in daily] + [1]),
        service_max=max([s["value"] for s in by_service] + [1]), recent=recent,
        today=today(), week_ago=(date.today() - timedelta(days=6)).isoformat(),
        month_start=date.today().replace(day=1).isoformat())


@app.route("/manager/services", methods=["GET", "POST"])
@manager_required
def services():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = parse_money(request.form.get("unit_price"))
        icon = request.form.get("icon", "").strip() or "🖨️"
        service_id = parse_int(request.form.get("id"))
        if not name or price is None or price < 0:
            flash("Enter a service name and a valid price.", "error")
        else:
            try:
                if service_id:
                    execute("UPDATE services SET name = ?, unit_price = ?, icon = ?, active = ? "
                            "WHERE id = ?", (name, price, icon,
                                             1 if request.form.get("active") else 0, service_id))
                    flash(f"{name} updated. New orders will use {money(price)} each.", "success")
                else:
                    execute("INSERT INTO services (name, unit_price, icon) VALUES (?, ?, ?)",
                            (name, price, icon))
                    flash(f"{name} added at {money(price)} each.", "success")
            except sqlite3.IntegrityError:
                flash(f"A service called {name} already exists.", "error")
        return redirect(url_for("services"))
    rows = query("SELECT * FROM services ORDER BY active DESC, id")
    return render_template("services.html", services=rows)


@app.route("/manager/staff", methods=["GET", "POST"])
@manager_required
def staff():
    if request.method == "POST":
        action = request.form.get("action")
        user_id = parse_int(request.form.get("id"))
        if action == "add":
            username = request.form.get("username", "").strip().lower()
            full_name = request.form.get("full_name", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role")
            if not re.fullmatch(r"[a-z0-9_.]{3,30}", username):
                flash("Username: 3-30 letters, numbers, dots or underscores.", "error")
            elif not full_name or role not in ("attendant", "manager"):
                flash("Enter the full name and choose a role.", "error")
            elif len(password) < 6:
                flash("Password must be at least 6 characters.", "error")
            else:
                try:
                    execute("INSERT INTO users (username, full_name, password_hash, role) "
                            "VALUES (?, ?, ?, ?)",
                            (username, full_name, hash_password(password), role))
                    flash(f"Account created for {full_name}.", "success")
                except sqlite3.IntegrityError:
                    flash(f"The username {username} is taken.", "error")
        elif action == "toggle" and user_id:
            if user_id == g.user["id"]:
                flash("You can't deactivate your own account.", "error")
            else:
                execute("UPDATE users SET active = 1 - active WHERE id = ?", (user_id,))
                flash("Account status changed.", "success")
        elif action == "password" and user_id:
            password = request.form.get("password", "")
            if len(password) < 6:
                flash("Password must be at least 6 characters.", "error")
            else:
                execute("UPDATE users SET password_hash = ? WHERE id = ?",
                        (hash_password(password), user_id))
                flash("Password reset.", "success")
        return redirect(url_for("staff"))
    rows = query("SELECT * FROM users ORDER BY active DESC, role DESC, full_name")
    return render_template("staff.html", staff=rows)


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", 5000)), debug=True)
