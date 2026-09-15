"""Acceptance checks for the behaviors learners can observe in Tasker."""

import csv
import io
import sqlite3
import tempfile
import unittest
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

    def test_api_search_finds_matching_titles_for_the_current_user(self):
        self.post(self.alice, "/tasks", title="Plan Alice's demo")
        self.post(self.bob, "/tasks", title="Plan Bob's demo")
        response = self.bob.get("/api/tasks", query_string={"q": "demo", "user_id": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([task["title"] for task in response.get_json()["tasks"]], ["Plan Bob's demo"])

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


if __name__ == "__main__":
    unittest.main()
