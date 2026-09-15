"""Tasker: a small, local teaching app. Run with `python app.py`."""

import argparse
import csv
import io
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import (
    Flask, Response, abort, flash, g, jsonify, redirect, render_template,
    request, session, url_for,
)
from werkzeug.exceptions import HTTPException, ServiceUnavailable

ROOT = Path(__file__).resolve().parent
DEMO_USERS = ((1, "Alice"), (2, "Bob"))
FILTERS = ("all", "open", "completed")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    """Use one SQLite connection per request, and close it afterward."""
    if "db" not in g:
        from flask import current_app
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def seed_demo(db):
    today = date.today()
    samples = [
        (1, "Book the meeting room", 0, False),
        (1, "Send the weekly update", 0, False),
        (1, "Plan next week's priorities", 1, False),
        (1, "Pick up a birthday card", None, False),
        (1, "Review the project notes", -1, True),
        (1, "Schedule a catch-up with the team", -1, True),
        (2, "Prepare the workshop slides", 0, False),
        (2, "Water the plants", 1, False),
        (2, "Return the library books", None, False),
        (2, "Confirm the lunch reservation", -1, True),
    ]
    with db:
        db.executemany("INSERT INTO users (id, name) VALUES (?, ?)", DEMO_USERS)
        for user_id, title, offset, completed in samples:
            due = (today + timedelta(days=offset)).isoformat() if offset is not None else None
            db.execute(
                "INSERT INTO tasks (user_id, title, due_date, completed, created_at, completed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, title, due, int(completed), now(), now() if completed else None),
            )


def read_or_create_key(directory):
    """Keep sessions valid across restarts without committing a secret."""
    key_path = directory / "session.key"
    try:
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return key_path.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(key)
    return key


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=str(ROOT / ".instance" / "tasker.sqlite3"),
        SECRET_KEY=None,
        SESSION_COOKIE_NAME="tasker_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=16 * 1024,
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
    )
    if test_config:
        app.config.update(test_config)
    directory = Path(app.config["DATABASE"]).parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = read_or_create_key(directory)

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with app.app_context():
        db = get_db()
        db.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
        if db.execute("SELECT count(*) FROM users").fetchone()[0] == 0:
            seed_demo(db)

    @app.before_request
    def load_user_and_check_csrf():
        if request.endpoint == "static":
            return
        # The home page starts a fictional Alice session for classroom convenience.
        # This deliberately is NOT a production login or identity verification system.
        if request.endpoint == "index" and session.get("user_id") not in (1, 2):
            session.clear()
            session["user_id"] = 1
            session["csrf_token"] = secrets.token_hex(32)
        g.user = get_db().execute(
            "SELECT id, name FROM users WHERE id = ?", (session.get("user_id"),)
        ).fetchone()
        if not g.user:
            abort(401, description="Open Tasker to start a demo session.")
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            supplied = request.form.get("csrf_token", "")
            if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
                abort(400, description="This page has expired. Refresh Tasker and try again.")

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'self'"
        )
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def shared_template_values():
        return {"demo_users": DEMO_USERS, "csrf_token": session.get("csrf_token", "")}

    @app.template_filter("due_label")
    def due_label(value):
        if not value:
            return "No due date"
        due = date.fromisoformat(value)
        delta = (due - date.today()).days
        if delta == 0:
            return "Today"
        if delta == 1:
            return "Tomorrow"
        return f"{due.strftime('%b')} {due.day}" + (f", {due.year}" if due.year != date.today().year else "")

    def selected_filter():
        value = request.values.get("filter", "all")
        return value if value in FILTERS else "all"

    def user_tasks(search=None):
        # The owner restriction is server-side, even if a request supplies another user_id.
        query = "SELECT * FROM tasks WHERE user_id = ?"
        if search:
            # Deliberately unsafe lesson checkpoint: CodeQL should flag this interpolation.
            query += f" AND title LIKE '%{search}%'"
        query += " ORDER BY completed, due_date IS NULL, due_date, id DESC"
        return get_db().execute(
            query, (g.user["id"],),
        ).fetchall()

    def owned_task(task_id):
        task = get_db().execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, g.user["id"]),
        ).fetchone()
        if task is None:
            abort(404, description="That task isn't available in your list.")
        return task

    def task_page(errors=None, form=None, status=200):
        tasks = user_tasks()
        counts = {
            "all": len(tasks),
            "open": sum(not task["completed"] for task in tasks),
            "completed": sum(bool(task["completed"]) for task in tasks),
        }
        active = selected_filter()
        visible = [task for task in tasks if active == "all" or bool(task["completed"]) == (active == "completed")]
        today = date.today()
        return render_template(
            "index.html", tasks=visible, counts=counts, active=active,
            today=today.isoformat(), date_heading=today.strftime("%A, %B ") + str(today.day),
            errors=errors or {}, form=form or {},
        ), status

    @app.get("/")
    def index():
        return task_page()

    @app.post("/demo/switch")
    def switch_user():
        user_id = request.form.get("user_id", type=int)
        if user_id not in (1, 2):
            abort(400, description="Choose Alice or Bob for this demo.")
        session.clear()
        session["user_id"] = user_id
        session["csrf_token"] = secrets.token_hex(32)
        return redirect(url_for("index"), code=303)

    @app.post("/tasks")
    def add_task():
        title = request.form.get("title", "").strip()
        due = request.form.get("due_date", "").strip()
        errors = {}
        if not title:
            errors["title"] = "Give your task a name."
        elif len(title) > 100:
            errors["title"] = "Use 100 characters or fewer."
        elif any(ord(character) < 32 or ord(character) == 127 for character in title):
            errors["title"] = "Use a single line of text for your task."
        if due:
            try:
                if date.fromisoformat(due).isoformat() != due:
                    raise ValueError
            except ValueError:
                errors["due_date"] = "Choose a valid date."
        if errors:
            return task_page(errors, {"title": title, "due_date": due}, 422)
        db = get_db()
        with db:
            db.execute(
                "INSERT INTO tasks (user_id, title, due_date, created_at) VALUES (?, ?, ?, ?)",
                (g.user["id"], title, due or None, now()),
            )
        flash("Task added. You've got this.")
        # A new task is open; show it even when it was added from the completed view.
        return redirect(url_for("index", filter="open" if selected_filter() == "completed" else selected_filter()), code=303)

    @app.post("/tasks/<int:task_id>/complete")
    def complete_task(task_id):
        owned_task(task_id)
        value = request.form.get("completed")
        if value not in ("0", "1"):
            abort(400, description="Choose an open or completed status.")
        db = get_db()
        with db:
            db.execute(
                "UPDATE tasks SET completed = ?, completed_at = ? WHERE id = ? AND user_id = ?",
                (int(value), now() if value == "1" else None, task_id, g.user["id"]),
            )
        flash("Task completed. Nice work." if value == "1" else "Task moved back to open.")
        return redirect(url_for("index", filter=selected_filter()), code=303)

    @app.get("/api/tasks")
    def list_tasks():
        return jsonify(tasks=[dict(task) for task in user_tasks(request.args.get("q"))])

    @app.get("/api/tasks/<int:task_id>")
    def get_task(task_id):
        return jsonify(dict(owned_task(task_id)))

    @app.get("/exports/tasks.csv")
    def export_tasks():
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Task", "Status", "Due date", "Created at (UTC)", "Completed at (UTC)"])
        for task in user_tasks():
            title = task["title"]
            # Spreadsheet apps must treat titles as text, not executable formulas.
            if title.lstrip().startswith(("=", "+", "-", "@")):
                title = "'" + title
            writer.writerow([
                title, "Completed" if task["completed"] else "Open", task["due_date"] or "",
                task["created_at"], task["completed_at"] or "",
            ])
        filename = f"tasker-{g.user['name'].lower()}-{date.today().isoformat()}.csv"
        return Response(
            "\ufeff" + output.getvalue(), mimetype="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/") or request.path.startswith("/exports/"):
            return jsonify(error=error.description), error.code
        return render_template("error.html", error=error), error.code

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.error("Tasker database operation failed: %s", type(error).__name__)
        error = ServiceUnavailable(description="Your tasks couldn't be saved or loaded. Please try again.")
        if request.path.startswith("/api/") or request.path.startswith("/exports/"):
            return jsonify(error=error.description), 503
        return render_template("error.html", error=error), 503

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the local Tasker course app.")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--reset-demo", action="store_true", help="Replace all tasks with the sample data")
    parser.add_argument("--yes", action="store_true", help="Confirm replacement of local demo data")
    args = parser.parse_args()
    app = create_app()
    if args.reset_demo:
        if not args.yes:
            parser.error("Reset deletes local tasks. Add --yes to confirm, after stopping the server.")
        with app.app_context():
            db = get_db()
            with db:
                db.execute("DELETE FROM tasks")
                db.execute("DELETE FROM users")
            seed_demo(db)
        print("Tasker demo reset. Alice and Bob's sample tasks are ready.")
    else:
        app.run(host="127.0.0.1", port=args.port, debug=False)
