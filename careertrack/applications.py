from uuid import uuid4

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .constants import STATUS_OPTIONS
from .db import execute_write, fetch_all, fetch_one, get_snowflake_connection
from .utils import clean_text, parse_datetime_local


applications_bp = Blueprint("applications", __name__)


def insert_activity(cursor, application_id, user_id, old_status, new_status, note):
    cursor.execute(
        """
        INSERT INTO APPLICATION_ACTIVITY
            (ID, APPLICATION_ID, USER_ID, OLD_STATUS, NEW_STATUS, NOTE, CREATED_AT)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
        """,
        (str(uuid4()), application_id, user_id, old_status, new_status, note),
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


@applications_bp.route("/applications")
@login_required
def list_applications():
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
        filters={
            "status": status,
            "company": company or "",
            "job_title": job_title or "",
        },
    )


@applications_bp.route("/applications/new", methods=["GET", "POST"])
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
                action_url=url_for("applications.new_application"),
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
        return redirect(
            url_for("applications.application_detail", application_id=application_id)
        )

    return render_template(
        "application_form.html",
        mode="new",
        application={},
        action_url=url_for("applications.new_application"),
    )


@applications_bp.route("/applications/<application_id>")
@login_required
def application_detail(application_id):
    application = get_application_or_404(application_id)
    if not application:
        return redirect(url_for("applications.list_applications"))

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


@applications_bp.route("/applications/<application_id>/edit", methods=["GET", "POST"])
@login_required
def edit_application(application_id):
    application = get_application_or_404(application_id)
    if not application:
        return redirect(url_for("applications.list_applications"))

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
                action_url=url_for(
                    "applications.edit_application", application_id=application_id
                ),
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
        return redirect(
            url_for("applications.application_detail", application_id=application_id)
        )

    return render_template(
        "application_form.html",
        mode="edit",
        application=application,
        action_url=url_for("applications.edit_application", application_id=application_id),
    )


@applications_bp.route("/applications/<application_id>/delete", methods=["POST"])
@login_required
def delete_application(application_id):
    application = get_application_or_404(application_id)
    if not application:
        return redirect(url_for("applications.list_applications"))

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
    return redirect(url_for("applications.list_applications"))


@applications_bp.route("/applications/<application_id>/interviews/new", methods=["GET", "POST"])
@login_required
def new_interview(application_id):
    application = get_application_or_404(application_id)
    if not application:
        return redirect(url_for("applications.list_applications"))

    if request.method == "GET":
        return redirect(
            url_for("applications.application_detail", application_id=application_id)
        )

    interview_type = clean_text(request.form.get("interview_type"))
    scheduled_at_raw = request.form.get("scheduled_at")
    interviewer_name = clean_text(request.form.get("interviewer_name"))
    outcome = clean_text(request.form.get("outcome"))
    notes = clean_text(request.form.get("notes"))

    if not interview_type:
        flash("Interview type is required.", "danger")
        return redirect(
            url_for("applications.application_detail", application_id=application_id)
        )

    try:
        scheduled_at = parse_datetime_local(scheduled_at_raw)
    except ValueError:
        flash("Use a valid interview date and time.", "danger")
        return redirect(
            url_for("applications.application_detail", application_id=application_id)
        )

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
    return redirect(
        url_for("applications.application_detail", application_id=application_id)
    )
