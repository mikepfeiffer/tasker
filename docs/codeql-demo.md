# CodeQL lesson: passing tests can miss a security flaw

This lesson branch adds optional title search to `GET /api/tasks?q=demo`. The
regular app and its clean security baseline remain on `main`.

The first lesson commit deliberately inserts the request's `q` value into a SQL
string. An ordinary search test passes, but CodeQL should identify SQL injection.
This is an intentionally vulnerable teaching checkpoint and should not be merged.

The follow-up commit will bind the search value as a SQL parameter and add a
regression test for quotes and SQL-injection input. Both commits and their GitHub
check results will remain available for the recorded walkthrough.

## What to explain

- Unit tests run concrete examples. An ordinary search can work while an unsafe
  input changes the meaning of the SQL query.
- CodeQL follows request data into the SQL execution call without starting the app.
- SQL parameters keep the search value as data instead of SQL instructions.
- The analysis job reports that scanning completed. The separate **Code scanning
  results / CodeQL** pull-request check reports security findings.
