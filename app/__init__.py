from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Config
from app.services.database import get_db
from app.services.logging_service import setup_logging
from app.services.schedule_service import setup_schedulers

import pytz
import os
import threading

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}}) # for development
    JWTManager(app)
    setup_logging()

    # blueprints
    from app.routes.auth import auth_bp
    from app.routes.users import users_bp
    from app.routes.venues import venues_bp
    from app.routes.items import items_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(venues_bp, url_prefix='/api/venues')
    app.register_blueprint(items_bp, url_prefix='/api/items')

    # scheduler
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Jerusalem'))
        threading.Thread(target=setup_schedulers, args=(scheduler,), daemon=True).start()

    return app