import os
from datetime import datetime
from uuid import uuid4

import snowflake.connector
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from snowflake.connector import DictCursor
from werkzeug.security import check_password_hash, generate_password_hash


load_dotenv()


STATUS_OPTIONS = [
    "Saved",
    "Applied",
    "Screening",
    "Interview",
    "Offer",
    "Rejected",
    "Withdrawn",
]

SUMMARY_STATUSES = ["Saved", "Applied", "Interview", "Offer", "Rejected"]


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"


class User(UserMixin):
    def __init__(self, user_id, email, name):
        self.id = user_id
        self.email = email
        self.name = name


def get_snowflake_connection():
    """Create a Snowflake connection from environment variables."""
    required = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
    ]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            "Missing Snowflake environment variables: " + ", ".join(missing)
        )

    connection_options = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA"),
    }

    role = os.getenv("SNOWFLAKE_ROLE")
    if role:
        connection_options["role"] = role

    return snowflake.connector.connect(**connection_options)


def fetch_one(sql, params=None):
    conn = get_snowflake_connection()
    cursor = conn.cursor(DictCursor)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def fetch_all(sql, params=None):
    conn = get_snowflake_connection()
    cursor = conn.cursor(DictCursor)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def execute_write(sql, params=None):
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params or ())
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def insert_activity(cursor, application_id, user_id, old_status, new_status, note):
    cursor.execute(
        """
        INSERT INTO APPLICATION_ACTIVITY
            (ID, APPLICATION_ID, USER_ID, OLD_STATUS, NEW_STATUS, NOTE, CREATED_AT)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
        """,
        (str(uuid4()), application_id, user_id, old_status, new_status, note),
    )


def get_user_by_id(user_id):
    row = fetch_one(
        """
        SELECT ID, EMAIL, NAME
        FROM USERS
        WHERE ID = %s
        """,
        (user_id,),
    )
    if not row:
        return None
    return User(row["ID"], row["EMAIL"], row["NAME"])


def get_user_by_email(email):
    return fetch_one(
        """
        SELECT ID, EMAIL, NAME, PASSWORD_HASH
        FROM USERS
        WHERE LOWER(EMAIL) = LOWER(%s)
        """,
        (email,),
    )


def get_application_or_404(application_id):
    application = fetch_one(
        """
        SELECT *
        FROM JOB_APPLICATIONS
        WHERE ID = %s AND USER_ID = %s
        """,
        (application_id, current_user.id),
    )
    if not application:
        flash("Application not found.", "warning")
        return None
    return application


def clean_text(value):
    value = (value or "").strip()
    return value or None


def form_payload():
    status = request.form.get("status", "Saved")
    if status not in STATUS_OPTIONS:
        status = "Saved"

    return {
        "company": clean_text(request.form.get("company")),
        "job_title": clean_text(request.form.get("job_title")),
        "job_location": clean_text(request.form.get("job_location")),
        "job_url": clean_text(request.form.get("job_url")),
        "status": status,
        "salary_range": clean_text(request.form.get("salary_range")),
        "applied_date": clean_text(request.form.get("applied_date")),
        "deadline_date": clean_text(request.form.get("deadline_date")),
        "notes": clean_text(request.form.get("notes")),
    }


def validate_application_payload(payload):
    errors = []
    if not payload["company"]:
        errors.append("Company is required.")
    if not payload["job_title"]:
        errors.append("Job title is required.")
    return errors


def parse_datetime_local(value):
    value = clean_text(value)
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M")


def is_safe_next_url(next_url):
    return bool(next_url) and next_url.startswith("/") and not next_url.startswith("//")


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(user_id)


@app.context_processor
def inject_global_template_data():
    return {"STATUS_OPTIONS": STATUS_OPTIONS}


@app.template_filter("display_date")
def display_date(value):
    if not value:
        return "Not set"
    if isinstance(value, str):
        return value[:10]
    return value.strftime("%b %d, %Y")


@app.template_filter("display_datetime")
def display_datetime(value):
    if not value:
        return "Not set"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime("%b %d, %Y at %I:%M %p")


@app.template_filter("date_input")
def date_input(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value[:10]
    return value.strftime("%Y-%m-%d")


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = clean_text(request.form.get("name"))
        email = clean_text(request.form.get("email"))
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if email and get_user_by_email(email):
            errors.append("An account already exists for that email.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("register.html", form=request.form)

        execute_write(
            """
            INSERT INTO USERS (ID, NAME, EMAIL, PASSWORD_HASH, CREATED_AT)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP())
            """,
            (
                str(uuid4()),
                name,
                email.lower(),
                generate_password_hash(password),
            ),
        )
        flash("Account created. You can log in now.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = clean_text(request.form.get("email"))
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"
        user_row = get_user_by_email(email) if email else None

        if user_row and check_password_hash(user_row["PASSWORD_HASH"], password):
            login_user(
                User(user_row["ID"], user_row["EMAIL"], user_row["NAME"]),
                remember=remember,
            )
            next_url = request.args.get("next")
            if is_safe_next_url(next_url):
                return redirect(next_url)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    rows = fetch_all(
        """
        SELECT STATUS, COUNT(*) AS COUNT_VALUE
        FROM JOB_APPLICATIONS
        WHERE USER_ID = %s
        GROUP BY STATUS
        """,
        (current_user.id,),
    )
    summary = {status: 0 for status in SUMMARY_STATUSES}
    total = 0
    for row in rows:
        count = int(row["COUNT_VALUE"])
        total += count
        if row["STATUS"] in summary:
            summary[row["STATUS"]] = count
    summary["Total"] = total

    recent_applications = fetch_all(
        """
        SELECT *
        FROM JOB_APPLICATIONS
        WHERE USER_ID = %s
        ORDER BY UPDATED_AT DESC
        LIMIT 5
        """,
        (current_user.id,),
    )
    upcoming_interviews = fetch_all(
        """
        SELECT
            I.ID,
            I.SCHEDULED_AT,
            I.INTERVIEW_TYPE,
            I.INTERVIEWER_NAME,
            I.OUTCOME,
            J.COMPANY,
            J.JOB_TITLE,
            J.ID AS APPLICATION_ID
        FROM INTERVIEWS I
        INNER JOIN JOB_APPLICATIONS J
            ON I.APPLICATION_ID = J.ID
        WHERE I.USER_ID = %s
        ORDER BY I.SCHEDULED_AT ASC NULLS LAST
        LIMIT 5
        """,
        (current_user.id,),
    )

    return render_template(
        "dashboard.html",
        summary=summary,
        recent_applications=recent_applications,
        upcoming_interviews=upcoming_interviews,
    )


@app.route("/applications")
@login_required
def applications():
    status = request.args.get("status", "")
    company = clean_text(request.args.get("company"))
    job_title = clean_text(request.args.get("job_title"))

    filters = ["USER_ID = %s"]
    params = [current_user.id]

    if status in STATUS_OPTIONS:
        filters.append("STATUS = %s")
        params.append(status)
    if company:
        filters.append("COMPANY ILIKE %s")
        params.append(f"%{company}%")
    if job_title:
        filters.append("JOB_TITLE ILIKE %s")
        params.append(f"%{job_title}%")

    sql = f"""
        SELECT *
        FROM JOB_APPLICATIONS
        WHERE {' AND '.join(filters)}
        ORDER BY UPDATED_AT DESC
    """
    application_rows = fetch_all(sql, tuple(params))

    return render_template(
        "applications.html",
        applications=application_rows,
        filters={"status": status, "company": company or "", "job_title": job_title or ""},
    )


@app.route("/applications/new", methods=["GET", "POST"])
@login_required
def new_application():
    if request.method == "POST":
        payload = form_payload()
        errors = validate_application_payload(payload)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "application_form.html",
                mode="new",
                application=request.form,
                action_url=url_for("new_application"),
            )

        application_id = str(uuid4())
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO JOB_APPLICATIONS (
                    ID, USER_ID, COMPANY, JOB_TITLE, JOB_LOCATION, JOB_URL,
                    STATUS, SALARY_RANGE, APPLIED_DATE, DEADLINE_DATE, NOTES,
                    CREATED_AT, UPDATED_AT
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
                )
                """,
                (
                    application_id,
                    current_user.id,
                    payload["company"],
                    payload["job_title"],
                    payload["job_location"],
                    payload["job_url"],
                    payload["status"],
                    payload["salary_range"],
                    payload["applied_date"],
                    payload["deadline_date"],
                    payload["notes"],
                ),
            )
            insert_activity(
                cursor,
                application_id,
                current_user.id,
                None,
                payload["status"],
                "Application created.",
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

        flash("Application added.", "success")
        return redirect(url_for("application_detail", application_id=application_id))

    return render_template(
        "application_form.html",
        mode="new",
        application={},
        action_url=url_for("new_application"),
    )


@app.route("/applications/<application_id>")
@login_required
def application_detail(application_id):
    application = get_application_or_404(application_id)
    if not application:
        return redirect(url_for("applications"))

    interviews = fetch_all(
        """
        SELECT *
        FROM INTERVIEWS
        WHERE APPLICATION_ID = %s AND USER_ID = %s
        ORDER BY SCHEDULED_AT ASC NULLS LAST, CREATED_AT DESC
        """,
        (application_id, current_user.id),
    )
    activities = fetch_all(
        """
        SELECT *
        FROM APPLICATION_ACTIVITY
        WHERE APPLICATION_ID = %s AND USER_ID = %s
        ORDER BY CREATED_AT DESC
        """,
        (application_id, current_user.id),
    )

    return render_template(
        "application_detail.html",
        application=application,
        interviews=interviews,
        activities=activities,
    )


@app.route("/applications/<application_id>/edit", methods=["GET", "POST"])
@login_required
def edit_application(application_id):
    application = get_application_or_404(application_id)
    if not application:
        return redirect(url_for("applications"))

    if request.method == "POST":
        payload = form_payload()
        errors = validate_application_payload(payload)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "application_form.html",
                mode="edit",
                application={**application, **request.form},
                action_url=url_for("edit_application", application_id=application_id),
            )

        old_status = application["STATUS"]
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE JOB_APPLICATIONS
                SET
                    COMPANY = %s,
                    JOB_TITLE = %s,
                    JOB_LOCATION = %s,
                    JOB_URL = %s,
                    STATUS = %s,
                    SALARY_RANGE = %s,
                    APPLIED_DATE = %s,
                    DEADLINE_DATE = %s,
                    NOTES = %s,
                    UPDATED_AT = CURRENT_TIMESTAMP()
                WHERE ID = %s AND USER_ID = %s
                """,
                (
                    payload["company"],
                    payload["job_title"],
                    payload["job_location"],
                    payload["job_url"],
                    payload["status"],
                    payload["salary_range"],
                    payload["applied_date"],
                    payload["deadline_date"],
                    payload["notes"],
                    application_id,
                    current_user.id,
                ),
            )
            if old_status != payload["status"]:
                insert_activity(
                    cursor,
                    application_id,
                    current_user.id,
                    old_status,
                    payload["status"],
                    f"Status changed from {old_status} to {payload['status']}.",
                )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

        flash("Application updated.", "success")
        return redirect(url_for("application_detail", application_id=application_id))

    return render_template(
        "application_form.html",
        mode="edit",
        application=application,
        action_url=url_for("edit_application", application_id=application_id),
    )


@app.route("/applications/<application_id>/delete", methods=["POST"])
@login_required
def delete_application(application_id):
    application = get_application_or_404(application_id)
    if not application:
        return redirect(url_for("applications"))

    conn = get_snowflake_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM INTERVIEWS WHERE APPLICATION_ID = %s AND USER_ID = %s",
            (application_id, current_user.id),
        )
        cursor.execute(
            """
            DELETE FROM APPLICATION_ACTIVITY
            WHERE APPLICATION_ID = %s AND USER_ID = %s
            """,
            (application_id, current_user.id),
        )
        cursor.execute(
            "DELETE FROM JOB_APPLICATIONS WHERE ID = %s AND USER_ID = %s",
            (application_id, current_user.id),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    flash("Application deleted.", "info")
    return redirect(url_for("applications"))


@app.route("/applications/<application_id>/interviews/new", methods=["GET", "POST"])
@login_required
def new_interview(application_id):
    application = get_application_or_404(application_id)
    if not application:
        return redirect(url_for("applications"))

    if request.method == "GET":
        return redirect(url_for("application_detail", application_id=application_id))

    interview_type = clean_text(request.form.get("interview_type"))
    scheduled_at_raw = request.form.get("scheduled_at")
    interviewer_name = clean_text(request.form.get("interviewer_name"))
    outcome = clean_text(request.form.get("outcome"))
    notes = clean_text(request.form.get("notes"))

    if not interview_type:
        flash("Interview type is required.", "danger")
        return redirect(url_for("application_detail", application_id=application_id))

    try:
        scheduled_at = parse_datetime_local(scheduled_at_raw)
    except ValueError:
        flash("Use a valid interview date and time.", "danger")
        return redirect(url_for("application_detail", application_id=application_id))

    execute_write(
        """
        INSERT INTO INTERVIEWS (
            ID, APPLICATION_ID, USER_ID, INTERVIEW_TYPE, SCHEDULED_AT,
            INTERVIEWER_NAME, OUTCOME, NOTES, CREATED_AT
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
        """,
        (
            str(uuid4()),
            application_id,
            current_user.id,
            interview_type,
            scheduled_at,
            interviewer_name,
            outcome,
            notes,
        ),
    )

    flash("Interview added.", "success")
    return redirect(url_for("application_detail", application_id=application_id))


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
