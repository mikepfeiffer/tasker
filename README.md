# Tasker

A small personal task tracker for the AI-assisted coding course. The same screen,
two fictional people, and a few familiar behaviors give every demo a shared context.

## Windows setup for the course

Install **Python 3.12** from [python.org](https://www.python.org/downloads/windows/),
including the Python launcher, and install [Git](https://git-scm.com/downloads/win).
Use Python 3.12 for the course to match the Windows and Linux CI checks.

In PowerShell or Command Prompt:

```powershell
git clone https://github.com/mikepfeiffer/tasker.git
cd tasker
.\setup.cmd
.\run.cmd
```

The repository is public, so cloning does not require signing in. To push your own
changes using GitHub CLI, run `gh auth login` and `gh auth setup-git` once on Windows.
The Mac's GitHub sign-in does not transfer to another machine.

`setup.cmd` creates a Windows virtual environment and installs the pinned
dependencies. It needs an internet connection on first setup. `run.cmd` starts
the app without downloading anything. Neither command requires activating a
PowerShell script or changing the machine's script-execution policy.

Open **http://127.0.0.1:5050** in Edge or Chrome. Keep the terminal open during the
demo and stop the server with Ctrl+C. On later runs, just use `.\run.cmd` from
the project folder. If port 5050 is busy, use `.\run.cmd --port 5051` and open
http://127.0.0.1:5051 instead.

The helpers also work when the project folder contains spaces. Keep the checkout
in a normal local folder, such as `C:\demos\tasker`. Clone the source and run setup
on each computer; don't copy a Mac `.venv` folder to Windows. Each computer creates
its own demo database and session key when Tasker first starts.

If you prefer individual commands instead of the helpers:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe app.py
```

## macOS / Linux setup

Python 3.12 is recommended. From this folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python app.py
```

Open **http://127.0.0.1:5050**. Stop the server with Ctrl+C.
If that port is busy, use `python app.py --port 5051`.
After the initial setup, activate the environment and run `python app.py` again.
`requirements.lock.txt` pins the course-demo dependencies; `requirements.txt`
records the app's direct dependencies.

## Local settings and the .env classroom demo

Tasker optionally reads a `.env` file beside `app.py` when started with `run.cmd`
or `python app.py`. Run `.\setup.cmd` again after updating an existing checkout to
install the added `python-dotenv` dependency. On macOS/Linux, use
`python -m pip install -r requirements.lock.txt`.
No `.env` file is required; the default port is 5050.

To prepare the demo, copy `.env.example` to `.env` if you do not already have one:

```powershell
Copy-Item .env.example .env
```

On macOS/Linux, use `cp .env.example .env`. Edit your local `.env`:

```dotenv
TASKER_PORT=5051
OPENAI_API_KEY=bogus-key-for-classroom-demo
```

Start Tasker with `.\run.cmd` (macOS/Linux: `python app.py`) and open
http://127.0.0.1:5051. Stop and restart the server after changing `.env`.
An explicit `--port` takes priority, followed by an existing `TASKER_PORT`
environment variable, then `.env`, then the default 5050. Ports must be whole
numbers from 1 to 65535.

`OPENAI_API_KEY` is a placeholder for a future chatbot interface. Tasker does not
use it or make API calls. A bogus value is enough for this lesson; keep the value
in `.env.example` blank. The existing session key still lives in
`.instance/session.key`.

Show students these existing `.gitignore` rules:

```gitignore
.env
.env.*
!.env.example
```

Then demonstrate the difference between shared configuration and local values:

```powershell
git check-ignore -v .env
git status --short --ignored -- .env .env.example
```

The first command identifies the rule that excludes `.env`; the second marks it
with `!!` (ignored). `.env.example` is allowed in Git so everyone has a template.
Commit the template and application code, and keep personal settings and keys in
the ignored `.env`. Ignoring a file does not encrypt it or remove it from Git if
it was already tracked.

## What it does

- Starts with Alice's sample tasks. Switch to Bob from the account menu.
- Adds a task with a title and an optional due date.
- Marks a task complete and reopens it.
- Filters all, open, completed, and Due today tasks, with counts.
- Due today (`/?filter=today`) shows your open tasks due on the computer's local
  calendar date. Adding or completing a task keeps this view selected; tasks with
  another date or no date are saved but do not appear here.
- Downloads the current person's complete task history as a CSV spreadsheet file.
- Saves tasks in `.instance/tasker.sqlite3`, including across server restarts.

All primary actions work without JavaScript. The small script adds menu dismissal,
notification dismissal, and an extra check for blank task titles.

## Demo accounts and boundaries

**This is a local teaching app, not a production authentication system.** The menu
intentionally lets anyone at this computer choose Alice or Bob without a password.
The home page starts an Alice session automatically. It uses only fictional data
and binds to `127.0.0.1` by default.

Once a demo account is selected, the server enforces that account's ownership of
tasks. Changing a task ID or adding `?user_id=1` to an export does not grant access
to another account's records. The account switcher demonstrates identity selection;
it is not proof that a visitor is Alice or Bob.

The app uses a signed session cookie, CSRF checks on forms, parameterized SQL,
escaped HTML, and CSV formula-prefix protection. A generated session-signing key
lives in `.instance/session.key`, outside the tracked source. No real services,
cloud credentials, external fonts, analytics, or AI API keys are needed.

Before any shared or public deployment, replace demo identity selection with real
authentication, configure HTTPS cookies and allowed hosts, and use a production
server. These changes are outside this local starter's scope.

## Small code map

| File | Purpose |
| --- | --- |
| `app.py` | Routes, validation, account ownership, database access, and CSV export |
| `schema.sql` | The users and tasks tables |
| `templates/index.html` | Task form, filters, and list |
| `templates/base.html` | Page frame and demo-account menu |
| `templates/icons.html` | Small interface icons |
| `static/style.css` | Responsive layout and colors |
| `static/app.js` | Optional browser conveniences |
| `static/agent-tools.js` | Optional read-only task tool for browsers with WebMCP support |
| `tests/test_app.py` | Observable acceptance and access-boundary checks |
| `tests/test_startup.py` | Local settings, port precedence, and startup validation |

Flask serves the app, and `python-dotenv` loads optional local settings. SQLite,
CSV handling, and the test runner are included with Python. There is no frontend
build step.

## Run the checks

On Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On macOS/Linux, with the virtual environment active:

```sh
python -m unittest discover -s tests -v
```

Tests use a separate temporary database. They do not alter the demo's saved tasks.
They cover persistence, exact title-length boundaries, date validation, completion,
filters, account separation, exports, HTML escaping, request protection, empty
accounts, a controlled database failure, Unicode CSV downloads, and generated
session keys in folders containing spaces and non-ASCII text. Startup checks cover
local settings, port precedence, and invalid ports. Passing these checks establishes the
specified cases, not a general production-security guarantee.

GitHub Actions runs the checks on Windows and Linux using Python 3.12. The Windows
job also runs the actual setup helper and checks the launcher from outside the
project directory. Both jobs check out the source into a folder containing spaces.

### GitHub Actions: tests and security

[`.github/workflows/tests.yml`](.github/workflows/tests.yml) defines the **Tests and
security** workflow. It runs on pushes to `main`, pull requests, and manual runs
from **Actions → Tests and security → Run workflow**.

| Trigger | Windows and Linux tests | CodeQL | Dependency review |
| --- | --- | --- | --- |
| Pull request | Run | After tests pass | After tests pass |
| Push or merge to `main` | Skip | Run | Skip |
| Manual run | Run | After tests pass | Skip |

1. **Unit tests:** run the existing checks on Windows and Linux with Python 3.12
   before merging a pull request, or when started manually. They do not repeat
   after a merge to `main`; configure branch protection below to require them
   before merging.
2. **CodeQL:** scans the Python source with the default security queries. On PRs
   and manual runs, `needs: run-app-tests` waits for both test jobs to pass; if
   tests fail, the scan is skipped. On pushes to `main`, the scan runs even though
   the test jobs are skipped, keeping the default branch's security alerts current.
   Python needs no build step. Canceling the workflow also prevents the scan from
   starting.
3. **Dependency review:** on pull requests, another job runs after the tests and
   checks added or updated packages against known vulnerability advisories. It
   fails for any severity (`low` or higher), across all dependency scopes. It runs
   alongside CodeQL and needs only the workflow's read access to repository content.

Tests execute specific examples; CodeQL looks for unsafe patterns and data flows
in Python source code. CodeQL results appear under **Security → Code scanning** and on pull
requests. A successful analysis job means the scan completed; the separate
**Code scanning results / CodeQL** PR check fails for high or critical security
findings by default. See [GitHub's explanation of scan checks](https://docs.github.com/en/code-security/how-tos/manage-security-alerts/manage-code-scanning-alerts/triage-alerts-in-pull-requests).

This workflow uses CodeQL **advanced setup**. Keep default setup disabled to avoid
conflicting uploads. CodeQL is free for this public repository; private copies
need an eligible organization plan with GitHub Code Security enabled. See
[GitHub's setup requirements](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/configure-code-scanning/configuring-advanced-setup-for-code-scanning).

Dependency review is **Software Composition Analysis (SCA)**: it checks third-party
package versions using GitHub's dependency graph and advisory data. Enable
**Settings → Advanced Security → Dependency graph** before the first run. Open
the PR's **Dependency review (third-party packages)** job to see its summary.
This review compares dependency changes in the PR. It skips pushes and manual
runs, and does not audit unchanged packages. Dependabot alerts provide ongoing
checks for vulnerabilities in existing dependencies. See
[GitHub's dependency review documentation](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review).

### Branch protection for your own GitHub repository

If you fork this repository or publish a clone to your own GitHub repository,
configure branch protection there. These rules live in GitHub settings, not in
the workflow file, and cloning the code does not configure them for you.

1. Enable workflows in the **Actions** tab if prompted. Open a pull request in
   your repository and let the **Tests and security** workflow pass once so GitHub
   can offer its check names in the settings.
2. Go to **Settings → Branches**. Under **Branch protection rules**, choose
   **Add classic branch protection rule**, or edit an existing rule for `main`.
   Use `main` as the branch name pattern.
3. Enable **Require a pull request before merging**. For a solo course repository,
   leave **Require approvals** unchecked so you can merge your own PRs.
4. Enable **Require status checks to pass before merging**, then enable
   **Require branches to be up to date before merging**. Select both
   **Run app tests (Windows)** and **Run app tests (Linux)**.
5. To enforce the rule for your administrator account too, enable
   **Do not allow bypassing the above settings**.
6. Save the rule using **Create** or **Save changes**.

Both tests must pass against the latest `main` before merging. If another PR is
merged first, update your PR branch and let the checks run again. The setup above
requires the app tests; CodeQL and dependency review still run on PRs, but are not
made required by these selections. A successful CodeQL analysis job is separate
from its findings check, as explained above.

Branch protection is available for public repositories on GitHub Free; private
repositories need an eligible paid plan. See [GitHub's branch protection instructions](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule).

## Reset for another recording

Stop the server first. This command **deletes all local tasks** and restores fresh
Alice and Bob examples with due dates relative to the day of the reset:

Windows:

```powershell
.\run.cmd --reset-demo --yes
.\run.cmd
```

macOS/Linux:

```sh
python app.py --reset-demo --yes
python app.py
```

## Simple classroom walkthrough

Before recording, run setup and the checks on the Windows machine once. Start the
app, verify this walkthrough in the browser you will use on camera, and reset the
sample data if you want due dates relative to the recording day. Once dependencies
are installed, Tasker runs without internet access.

1. Open Alice's list and add “Prepare the course demo.”
2. Mark it complete, select **Completed**, then reopen it.
3. Download the history and inspect the spreadsheet.
4. Switch to Bob and observe that Alice's task is absent.
5. Switch back to Alice and reload: the task is still saved.

For code-review lessons, the read-only JSON routes make ownership easy to inspect:
`GET /api/tasks` and `GET /api/tasks/<id>`. Open the app first to establish the demo
session. A request for another user's task returns 404; an unauthenticated API or
export request returns 401. The CSV export always includes all of the current
user's tasks, regardless of the selected screen filter.

This is the working reference app. Deliberately broken variants and per-lesson
checkpoints can be prepared separately; no intentional vulnerabilities are built
into the default application.

Framework references: [Flask installation](https://flask.palletsprojects.com/en/stable/installation/),
[security considerations](https://flask.palletsprojects.com/en/stable/web-security/),
and [release notes](https://flask.palletsprojects.com/en/stable/changes/).
Python's [virtual-environment documentation](https://docs.python.org/3.12/library/venv.html)
explains why environments are recreated per machine and why activation is optional.
