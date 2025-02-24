from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from werkzeug.security import check_password_hash
from app.services.database import get_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login_user():
    try:
        username = request.json.get('username')
        password = request.json.get('password')
        db = get_db()
        user = db.users.find_one({"username": username})

        if not user or not check_password_hash(user['password'], password):
            return jsonify({"error": "Invalid username or password"}), 401

        venue = db.venue_settings.find_one({"venue_id": user['venue_id']})
        if not venue:
            return jsonify({"error": "Venue not found"}), 404

        additional_claims = {
            "venue_id": user['venue_id'],
            "venue_name": venue['venue_name'],
            "venue_logo": venue['venue_logo'],
            "role": user['role']
        }

        access_token = create_access_token(identity=username, additional_claims=additional_claims)
        return jsonify(access_token=access_token), 200
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route('/user', methods=['GET'])
@jwt_required()
def get_user():
    current_user = get_jwt_identity()
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    db = get_db()

    user_document = db.users.find_one({'username': current_user})
    if not user_document:
        return jsonify({"error": "User not found"}), 404

    jwt_venue = get_jwt().get('venue_id')
    jwt_role = get_jwt().get('role')

    if user_document['venue_id'] != jwt_venue or user_document['role'] != jwt_role:
        venue_settings = db.venue_settings.find_one({"venue_id": user_document['venue_id']})
        new_claims = {
            "venue_id": user_document['venue_id'],
            "venue_name": venue_settings['venue_name'] if venue_settings else "Unknown Venue",
            "venue_logo": venue_settings['venue_logo'] if venue_settings else "",
            "role": user_document['role']
        }
        new_access_token = create_access_token(identity=current_user, additional_claims=new_claims)
        return jsonify({
            "error": "Claims mismatch, re-new token",
            "new_access_token": new_access_token
        }), 401

    if user_document['venue_id'] != "all":
        venue_settings = db.venue_settings.find_one({"venue_id": user_document['venue_id']})
        if not venue_settings:
            return jsonify({"error": "Venue not found"}), 404

    if not user_document.get('firstLogin', False):
        user_document['firstLogin'] = True
        db.users.update_one({'username': current_user}, {'$set': {'firstLogin': True}})

    db.users.update_one(
        {'username': current_user},
        {'$set': {'last_seen': datetime.utcnow(), 'ip_address': client_ip}},
        upsert=True
    )

    return jsonify({
        "logged_in_as": current_user,
        "role": user_document['role'],
        "venue": "all" if user_document['role'] == "administrator" else user_document['venue_id']
    }), 200

@auth_bp.route('/set-venue/<venue_id>', methods=['PUT'])
@jwt_required()
def set_venue_for_user(venue_id):
    claims = get_jwt()
    if claims.get('role') != "administrator":
        return jsonify({"error": "Unauthorized"}), 403

    db = get_db()
    user_document = db.users.find_one({'username': get_jwt_identity()})
    if not user_document:
        return jsonify({"error": "User not found"}), 404

    venue_settings = db.venue_settings.find_one({"venue_id": venue_id})
    if not venue_settings:
        return jsonify({"error": "Venue not found"}), 404

    db.users.update_one({'username': get_jwt_identity()}, {'$set': {'venue_id': venue_id}})
    return jsonify({"message": "Venue set successfully"}), 200