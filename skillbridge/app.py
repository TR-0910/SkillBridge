"""SkillBridge: data-driven career guidance and upskilling (Flask + SQLite)."""
import functools
import sqlite3
from collections import Counter
from datetime import datetime

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db
from job_sources import CSVJobSource
from recommender import CourseCatalog, Recommender
from skills import SkillDictionary

app = Flask(__name__)
app.config.from_object(config)
app.teardown_appcontext(db.close_db)

skill_dict = SkillDictionary()
courses = CourseCatalog()
_recommender = None


def get_recommender():
    global _recommender
    if _recommender is None:
        _recommender = Recommender(db.all_jobs())
    return _recommender


def bootstrap_data():
    db.init_db()
    if not db.all_jobs():
        db.load_jobs(CSVJobSource(), skill_dict)


bootstrap_data()


@app.cli.command("refresh-jobs")
def refresh_jobs():
    """Load any new jobs from the configured source (swap CSVJobSource for an API source here)."""
    global _recommender
    added = db.load_jobs(CSVJobSource(), skill_dict)
    _recommender = None
    print(f"Added {added} new jobs.")


# ---------- helpers ----------
def current_user():
    if "user" not in g:
        uid = session.get("uid")
        g.user = db.get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone() if uid else None
    return g.user


def login_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if current_user() is None:
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def user_levels(uid):
    rows = db.get_db().execute("SELECT skill, level FROM user_skills WHERE user_id = ?", (uid,)).fetchall()
    return {r["skill"]: r["level"] for r in rows}


def profile_text(user, levels):
    parts = [s for s, lv in levels.items() for _ in range(lv)]   # higher level = more weight
    parts += [user[k] or "" for k in ("education", "interests", "projects", "certificates")]
    return " ".join(parts)


def ranked_for(user, query=None):
    levels = user_levels(user["id"])
    return levels, get_recommender().rank(profile_text(user, levels), levels, query)


@app.context_processor
def inject():
    return {"current_user": current_user(), "levels": config.LEVELS,
            "statuses": config.STATUSES, "courses": courses, "demand": get_recommender().demand}


# ---------- auth ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, email = request.form["name"].strip(), request.form["email"].strip().lower()
        pw = request.form["password"]
        if not name or "@" not in email or len(pw) < 6:
            flash("Enter your name, a valid email, and a password of at least 6 characters.", "danger")
        else:
            try:
                with db.get_db() as conn:
                    cur = conn.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                                       (name, email, generate_password_hash(pw)))
                session.clear()
                session["uid"] = cur.lastrowid
                flash("Account created. Add your skills to see job matches.", "success")
                return redirect(url_for("profile"))
            except sqlite3.IntegrityError:
                flash("That email is already registered. Log in instead.", "danger")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        row = db.get_db().execute("SELECT * FROM users WHERE email = ?",
                                  (request.form["email"].strip().lower(),)).fetchone()
        if row and check_password_hash(row["password_hash"], request.form["password"]):
            session.clear()
            session["uid"] = row["id"]
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "danger")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- pages ----------
@app.route("/")
@login_required
def dashboard():
    user = current_user()
    levels, ranked = ranked_for(user)
    gaps = Counter(s for r in ranked[:10] for s in r["analysis"]["missing"])
    counts = db.get_db().execute(
        "SELECT status, COUNT(*) n FROM applications WHERE user_id = ? GROUP BY status", (user["id"],)).fetchall()
    return render_template("dashboard.html", top=ranked[:5], focus=gaps.most_common(6),
                           has_skills=bool(levels), counts={r["status"]: r["n"] for r in counts})


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    conn = db.get_db()
    if request.method == "POST":
        new = {}
        for s in skill_dict.skills:
            try:
                lv = max(0, min(3, int(request.form.get(f"skill::{s}", 0))))
            except ValueError:
                lv = 0
            if lv:
                new[s] = lv
        with conn:
            conn.execute("UPDATE users SET education=?, interests=?, projects=?, certificates=? WHERE id=?",
                         (request.form.get("education", ""), request.form.get("interests", ""),
                          request.form.get("projects", ""), request.form.get("certificates", ""), user["id"]))
            conn.execute("DELETE FROM user_skills WHERE user_id = ?", (user["id"],))
            conn.executemany("INSERT INTO user_skills (user_id, skill, level) VALUES (?, ?, ?)",
                             [(user["id"], s, lv) for s, lv in new.items()])
        flash("Profile and skills saved. Your matches have been updated.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user, groups=skill_dict.grouped(), mine=user_levels(user["id"]))


@app.route("/jobs")
@login_required
def jobs():
    q = request.args.get("q", "")
    levels, ranked = ranked_for(current_user(), q)
    return render_template("jobs.html", ranked=ranked, q=q, has_skills=bool(levels))


@app.route("/jobs/<int:job_id>")
@login_required
def job(job_id):
    user = current_user()
    rec = get_recommender()
    j = next((x for x in rec.jobs if x["id"] == job_id), None)
    if j is None:
        abort(404)
    analysis = rec.analyze(j, user_levels(user["id"]))
    app_row = db.get_db().execute("SELECT * FROM applications WHERE user_id=? AND job_id=?",
                                  (user["id"], job_id)).fetchone()
    return render_template("job.html", job=j, a=analysis, pct=round(100 * analysis["coverage"]), app_row=app_row)


# ---------- application tracker ----------
@app.route("/applications")
@login_required
def tracker():
    user = current_user()
    rows = db.get_db().execute(
        "SELECT a.id, a.status, a.notes, a.updated_at, j.id AS job_id, j.title, j.company, j.location"
        " FROM applications a JOIN jobs j ON j.id = a.job_id WHERE a.user_id = ? ORDER BY a.updated_at DESC",
        (user["id"],)).fetchall()
    rec, lv = get_recommender(), user_levels(user["id"])
    by_id = {x["id"]: x for x in rec.jobs}
    items = [{**dict(r), "analysis": rec.analyze(by_id[r["job_id"]], lv)} for r in rows]
    return render_template("tracker.html", items=items)


@app.route("/applications/add", methods=["POST"])
@login_required
def add_application():
    job_id, status = request.form.get("job_id", type=int), request.form.get("status", "Saved")
    if status not in config.STATUSES or not any(j["id"] == job_id for j in get_recommender().jobs):
        abort(400)
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO applications (user_id, job_id, status, updated_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(user_id, job_id) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at",
            (current_user()["id"], job_id, status, datetime.now().isoformat(timespec="seconds")))
    flash(f"Marked as {status}.", "success")
    return redirect(url_for("job", job_id=job_id))


@app.route("/applications/<int:app_id>/update", methods=["POST"])
@login_required
def update_application(app_id):
    status = request.form.get("status", "")
    if status not in config.STATUSES:
        abort(400)
    with db.get_db() as conn:
        cur = conn.execute("UPDATE applications SET status=?, notes=?, updated_at=? WHERE id=? AND user_id=?",
                           (status, request.form.get("notes", "")[:500],
                            datetime.now().isoformat(timespec="seconds"), app_id, current_user()["id"]))
    if cur.rowcount == 0:
        abort(404)
    flash("Application updated.", "success")
    return redirect(url_for("tracker"))


if __name__ == "__main__":
    app.run(debug=True)
