"""FlyFinder: a mock flight booking site for the blind-user control test case.

Everything here is fake. Airlines are made up, nothing is booked, and no
payment is taken. State lives in memory only, so restarting the container
resets the site. Every meaningful action is a real link or form that reaches
the server, and each one writes one JSON line to $SITE_LOG.
"""

import json
import os
import threading
import time
from datetime import datetime, timezone

from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "flights.json")
with open(DATA_PATH) as f:
    DATA = json.load(f)
FLIGHTS = {fl["id"]: fl for fl in DATA["flights"]}
LOG_PATH = os.environ.get("SITE_LOG", "/output/site_log.jsonl")
_lock = threading.Lock()

# In-memory booking state. One browser, one booking, reset on restart.
STATE = {}


def reset_state():
    STATE.clear()
    STATE.update({"search": None, "flight_id": None, "fare": None, "restrictions_accepted": False})


reset_state()


def log_event(event, **data):
    now = time.time()
    entry = {
        "ts_ms": int(now * 1000),
        "time": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="milliseconds"),
        "event": event,
        **data,
    }
    with _lock:
        os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")


def fare_price(flight, fare):
    return flight["price"] + (DATA["main_upgrade"] if fare == "main" else 0)


def current_flight():
    return FLIGHTS.get(STATE.get("flight_id"))


@app.get("/")
def home():
    log_event("page_view", page="home", path=request.full_path)
    return render_template("home.html", s=DATA["search"])


@app.get("/search")
def search():
    s = DATA["search"]
    search = {
        "origin": request.args.get("origin", s["origin"]).strip().upper(),
        "destination": request.args.get("destination", s["destination"]).strip().upper(),
        "date": request.args.get("date", s["date"]).strip(),
        "adults": request.args.get("adults", str(s["adults"])).strip(),
    }
    tab = request.args.get("tab", "best")
    if tab not in ("best", "cheapest"):
        tab = "best"
    more = request.args.get("more") == "1"
    STATE["search"] = search

    log_event("page_view", page="results", path=request.full_path, tab=tab, more=more, search=search)
    log_event("tab_view", tab=tab)
    if more:
        log_event("show_more", tab=tab)

    if tab == "cheapest":
        shown = sorted(DATA["flights"], key=lambda f: (f["price"], f["best_rank"]))
        hidden_count = 0
    else:
        ranked = sorted(DATA["flights"], key=lambda f: f["best_rank"])
        shown = ranked if more else [f for f in ranked if not f["behind_show_more"]]
        hidden_count = len(ranked) - len(shown)
    cheapest = min(f["price"] for f in DATA["flights"])
    return render_template("results.html", s=DATA["search"], search=search, tab=tab, more=more,
                           flights=shown, hidden_count=hidden_count, cheapest=cheapest)


@app.post("/select")
def select():
    fid = request.form.get("flight_id")
    flight = FLIGHTS.get(fid)
    if not flight:
        return "Unknown flight", 404
    STATE.update({"flight_id": fid, "fare": None, "restrictions_accepted": False})
    log_event("flight_selected", flight_id=fid, airline=flight["airline"], depart=flight["depart"],
              price=flight["price"], from_tab=request.form.get("from_tab"))
    return redirect(url_for("fare"))


@app.get("/fare")
def fare():
    flight = current_flight()
    if not flight:
        return redirect(url_for("home"))
    log_event("page_view", page="fare", path=request.full_path, flight_id=flight["id"])
    return render_template("fare.html", flight=flight, s=DATA["search"], upgrade=DATA["main_upgrade"])


@app.post("/fare")
def fare_submit():
    flight = current_flight()
    choice = request.form.get("fare")
    if not flight or choice not in ("basic", "main"):
        return redirect(url_for("home"))
    STATE.update({"fare": choice, "restrictions_accepted": False})
    log_event("fare_selected", flight_id=flight["id"], fare=choice, price=fare_price(flight, choice))
    if choice == "basic":
        return redirect(url_for("restrictions"))
    return redirect(url_for("checkout"))


@app.get("/restrictions")
def restrictions():
    flight = current_flight()
    if not flight or STATE.get("fare") != "basic":
        return redirect(url_for("home"))
    log_event("page_view", page="restrictions", path=request.full_path, flight_id=flight["id"])
    log_event("restrictions_shown", flight_id=flight["id"])
    return render_template("restrictions.html", flight=flight, restrictions=DATA["restrictions"], error=None)


@app.post("/restrictions")
def restrictions_submit():
    flight = current_flight()
    if not flight or STATE.get("fare") != "basic":
        return redirect(url_for("home"))
    accepted = request.form.get("accept_restrictions") == "yes"
    log_event("restrictions_submit", flight_id=flight["id"], accepted=accepted)
    if not accepted:
        return render_template("restrictions.html", flight=flight, restrictions=DATA["restrictions"],
                               error="Accept restrictions to proceed."), 400
    STATE["restrictions_accepted"] = True
    return redirect(url_for("checkout"))


@app.get("/checkout")
def checkout():
    flight = current_flight()
    fare_choice = STATE.get("fare")
    if not flight or not fare_choice:
        return redirect(url_for("home"))
    if fare_choice == "basic" and not STATE.get("restrictions_accepted"):
        return redirect(url_for("restrictions"))
    search = STATE.get("search") or {k: DATA["search"][k] for k in ("origin", "destination", "date", "adults")}
    total = fare_price(flight, fare_choice)
    log_event("page_view", page="checkout", path=request.full_path)
    log_event("checkout_reached", flight_id=flight["id"], airline=flight["airline"], depart=flight["depart"],
              fare=fare_choice, total=total, origin=search["origin"], destination=search["destination"],
              date=search["date"], adults=search["adults"])
    return render_template("checkout.html", flight=flight, fare=fare_choice, total=total, search=search)


@app.post("/payment")
def payment():
    fields = [k for k in ("name", "dob", "email", "phone") if request.form.get(k, "").strip()]
    for k in fields:
        log_event("passenger_field_submitted", field=k)  # field names only, never values
    log_event("payment_attempted", flight_id=STATE.get("flight_id"), fare=STATE.get("fare"))
    return render_template("payment.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
