import os

from dotenv import load_dotenv
from flask import Flask

from .constants import STATUS_OPTIONS
from .extensions import login_manager
from .models import get_user_by_id
from .template_filters import date_input, display_date, display_datetime


def create_app():
    load_dotenv()

    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(user_id)

    @app.context_processor
    def inject_global_template_data():
        return {"STATUS_OPTIONS": STATUS_OPTIONS}

    app.add_template_filter(display_date, "display_date")
    app.add_template_filter(display_datetime, "display_datetime")
    app.add_template_filter(date_input, "date_input")

    from .applications import applications_bp
    from .auth import auth_bp
    from .main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(applications_bp)

    return app
