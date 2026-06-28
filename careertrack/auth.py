from uuid import uuid4

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from .db import execute_write
from .models import User, get_user_by_email
from .utils import clean_text, is_safe_next_url


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

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
        return redirect(url_for("auth.login"))

    return render_template("register.html", form={})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

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
            return redirect(url_for("main.dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
