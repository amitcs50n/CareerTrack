# CareerTrack

CareerTrack is a Flask and Snowflake job application tracker built as a clean portfolio MVP. It supports account registration, login, application CRUD, search and filters, interview tracking, dashboard metrics, and an activity log for status changes.

## Tech Stack

- Python Flask
- Snowflake with `snowflake-connector-python`
- Flask-Login
- Werkzeug password hashing
- python-dotenv
- Bootstrap and Jinja templates

## Project Structure

```text
CareerTrack/
  app.py
  requirements.txt
  .env.example
  README.md
  sql/schema.sql
  static/css/style.css
  templates/
    base.html
    login.html
    register.html
    dashboard.html
    applications.html
    application_form.html
    application_detail.html
```

## Snowflake Setup

1. Log in to Snowflake with an account that can create a database, warehouse, schema, and tables.
2. Open a Snowflake worksheet.
3. Run the SQL in `sql/schema.sql`.
4. Create or choose an application user/role that has access to `CAREERTRACK_DB.APP`.

The schema script creates:

- `USERS`
- `JOB_APPLICATIONS`
- `INTERVIEWS`
- `APPLICATION_ACTIVITY`

Snowflake standard table constraints are informational in many accounts, so the Flask app also checks ownership and email uniqueness in application code.

## Local Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your real Snowflake settings. Do not commit `.env`.

Run the app:

```bash
flask --app app run --debug
```

Then open:

```text
http://127.0.0.1:5000
```

## Routes

- `/` redirects to login or dashboard
- `/register` creates a user account
- `/login` logs in a user
- `/logout` logs out a user
- `/dashboard` shows summary cards, recent applications, and upcoming interviews
- `/applications` lists applications with status, company, and job title filters
- `/applications/new` creates an application
- `/applications/<application_id>` shows application details, interviews, and activity
- `/applications/<application_id>/edit` edits an application
- `/applications/<application_id>/delete` deletes an application
- `/applications/<application_id>/interviews/new` adds an interview

## Security Notes

- Snowflake credentials are read from environment variables.
- Passwords are stored with Werkzeug password hashes only.
- All SQL statements use Snowflake connector bind parameters.
- Every application, interview, and activity query is scoped to the logged-in user's UUID.
- The delete route accepts POST only.

## Status Values

- Saved
- Applied
- Screening
- Interview
- Offer
- Rejected
- Withdrawn

## Portfolio Extension Ideas

- Add pagination for large application lists.
- Add resume and cover letter upload storage.
- Add email reminders for interviews.
- Add charts for application funnel trends.
- Add admin-only demo data seeding.
