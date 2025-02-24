from flask import Blueprint

auth_bp = Blueprint('auth', __name__)
users_bp = Blueprint('users', __name__)
venues_bp = Blueprint('venues', __name__)
items_bp = Blueprint('items', __name__)