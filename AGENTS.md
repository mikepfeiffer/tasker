# AGENTS.md

This file provides guidance for AI coding agents when working with code in this repository.

## What this is

Tasker is a deliberately small Flask task tracker that serves as the shared reference app for an
AI-assisted coding course. Two fictional accounts (Alice is user 1, Bob is user 2) are chosen from a
menu without passwords. That is the intended classroom design, not a defect: the README states the
boundaries explicitly (local only, fictional data, demo identity selection instead of authentication,
and no intentional vulnerabilities in this default version). Do not replace the demo login with real
authentication or add production deployment concerns unless asked.

The course runs on Windows. `setup.cmd` and `run.cmd` are plain `.cmd` files on purpose so learners
never have to change PowerShell's script-execution policy. Keep them as `.cmd`, keep them working when
the checkout path contains spaces, and keep their CRLF line endings (`.gitattributes` forces LF for
every other file).

## Commands

Python 3.12 is required (`setup.cmd` refuses other versions; CI runs 3.12 on Windows and Linux). The
Windows commands call the venv interpreter directly, so no activation is needed. Run tests from the
repo root: `tests/test_app.py` does `from app import create_app`, which resolves via the current
directory.

```powershell
.\setup.cmd                          # create .venv and install requirements.lock.txt
.\run.cmd                            # serve on http://127.0.0.1:5050
.\run.cmd --port 5051                # if 5050 is busy
.\run.cmd --reset-demo --yes         # DELETES local tasks and reseeds Alice/Bob; stop the server first

.\.venv\Scripts\python.exe -m unittest discover -s tests -v            # full suite
.\.venv\Scripts\python.exe -m unittest discover -s tests -k csrf -v    # tests whose name contains "csrf"
.\.venv\Scripts\python.exe -m unittest tests.test_app.TaskerTests.test_missing_csrf_is_rejected_on_every_write_route -v
```

macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.lock.txt`,
then `python app.py` and `python -m unittest discover -s tests -v`.

There is no linter, formatter, pytest, or frontend build step configured; tests are stdlib `unittest`
only. `requirements.txt` records the direct dependencies (Flask and python-dotenv) and
`requirements.lock.txt` is the fully pinned set that `setup.cmd` and CI install. Update both
together when changing dependencies.

## Architecture

All server code is in `app.py`, built by the `create_app(test_config=None)` factory. Routes are
closures inside the factory; the module-level helpers (`get_db`, `seed_demo`, `read_or_create_key`,
`now`) are what the tests import and patch. `main()` owns the CLI flags (`--port`,
`--reset-demo`, `--yes`) and is called by the `__main__` block.

**Local settings.** `main()` loads the optional `.env` beside `app.py` using python-dotenv,
without overriding existing environment variables. Port priority is `--port`, `TASKER_PORT`
in the environment, `TASKER_PORT` in `.env`, then 5050. `.env` is ignored; `.env.example` is
the shared template. `OPENAI_API_KEY` is an unused placeholder for a future chatbot lesson;
no API calls or chatbot interface exist yet. Importing `create_app` does not load `.env`.

**Startup.** `create_app` creates `.instance/` (gitignored), reads or generates
`.instance/session.key` as `SECRET_KEY` unless the config supplies one, runs `schema.sql` (all
`CREATE ... IF NOT EXISTS`, so it is idempotent), and seeds the sample tasks when the `users` table
is empty. There is no migration system: a schema change must either be additive with
`IF NOT EXISTS` or require deleting/resetting `.instance/tasker.sqlite3`.

**Every request passes through `load_user_and_check_csrf`** (`before_request`):

- Static files are skipped.
- `GET /` with no valid session silently starts an Alice session (`user_id=1` plus a fresh
  `csrf_token`). No other endpoint does this, so hitting `/api/tasks` first returns 401.
- Any other endpoint without a valid session user aborts 401.
- Every `POST` must carry a `csrf_token` form field equal to the session's token, otherwise 400.
  Because this is global, a new POST route is protected automatically, but its form must include
  `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">` (exposed by the context
  processor).

**Ownership is enforced only server-side, through two helpers.** `user_tasks()` and
`owned_task(task_id)` scope every query to `g.user["id"]`. Another user's task yields 404 (not 403),
and query parameters such as `user_id=` are ignored everywhere. Any new route that reads or writes
tasks must go through these helpers; the tests assert the boundary from Bob's perspective.

**Request and response conventions.**

- HTML writes are plain forms. A `POST` validates, writes, then answers `303` back to `/` with the
  `filter` query parameter preserved (carried as a hidden input and sanitized by
  `selected_filter()`). Adding a task from the Completed view redirects to Open instead.
  Validation failures re-render the page with status 422 plus an `errors` dict and the submitted
  `form` values.
- `/api/*` and `/exports/*` get JSON error bodies; HTML routes render `error.html`. Both come from
  the shared `HTTPException` handler. `sqlite3.Error` maps to a generic 503 that logs only the
  exception type; tests check that internal messages never reach the response.
- The Content Security Policy is `script-src 'self'; style-src 'self'`, so templates may not
  contain inline `<script>`, inline `<style>`, or inline event handlers. Browser code goes in
  `static/*.js` and is loaded with `defer`.
- Dates are ISO strings in SQLite: `due_date` is `YYYY-MM-DD`; `created_at` and `completed_at`
  are UTC ISO seconds from `now()`. `completed` is an integer 0/1. The 1 to 100 character title
  rule is enforced both in `add_task` and by a `CHECK` constraint in `schema.sql`.
- The CSV export prepends a UTF-8 BOM and prefixes titles starting with `=`, `+`, `-`, or `@` with
  an apostrophe (spreadsheet formula guard). It always exports all of the current user's tasks
  regardless of the on-screen filter.

**Templates and static files.** `base.html` is the page frame plus the account switcher (a
`<details>` element containing one POST form per demo user); `index.html` holds the composer,
filters, and list; `icons.html` exposes an `icon(name)` macro, and adding an icon means adding an
`elif` branch there. `static/app.js` is optional progressive enhancement only (menu and notice
dismissal, a whitespace-only title check); every primary action must keep working with JavaScript
disabled. `static/agent-tools.js` registers a read-only WebMCP tool via
`document.modelContext.registerTool` that calls `/api/tasks`, and is a no-op in browsers without
that API.

## Tests

`tests/test_app.py` is a single `TaskerTests` class. `setUp` builds a fresh app per test with
`create_app({"TESTING": True, "DATABASE": <temp file>, "SECRET_KEY": ...})`, so the demo database
in `.instance/` is never touched. It prepares two clients, `self.alice` and `self.bob`, and a
`post()` helper that reads the CSRF token out of the session before posting; use it for any write
request in new tests.

`tests/test_startup.py` checks `main()` with temporary `.env` files and an isolated
environment. It replaces `create_app` so no server starts and no demo database is touched.

The tests assert on rendered copy, for example the empty-state heading "A fresh start", the eyebrow
"BOB'S WORKSPACE", and validation messages like "Choose a valid date". Changing user-facing strings
in `app.py` or the templates breaks tests until both are updated together.

CI (`.github/workflows/tests.yml`) checks the source out into a directory named `tasker demo` on
both Windows and Ubuntu, runs `setup.cmd` and then `run.cmd --help` from a different directory on
Windows, and runs the same `unittest discover` command on both. Anything that breaks under a path
containing spaces fails CI.
