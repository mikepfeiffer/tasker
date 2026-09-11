"""Repeatable Due today checks using a disposable database and local date."""

import csv
import io
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app import create_app, get_db


class DueTodayTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        clock_patch = patch("app.date", wraps=date)
        self.clock = clock_patch.start()
        self.addCleanup(clock_patch.stop)
        self.clock.today.return_value = date(2026, 1, 31)
        self.app = create_app({
            "TESTING": True,
            "DATABASE": str(Path(directory.name) / "today.sqlite3"),
            "SECRET_KEY": "synthetic-test-key-only",
        })
        self.samples = [
            (1, "Alice today", "2026-01-31", 0),
            (1, "Alice completed", "2026-01-31", 1),
            (1, "Alice yesterday", "2026-01-30", 0),
            (1, "Alice tomorrow", "2026-02-01", 0),
            (1, "Alice undated", None, 0),
            (2, "Bob today", "2026-01-31", 0),
        ]
        with self.app.app_context():
            db = get_db()
            with db:
                db.execute("DELETE FROM tasks")
                db.executemany(
                    "INSERT INTO tasks (user_id, title, due_date, completed, created_at) "
                    "VALUES (?, ?, ?, ?, '2026-01-01T12:00:00+00:00')", self.samples,
                )
        self.client = self.app.test_client()
        self.client.get("/")

    def post(self, path, **data):
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        return self.client.post(path, data={"csrf_token": token, **data})

    def rows(self):
        with self.app.app_context():
            return get_db().execute("SELECT * FROM tasks ORDER BY id").fetchall()

    def assert_view(self, response, active, titles, counts):
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertEqual(set(re.findall(r'<span class="task-title">(.*?)</span>', html)), set(titles))
        for value, count in counts.items():
            self.assertRegex(html, rf'href="/\?filter={value}"[^>]*>[^<]+<span class="filter-count">{count}</span>')
        self.assertRegex(html, rf'href="/\?filter={active}" class="filter active" aria-current="page"')
        self.assertEqual(html.count('class="filter active"'), 1)
        self.assertIn(f'name="filter" value="{active}"', html)
        return html

    def test_membership_counts_and_refresh(self):
        for _ in range(2):
            self.assert_view(self.client.get("/?filter=today&user_id=2"), "today", ["Alice today"],
                             {"all": 5, "open": 4, "completed": 1, "today": 1})

    def test_local_calendar_date_is_recomputed_on_next_request(self):
        self.clock.today.return_value = date(2026, 2, 1)
        self.assert_view(self.client.get("/?filter=today"), "today", ["Alice tomorrow"], {"today": 1})

    def test_no_matches_and_entirely_empty_account(self):
        for condition in ("user_id = 1 AND title = 'Alice today'", "user_id = 1"):
            with self.subTest(condition=condition), self.app.app_context():
                db = get_db()
                with db:
                    db.execute("DELETE FROM tasks WHERE " + condition)
                html = self.assert_view(self.client.get("/?filter=today"), "today", [], {"today": 0})
                self.assertIn("<h2>Nothing due today</h2>", html)

    def test_complete_updates_list_count_and_preserves_selection(self):
        task_id = next(row["id"] for row in self.rows() if row["title"] == "Alice today")
        response = self.post(f"/tasks/{task_id}/complete", completed="1", filter="today")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.location, "/?filter=today")
        self.assert_view(self.client.get(response.location), "today", [],
                         {"all": 5, "open": 3, "completed": 2, "today": 0})
        row = next(row for row in self.rows() if row["id"] == task_id)
        self.assertEqual(row["completed"], 1)
        self.assertIsNotNone(row["completed_at"])

    def test_add_preserves_selection_and_saves_every_valid_due_date(self):
        visible = ["Alice today"]
        for index, due in enumerate(("2026-01-31", "2026-01-30", "2026-02-01", "")):
            with self.subTest(due=due):
                title = f"New task {index}"
                response = self.post("/tasks", title=title, due_date=due, filter="today", user_id="2")
                self.assertEqual(response.status_code, 303)
                self.assertEqual(response.location, "/?filter=today")
                if due == "2026-01-31":
                    visible.append(title)
                self.assert_view(self.client.get(response.location), "today", visible, {"today": 2})
                row = next(row for row in self.rows() if row["title"] == title)
                self.assertEqual((row["user_id"], row["due_date"], row["completed"]), (1, due or None, 0))

    def test_invalid_add_preserves_today_and_form_protections(self):
        response = self.post("/tasks", title="Keep my title", due_date="2026-02-30", filter="today")
        self.assertEqual(response.status_code, 422)
        html = response.get_data(as_text=True)
        self.assertIn('name="filter" value="today"', html)
        self.assertIn('value="Keep my title"', html)
        self.assertEqual(len(self.rows()), 6)
        bob_id = next(row["id"] for row in self.rows() if row["user_id"] == 2)
        self.assertEqual(self.post(f"/tasks/{bob_id}/complete", completed="1", filter="today").status_code, 404)
        for path, data in (("/tasks", {"title": "Rejected"}),
                           (f"/tasks/{bob_id}/complete", {"completed": "1"})):
            self.assertEqual(self.client.post(path, data={"filter": "today", **data}).status_code, 400)

    def test_existing_views_and_actions_keep_their_behavior(self):
        for active in ("all", "open", "completed"):
            with self.subTest(active=active):
                titles = [title for owner, title, _, completed in self.samples
                          if owner == 1 and (active == "all" or bool(completed) == (active == "completed"))]
                self.assert_view(self.client.get(f"/?filter={active}"), active, titles,
                                 {"all": 5, "open": 4, "completed": 1, "today": 1})
                task_id = next(row["id"] for row in self.rows() if row["title"] == "Alice today")
                for completed in ("1", "0"):
                    response = self.post(f"/tasks/{task_id}/complete", completed=completed, filter=active)
                    self.assertEqual(response.status_code, 303)
                    self.assertEqual(response.location, f"/?filter={active}")
                    row = next(row for row in self.rows() if row["id"] == task_id)
                    self.assertEqual(row["completed"], int(completed))
        for active in ("all", "open", "completed"):
            response = self.post("/tasks", title=f"Added from {active}", filter=active)
            self.assertEqual(response.status_code, 303)
            expected = "open" if active == "completed" else active
            self.assertEqual(response.location, f"/?filter={expected}")
            self.assertIn(f"Added from {active}", self.client.get(response.location).get_data(as_text=True))

    def test_account_switch_resets_view_and_separates_today_results(self):
        self.client.get("/?filter=today")
        for owner, title in ((2, "Bob today"), (1, "Alice today")):
            response = self.post("/demo/switch", user_id=str(owner), filter="today")
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.location, "/")
            self.assertIn('href="/?filter=all" class="filter active"', self.client.get("/").get_data(as_text=True))
            self.assert_view(self.client.get("/?filter=today"), "today", [title], {"today": 1})

    def test_download_from_today_keeps_all_current_account_rows_and_format(self):
        for owner in (1, 2):
            self.post("/demo/switch", user_id=str(owner))
            html = self.client.get("/?filter=today").get_data(as_text=True)
            self.assertIn('href="/exports/tasks.csv"', html)
            response = self.client.get(f"/exports/tasks.csv?filter=today&user_id={3 - owner}")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r\r\n", response.data)
            rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"), newline="")))
            self.assertEqual(rows[0], ["Task", "Status", "Due date", "Created at (UTC)", "Completed at (UTC)"])
            expected = [[row["title"], "Completed" if row["completed"] else "Open", row["due_date"] or "",
                         row["created_at"], row["completed_at"] or ""] for row in self.rows() if row["user_id"] == owner]
            self.assertCountEqual(rows[1:], expected)


if __name__ == "__main__":
    unittest.main()
