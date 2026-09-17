"""Acceptance checks for the behaviors learners can observe in Tasker."""

import csv
import io
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from app import create_app, get_db


class TaskerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = {
            "TESTING": True,
            "DATABASE": str(Path(self.directory.name) / "test.sqlite3"),
            "SECRET_KEY": "synthetic-test-key-only",
        }
        self.app = create_app(self.config)
        self.alice = self.app.test_client()
        self.bob = self.app.test_client()
        self.alice.get("/")
        self.bob.get("/")
        self.post(self.bob, "/demo/switch", user_id="2")

    def post(self, client, path, **data):
        with client.session_transaction() as session:
            token = session["csrf_token"]
        return client.post(path, data={"csrf_token": token, **data})

    def tasks(self, client):
        return client.get("/api/tasks").get_json()["tasks"]

    def test_home_shows_only_the_current_users_tasks(self):
        alice_page = self.alice.get("/").get_data(as_text=True)
        bob_page = self.bob.get("/").get_data(as_text=True)
        self.assertIn("Book the meeting room", alice_page)
        self.assertNotIn("Water the plants", alice_page)
        self.assertIn("Water the plants", bob_page)
        self.assertNotIn('<span class="task-title">Book the meeting room</span>', bob_page)

    def test_add_task_persists_with_its_date_and_owner_after_restart(self):
        response = self.post(self.alice, "/tasks", title="  Plan the workshop  ", due_date="2027-01-20", user_id="2")
        self.assertEqual(response.status_code, 303)
        restarted = create_app(self.config).test_client()
        restarted.get("/")
        matches = [task for task in self.tasks(restarted) if task["title"] == "Plan the workshop"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["due_date"], "2027-01-20")
        self.assertEqual(matches[0]["user_id"], 1)

    def test_blank_and_long_titles_are_rejected_but_exactly_100_is_allowed(self):
        original_count = len(self.tasks(self.alice))
        for title in ("", "   ", "a" * 101):
            with self.subTest(title=title):
                self.assertEqual(self.post(self.alice, "/tasks", title=title).status_code, 422)
        self.assertEqual(len(self.tasks(self.alice)), original_count)
        self.assertEqual(self.post(self.alice, "/tasks", title="a" * 100).status_code, 303)
        self.assertEqual(len(self.tasks(self.alice)), original_count + 1)

    def test_invalid_date_is_rejected_and_form_input_is_preserved(self):
        response = self.post(self.alice, "/tasks", title="Keep this title", due_date="2026-02-30")
        self.assertEqual(response.status_code, 422)
        self.assertIn('value="Keep this title"', response.get_data(as_text=True))
        self.assertIn("Choose a valid date", response.get_data(as_text=True))

    def test_completion_can_be_reversed_and_filters_match_status(self):
        task = next(task for task in self.tasks(self.alice) if task["title"] == "Book the meeting room")
        self.assertEqual(self.post(self.alice, f"/tasks/{task['id']}/complete", completed="1").status_code, 303)
        self.assertNotIn(task["title"], self.alice.get("/?filter=open").get_data(as_text=True).split('<ul class="task-list">')[-1])
        self.assertIn(task["title"], self.alice.get("/?filter=completed").get_data(as_text=True))
        completed = self.alice.get(f"/api/tasks/{task['id']}").get_json()
        self.assertIsNotNone(completed["completed_at"])
        self.post(self.alice, f"/tasks/{task['id']}/complete", completed="0")
        reopened = self.alice.get(f"/api/tasks/{task['id']}").get_json()
        self.assertEqual(reopened["completed"], 0)
        self.assertIsNone(reopened["completed_at"])

    def test_bob_cannot_read_or_change_alices_task_even_with_a_known_id(self):
        task = self.tasks(self.alice)[0]
        self.assertEqual(self.bob.get(f"/api/tasks/{task['id']}").status_code, 404)
        self.assertEqual(self.post(self.bob, f"/tasks/{task['id']}/complete", completed="1").status_code, 404)
        self.assertEqual(self.alice.get(f"/api/tasks/{task['id']}").get_json()["completed"], task["completed"])

    def test_export_uses_session_owner_not_query_parameters_and_includes_all_statuses(self):
        response = self.bob.get("/exports/tasks.csv?user_id=1&filter=open")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response.headers["Content-Disposition"])
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True).lstrip("\ufeff"))))
        self.assertEqual({row["Task"] for row in rows}, {task["title"] for task in self.tasks(self.bob)})
        self.assertEqual({row["Status"] for row in rows}, {"Open", "Completed"})

    def test_spreadsheet_formula_and_html_are_treated_as_text(self):
        self.post(self.alice, "/tasks", title='=HYPERLINK("https://example.invalid")')
        self.post(self.alice, "/tasks", title='<script>alert("demo")</script>')
        html = self.alice.get("/").get_data(as_text=True)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn('<script>alert("demo")</script>', html)
        exported = self.alice.get("/exports/tasks.csv").get_data(as_text=True)
        rows = list(csv.reader(io.StringIO(exported.lstrip("\ufeff"))))
        self.assertTrue(any(row[0].startswith("'=HYPERLINK") for row in rows))

    def test_missing_csrf_is_rejected_on_every_write_route(self):
        task = self.tasks(self.alice)[0]
        for route, data in (
            ("/tasks", {"title": "Should not be saved"}),
            ("/demo/switch", {"user_id": "2"}),
            (f"/tasks/{task['id']}/complete", {"completed": "1"}),
        ):
            with self.subTest(route=route):
                self.assertEqual(self.alice.post(route, data=data).status_code, 400)

    def test_unauthenticated_api_and_export_requests_are_denied(self):
        anonymous = self.app.test_client()
        for route in ("/api/tasks", "/api/tasks/1", "/exports/tasks.csv"):
            with self.subTest(route=route):
                self.assertEqual(anonymous.get(route).status_code, 401)

    def test_empty_account_has_an_empty_state_and_header_only_export(self):
        with self.app.app_context():
            db = get_db()
            with db:
                db.execute("DELETE FROM tasks WHERE user_id = 1")
        self.assertIn("A fresh start", self.alice.get("/").get_data(as_text=True))
        rows = list(csv.reader(io.StringIO(self.alice.get("/exports/tasks.csv").get_data(as_text=True).lstrip("\ufeff"))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(self.tasks(self.bob)), 4)

    def test_database_failure_has_a_controlled_response(self):
        with patch("app.get_db", side_effect=sqlite3.OperationalError("synthetic failure")):
            response = self.alice.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Please try again", response.get_data(as_text=True))
        self.assertNotIn("synthetic failure", response.get_data(as_text=True))

    def test_generated_key_keeps_the_selected_account_after_restart_in_a_path_with_spaces(self):
        config = {
            **self.config,
            "SECRET_KEY": None,
            "DATABASE": str(Path(self.directory.name) / "Tasker démo" / "tasker.sqlite3"),
        }
        first_app = create_app(config)
        first = first_app.test_client()
        first.get("/")
        self.post(first, "/demo/switch", user_id="2")
        cookie = first.get_cookie("tasker_session")
        second_app = create_app(config)
        second = second_app.test_client()
        second.set_cookie("tasker_session", cookie.value)
        self.assertIn("BOB'S WORKSPACE", second.get("/").get_data(as_text=True))
        self.assertEqual(second_app.config["SECRET_KEY"], first_app.config["SECRET_KEY"])

    def test_csv_is_utf8_with_excel_bom_and_preserves_non_ascii_and_quoted_titles(self):
        title = 'Review "café, Québec" budget'
        self.post(self.alice, "/tasks", title=title)
        response = self.alice.get("/exports/tasks.csv")
        self.assertTrue(response.data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\r\n", response.data)
        rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"), newline="")))
        self.assertIn(title, [row["Task"] for row in rows])


class FixedDate(date):
    """A stand-in for datetime.date whose today() is fixed, so date checks are repeatable."""

    @classmethod
    def today(cls):
        return cls(2026, 3, 10)


class DueTodayFilterTests(unittest.TestCase):
    """The Due today view shows only the current account's open tasks due on the local date."""

    TODAY, YESTERDAY, TOMORROW = "2026-03-10", "2026-03-09", "2026-03-11"
    post = TaskerTests.post
    tasks = TaskerTests.tasks

    def setUp(self):
        TaskerTests.setUp(self)
        patcher = patch("app.date", FixedDate)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.replace_tasks(
            (1, "Finish the report", self.TODAY, False),
            (1, "Already done today", self.TODAY, True),
            (1, "Missed yesterday", self.YESTERDAY, False),
            (1, "Plan tomorrow", self.TOMORROW, False),
            (1, "Someday task", None, False),
            (2, "Bob is due today too", self.TODAY, False),
        )

    def replace_tasks(self, *rows):
        with self.app.app_context():
            db = get_db()
            with db:
                db.execute("DELETE FROM tasks")
                db.executemany(
                    "INSERT INTO tasks (user_id, title, due_date, completed, created_at, completed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [(user_id, title, due, int(done), "2026-03-01T09:00:00+00:00", "2026-03-10T09:00:00+00:00" if done else None)
                     for user_id, title, due, done in rows],
                )

    def due_today_page(self, client=None):
        return (client or self.alice).get("/?filter=today").get_data(as_text=True)

    def listed_titles(self, html):
        return html.split('<ul class="task-list">')[-1] if '<ul class="task-list">' in html else ""

    def task_id(self, title):
        return next(task["id"] for task in self.tasks(self.alice) if task["title"] == title)

    def count_badge(self, html, value):
        return html.split(f'filter={value}"')[1].split("</a>")[0].split('<span class="filter-count">')[1].split("</span>")[0]

    def test_due_today_shows_only_alices_open_tasks_due_today(self):
        html = self.due_today_page()
        listed = self.listed_titles(html)
        self.assertIn("Finish the report", listed)
        for excluded in ("Already done today", "Missed yesterday", "Plan tomorrow", "Someday task", "Bob is due today too"):
            with self.subTest(excluded=excluded):
                self.assertNotIn(excluded, listed)
        self.assertEqual(self.count_badge(html, "today"), "1")
        self.assertIn('href="/?filter=today" class="filter active" aria-current="page">Due today', html)
        self.assertNotIn("Nothing due today", html)

    def test_existing_filter_counts_are_unchanged_by_the_new_filter(self):
        html = self.alice.get("/").get_data(as_text=True)
        self.assertEqual((self.count_badge(html, "all"), self.count_badge(html, "open"), self.count_badge(html, "completed")), ("5", "4", "1"))
        self.assertEqual(self.count_badge(self.due_today_page(self.bob), "today"), "1")
        self.assertIn("Bob is due today too", self.listed_titles(self.due_today_page(self.bob)))

    def test_no_matching_tasks_shows_nothing_due_today_with_a_zero_count(self):
        self.post(self.alice, f"/tasks/{self.task_id('Finish the report')}/complete", completed="1", filter="today")
        html = self.due_today_page()
        self.assertIn("<h2>Nothing due today</h2>", html)
        self.assertEqual(self.count_badge(html, "today"), "0")
        self.replace_tasks()
        html = self.due_today_page()
        self.assertIn("<h2>Nothing due today</h2>", html)
        self.assertEqual(self.count_badge(html, "today"), "0")
        self.assertIn("A fresh start", self.alice.get("/").get_data(as_text=True))

    def test_completing_a_task_from_due_today_keeps_the_view_and_updates_the_count(self):
        response = self.post(self.alice, f"/tasks/{self.task_id('Finish the report')}/complete", completed="1", filter="today")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["Location"], "/?filter=today")
        html = self.due_today_page()
        self.assertNotIn("Finish the report", self.listed_titles(html))
        self.assertEqual(self.count_badge(html, "today"), "0")
        self.assertIn('class="filter active" aria-current="page">Due today', html)

    def test_adding_tasks_from_due_today_keeps_the_view_and_lists_only_those_due_today(self):
        for title, due in (("Call the bank", self.TODAY), ("Renew the passport", self.TOMORROW), ("Read a book", "")):
            with self.subTest(title=title):
                response = self.post(self.alice, "/tasks", title=title, due_date=due, filter="today")
                self.assertEqual(response.status_code, 303)
                self.assertEqual(response.headers["Location"], "/?filter=today")
        saved = {task["title"]: task["due_date"] for task in self.tasks(self.alice)}
        self.assertEqual((saved["Call the bank"], saved["Renew the passport"], saved["Read a book"]), (self.TODAY, self.TOMORROW, None))
        html = self.due_today_page()
        listed = self.listed_titles(html)
        self.assertIn("Call the bank", listed)
        self.assertNotIn("Renew the passport", listed)
        self.assertNotIn("Read a book", listed)
        self.assertEqual(self.count_badge(html, "today"), "2")

    def test_refreshing_the_due_today_url_keeps_it_selected_and_ignores_unknown_filters(self):
        for _ in range(2):
            html = self.due_today_page()
            self.assertIn('class="filter active" aria-current="page">Due today', html)
            self.assertIn("Finish the report", self.listed_titles(html))
        unknown = self.alice.get("/?filter=tomorrow").get_data(as_text=True)
        self.assertIn('class="filter active" aria-current="page">All tasks', unknown)

    def test_export_still_includes_all_tasks_when_due_today_is_selected(self):
        response = self.alice.get("/exports/tasks.csv?filter=today")
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True).lstrip("\ufeff"))))
        self.assertEqual(list(rows[0].keys()), ["Task", "Status", "Due date", "Created at (UTC)", "Completed at (UTC)"])
        self.assertEqual({row["Task"] for row in rows}, {task["title"] for task in self.tasks(self.alice)})
        self.assertEqual(len(rows), 5)


if __name__ == "__main__":
    unittest.main()
