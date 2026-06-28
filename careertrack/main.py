from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from .constants import SUMMARY_STATUSES
from .db import fetch_all


main_bp = Blueprint("main", __name__)


@main_bp.route("/health")
def health():
    return {"status": "ok"}


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
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
