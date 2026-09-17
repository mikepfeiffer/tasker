# CodeQL lesson: passing tests can miss a security flaw

This lesson branch adds optional title search to `GET /api/tasks?q=demo`. The
regular app and its clean security baseline remain on `main`.

The first lesson commit (`bbe22b4`) deliberately inserts the request's `q` value
into a SQL string. All 15 tests passed on Windows and Linux, but CodeQL detected
`py/sql-injection` with high severity and failed the PR's security results check.
That historical commit is intentionally vulnerable teaching code.

The follow-up commit binds the search value as a SQL parameter and adds a regression
test for quotes and SQL-injection input. The regression test failed against the
unsafe code before the fix. The branch now contains the corrected implementation.

## Two-minute walkthrough

Open these pages before recording. The recorded results require no live workflow run.

1. **Baseline (15 seconds):** show the
   [clean main workflow run](https://github.com/mikepfeiffer/tasker/actions/runs/35010400658).
   Windows and Linux tests finish before the CodeQL job starts.
2. **Finding (45 seconds):** show the
   [failed CodeQL check](https://github.com/mikepfeiffer/tasker/runs/104521978341).
   It reports one high-severity security vulnerability, even though the
   [same commit's unit tests passed](https://github.com/mikepfeiffer/tasker/actions/runs/35010611435).
   Expand the SQL-injection annotation to trace request input into the query.
3. **Fix (30 seconds):** open the fix commit from the
   [PR's commits](https://github.com/mikepfeiffer/tasker/pull/4/commits).
   Show the SQL placeholder and separately bound search value, then the regression
   test for `Bob's` and SQL-injection input.
4. **Outcome (30 seconds):** show the
   [PR's latest checks](https://github.com/mikepfeiffer/tasker/pull/4/checks).
   The corrected version has 16 tests, including the added regression test.

Use the historical failed-check link in step 2 to show the red result after the fix;
the PR's current checks reflect its latest commit. GitHub Actions logs have a
retention period, so use these run links for the upcoming recording.

## What to explain

- Unit tests run concrete examples. An ordinary search can work while an unsafe
  input changes the meaning of the SQL query.
- CodeQL follows request data into the SQL execution call without starting the app.
- SQL parameters keep the search value as data instead of SQL instructions.
- The analysis job reports that scanning completed. The separate **Code scanning
  results / CodeQL** pull-request check reports security findings.
