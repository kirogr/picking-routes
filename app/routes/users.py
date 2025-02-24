from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.services.database import get_db
from app.utils.helpers import logdb_users_history
from bson import ObjectId

users_bp = Blueprint('users', __name__)


@users_bp.route('/', methods=['GET'])
@jwt_required()
def get_users():
    current_user = get_jwt_identity()
    db = get_db()
    user_document = db.users.find_one({'username': current_user})

    if not user_document:
        return jsonify({"error": "User not found"}), 404

    if user_document['role'] == 'administrator':
        users = list(db.users.find({}, {'password': 0}))
    elif user_document['role'] == 'venue_manager':
        venue_id = user_document.get('venue_id')
        users = list(db.users.find({'venue_id': venue_id, 'role': {'$ne': 'administrator'}}, {'password': 0}))
    else:
        return jsonify({"error": "Unauthorized"}), 403

    for user in users:
        user['_id'] = str(user['_id'])
        user["venue_name"] = "All venues" if user["role"] == "administrator" else \
        db.venue_settings.find_one({"venue_id": user["venue_id"]})['venue_name']
        user['can_edit'] = user_document['role'] == 'administrator' or (
                    user['role'] != 'administrator' and user.get('venue_id') == venue_id)
        user.pop('password', None)
        user.pop('ip_address', None)

    return jsonify(users), 200

@users_bp.route('/<user_id>/reset-password', methods=['POST'])
@jwt_required()
def reset_password(user_id):
    db = get_db()
    db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'password': 'new_password'}})
    return jsonify({"message": "Password reset successfully"}), 200

@users_bp.route('/<user_id>/delete', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    db = get_db()

    current_user = get_jwt_identity()
    user_document = db.users.find_one({'username': current_user})
    if not user_document:
        return jsonify({"error": "User not found"}), 404

    # validate if the user exists
    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        logdb_users_history(db, ObjectId(user_document['_id']), 'delete_user', None, f'User {user_id} not found', 'failed')
        return jsonify({"error": "User not found"}), 404

    if user_document['role'] not in ['administrator', 'venue_manager']:
        logdb_users_history(db, ObjectId(user_document['_id']), 'delete_user', ObjectId(user['_id']), "Unauthorized", 'failed')
        return jsonify({"error": "Unauthorized"}), 403

    if user['username'] == current_user:
        logdb_users_history(db, ObjectId(user_document['_id']), 'delete_user', ObjectId(user['_id']), "Cannot delete yourself", 'failed')
        return jsonify({"error": "Cannot delete yourself"}), 403

    if user.get('is_dev') == True:
        logdb_users_history(db, ObjectId(user_document['_id']), 'delete_user', ObjectId(user['_id']), "Cannot delete a developer", 'failed')
        return jsonify({"error": "Insufficient permissions"}), 403

    db.users.delete_one({'_id': ObjectId(user_id)})
    logdb_users_history(db, ObjectId(user_document['_id']), 'delete_user', ObjectId(user['_id']), f"User {user['_id']} deleted successfully")
    return jsonify({"message": "User deleted successfully"}), 200

@users_bp.route('/<user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    current_user = get_jwt_identity()
    db = get_db()

    try:
        user_id = ObjectId(user_id)
    except:
        return jsonify({"error": "Invalid user ID"}), 400

    user_document = db.users.find_one({'username': current_user})

    sender_id = ObjectId(user_document['_id'])

    if not user_document:
        return jsonify({"error": "User not found"}), 404

    is_admin = user_document['role'] == 'administrator'
    is_venue_manager = user_document['role'] == 'venue_manager'
    is_dev = user_document.get('is_dev')

    if not is_admin and not is_venue_manager:
        logdb_users_history(db, sender_id, "update_user", None, "Unauthorized (privilege escalation)", "failed")
        return jsonify({"error": "Unauthorized"}), 403

    user = db.users.find_one({'_id': user_id})
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user['username'] == current_user:
        logdb_users_history(db, sender_id, "update_user", user_id, "Cannot modify yourself", "failed")
        return jsonify({"error": "Unauthorized: Cannot modify yourself"}), 403

    if user['role'] == 'administrator' and not is_dev:
        logdb_users_history(db, sender_id, "update_user", user_id, "Cannot modify an administrator", "failed")
        return jsonify({"error": "Unauthorized: Cannot modify an administrator"}), 403

    update_data = request.json
    allowed_fields = {'role', 'username'}
    filtered_data = {key: update_data[key] for key in update_data if key in allowed_fields}

    if not filtered_data:
        logdb_users_history(db, sender_id, "update_user", user_id, "No valid fields provided", "failed")
        return jsonify({"error": "No valid fields provided"}), 400

    if is_venue_manager and 'role' in filtered_data and filtered_data['role'] == 'administrator':
        return jsonify({"error": "Unauthorized"}), 403

    db.users.update_one({'_id': user_id}, {'$set': filtered_data})
    logdb_users_history(db, sender_id, "update_user", user_id, f"Updated user: {filtered_data}")

    return jsonify({"message": "User updated successfully"}), 200

@users_bp.route('/add', methods=['POST'])
@jwt_required()
def add_user():
    current_user = get_jwt_identity()
    db = get_db()

    user_document = db.users.find_one({'username': current_user})

    if not user_document:
        return jsonify({"error": "User not found"}), 404

    is_admin = user_document['role'] == 'administrator'
    is_venue_manager = user_document['role'] == 'venue_manager'

    if not is_admin and not is_venue_manager:
        logdb_users_history(db, ObjectId(user_document['_id']), "add_user", None, "Unauthorized (privilege escalation)", "failed")

        return jsonify({"error": "Unauthorized"}), 403
    new_user = request.json

    if not new_user.get('username') or not new_user.get('password') or not new_user.get('role'):
        logdb_users_history(db, ObjectId(user_document['_id']), "add_user", None, "Missing required fields", "failed")
        return jsonify({"error": "Missing required fields"}), 400

    if is_venue_manager and new_user['role'] == 'administrator':
        logdb_users_history(db, ObjectId(user_document['_id']), "add_user", None, "Venue managers cannot assign administrator roles", "failed")
        return jsonify({"error": "Unauthorized: Venue managers cannot assign administrator roles"}), 403

    if new_user['role'] == 'venue_manager' and not new_user.get('venue_id'):
        logdb_users_history(db, ObjectId(user_document['_id']), "add_user", None, "Missing required fields", "failed")
        return jsonify({"error": "Missing required fields"}), 400

    db.users.insert_one({
        'username': new_user['username'],
        'email': new_user["email"],
        'password': new_user['password'],
        'role': new_user['role'],
        'venue_id': user_document['venue_id'],
        'last_seen': None,
        'firstLogin': False
    })

    logdb_users_history(db, ObjectId(user_document['_id']), "add_user", None, f"Added user: {new_user['username']} with \"{new_user['role']}\" role to venue \"{user_document['venue_id']}\"")

    return jsonify({"message": "User added successfully"}), 200