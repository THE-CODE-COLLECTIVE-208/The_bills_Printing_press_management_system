"""End-to-end checks for every main flow. Run: python -m pytest -q  (or python tests/test_app.py)"""
import os
import re
import sys
import tempfile

DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["PRINTSHOP_DB"] = DB
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as shop  # noqa: E402

shop.app.config["TESTING"] = True


def token_from_page(c, url):
    """Read the CSRF token from a rendered form, exactly like a browser would."""
    html = c.get(url).data
    m = re.search(rb'name="csrf" value="([0-9a-f]+)"', html)
    assert m, f"no CSRF token rendered on {url}"
    return m.group(1).decode()


def client():
    c = shop.app.test_client()
    c.csrf = token_from_page(c, "/checkin")
    return c


def post(c, url, **data):
    data["csrf"] = c.csrf
    return c.post(url, data=data, follow_redirects=True)


def login(c, username, password):
    r = post(c, "/login", username=username, password=password)
    assert b"Welcome" in r.data, r.data[:500]
    c.csrf = token_from_page(c, "/orders/new")  # login starts a fresh session


def test_full_flow():
    # Public pages render
    pub = client()
    for url in ["/", "/checkin", "/track", "/display", "/login"]:
        assert pub.get(url).status_code == 200, url
    # Staff pages need login
    assert pub.get("/queue").status_code == 302
    assert pub.get("/manager").status_code == 302
    # CSRF is enforced
    assert pub.post("/checkin", data={"name": "x"}).status_code == 400

    # Customer self check-in -> ticket -> tracking
    r = post(pub, "/checkin", name="Esi Ofori", phone="024 111 2222", service_id="4")
    assert r.status_code == 200 and b"001" in r.data and b"Lamination" in r.data
    code = re.search(rb'class="code">([0-9A-F]{6})<', r.data).group(1).decode()
    assert pub.get(f"/track/{code}").status_code == 200
    assert pub.get(f"/api/track/{code}").json["status"] == "Waiting"
    assert post(pub, "/track", code=code.lower()).request.path == f"/track/{code}"
    assert pub.get("/track/ZZZZZZ").status_code == 404
    assert b"Lamination" in pub.get("/display").data
    assert b"Esi" not in pub.get("/display").data  # board shows numbers, not names

    # Attendant
    att = client()
    login(att, "attendant", "attendant123")
    assert att.get("/manager").status_code == 403
    q = att.get("/queue")
    assert b"Esi Ofori" in q.data and b"Self check-in" in q.data
    # Returning-customer lookup
    assert att.get("/api/customers?phone=0241112222").json == {"found": True, "name": "Esi Ofori", "orders": 1}
    assert att.get("/api/customers?phone=0200000000").json == {"found": False}
    # New counter order, paid now
    r = post(att, "/orders/new", name="Kojo Darko", phone="0559998888", service_id="3",
             quantity="40", notes="A4", paid_now="1", method="Mobile Money")
    assert b"Order 002 saved" in r.data and b"20.00" in r.data and b"Payment of" in r.data
    # Validation
    assert b"Quantity must be" in post(att, "/orders/new", name="X", service_id="1", quantity="0").data

    # Move order 1 through statuses; can't complete before payment
    post(att, "/orders/1/status", status="In Progress")
    assert pub.get(f"/api/track/{code}").json["status"] == "In Progress"
    post(att, "/orders/1/status", status="Ready")
    assert b"Ready but not paid" in att.get("/queue").data
    r = post(att, "/orders/1/status", status="Completed")
    assert b"Record the payment" in r.data
    # Edit quantity, overpay rejected, partial then full payment
    r = post(att, "/orders/1/edit", service_id="4", quantity="3", notes="ID cards")
    assert b"New total: GH\xe2\x82\xb5 15.00" in r.data
    assert b"more than the balance" in post(att, "/orders/1/payment", amount="99", method="Cash").data
    assert b"Balance left: GH\xe2\x82\xb5 5.00" in post(att, "/orders/1/payment", amount="10", method="Cash").data
    assert b"fully paid" in post(att, "/orders/1/payment", amount="5", method="Card").data
    r = post(att, "/orders/1/status", status="Completed")
    assert b"is now Completed" in r.data
    assert b"be changed" in post(att, "/orders/1/edit", service_id="4", quantity="1").data
    # Jump straight from Waiting to Completed on a paid order fills every timestamp
    post(att, "/orders/2/status", status="Completed")
    with shop.app.app_context():
        row = shop.query("SELECT * FROM orders WHERE id = 2", one=True)
        assert row["processing_at"] and row["ready_at"] and row["completed_at"]
    # Search
    assert b"Kojo Darko" in att.get("/orders?q=kojo").data
    assert b"Kojo Darko" in att.get("/orders?q=002").data
    assert b"Kojo Darko" not in att.get("/orders?q=esi").data
    assert b"Esi Ofori" in att.get("/orders?status=Completed").data
    assert att.get("/orders/1").status_code == 200
    assert att.get("/orders/999").status_code == 404
    # Attendant can't cancel
    post(att, "/orders/new", name="Ibrahim", service_id="1", quantity="2")
    assert post(att, "/orders/3/cancel").status_code == 403

    # Manager
    mgr = client()
    login(mgr, "manager", "manager123")
    r = mgr.get("/manager")
    assert r.status_code == 200 and b"35.00" in r.data  # 20 + 10 + 5 collected
    assert b"Ibrahim" in r.data  # unpaid order listed
    assert mgr.get("/manager?start=2020-01-01&end=2030-01-01").status_code == 200
    assert b"cancelled" in post(mgr, "/orders/3/cancel").data
    assert b"be cancelled" in post(mgr, "/orders/1/cancel").data or b"already" in post(mgr, "/orders/1/cancel").data
    # Services
    assert b"added" in post(mgr, "/manager/services", name="Passport photos", unit_price="15", icon="").data
    assert b"already exists" in post(mgr, "/manager/services", name="Photocopy", unit_price="1").data
    r = post(mgr, "/manager/services", id="3", name="Photocopy", unit_price="0.60", icon="📄", active="1")
    assert b"0.60 each" in r.data
    # Staff
    assert b"Account created" in post(mgr, "/manager/staff", action="add", username="yaw",
                                      full_name="Yaw Boateng", role="attendant", password="secret1").data
    assert b"taken" in post(mgr, "/manager/staff", action="add", username="yaw",
                            full_name="Y", role="attendant", password="secret1").data
    assert b"own account" in post(mgr, "/manager/staff", action="toggle", id="2").data
    new = client()
    login(new, "yaw", "secret1")
    post(mgr, "/manager/staff", action="toggle", id="3")
    assert new.get("/queue").status_code == 302  # disabled user is logged out
    # Logout
    post(mgr, "/logout")
    assert mgr.get("/manager").status_code == 302


if __name__ == "__main__":
    test_full_flow()
    print("All checks passed.")
