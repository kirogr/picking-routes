import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app.services.database import get_db
from app.models import serialize_document
import pytz
from datetime import datetime, timedelta

venues_bp = Blueprint('venues', __name__)


@venues_bp.route('/', methods=['GET'])
@jwt_required()
def get_all_venues():
    db = get_db()
    current_user = get_jwt_identity()
    user_document = db.users.find_one({'username': current_user})

    if not user_document:
        return jsonify({"error": "User not found"}), 404

    if user_document.get('role') != "administrator":
        return jsonify({"error": "Unauthorized"}), 403

    tz = pytz.timezone('Asia/Jerusalem')
    now = datetime.now(tz)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    venues = db.venue_settings.find({})
    venue_list = []

    for venue in venues:
        venue_id = venue["venue_id"]

        today_assigned_count = db.item_updates.count_documents({
            "timestamp": {"$gte": start_of_today, "$lte": end_of_today},
            "venue": venue_id
        })

        # when the picking areas of the venue was last updated...
        last_picking_areas_update = db.picking_areas.find_one({"venue_id": venue_id})['last_updated']
        last_itemconfigs_update = db.item_configs.find_one({"venue_id": venue_id})['last_updated']

        # how many users are assigned to this venue
        users_assigned = db.users.count_documents({"venue_id": venue_id})

        venue_data = serialize_document(venue)
        venue_data["usersAssignedCount"] = users_assigned
        venue_data["itemsAssignedToday"] = str(today_assigned_count)
        venue_data["lastItemConfigsUpdate"] = last_itemconfigs_update
        venue_data["lastPickingAreasUpdate"] = last_picking_areas_update
        venue_data['nextPickingAreasUpdate'] = last_picking_areas_update + timedelta(days=3)
        venue_data['scheduleType'] = venue['schedule']['scheduleType']
        venue_list.append(venue_data)

    return jsonify(venue_list), 200

@venues_bp.route('/<venue_id>', methods=['PUT'])
@jwt_required()
def update_venue(venue_id):
    claims = get_jwt()
    if claims.get('role') != 'administrator':
        return jsonify({"error": "Unauthorized"}), 403

    db = get_db()
    update_data = request.json

    # check if the venue exists
    if not db.venue_settings.find_one({"venue_id": venue_id}):
        return jsonify({"error": "Venue not found"}), 404

    update_data.pop("_id", None)

    allowed_fields = {
        "venue_id": str,
        "venue_name": str,
        "venue_logo": str,
        "endpoints": dict,
        "binMappings": list,
        "locationTransformations": list,
        "overflowLocations": list,
        "venue_message": dict,
    }

    cleaned_data = {}
    for field, expected_type in allowed_fields.items():
        if field in update_data:
            if not isinstance(update_data[field], expected_type):
                return jsonify({
                    "error": f"Invalid type for field '{field}'. Expected {expected_type.__name__}"
                }), 400
            cleaned_data[field] = update_data[field]

    if "endpoints" in cleaned_data:
        required_endpoints = {
            "ALL_ITEMS_INFORMATION_ENDPOINT": str,
            "BASE_URL": str,
            "ITEM_CONFIG_ENDPOINT": str,
            "MENU_ID": str,
            "UNASSIGNED_ITEMS_ENDPOINT": str,
            "VENUE_ID": str
        }

        for endpoint, expected_type in required_endpoints.items():
            if endpoint not in cleaned_data["endpoints"]:
                return jsonify({
                    "error": f"Missing required endpoint: {endpoint}"
                }), 400
            if not isinstance(cleaned_data["endpoints"][endpoint], expected_type):
                return jsonify({
                    "error": f"Invalid type for endpoint '{endpoint}'. Expected {expected_type.__name__}"
                }), 400

        if update_data['venue_id'] == "":
            return jsonify({"error": "Venue ID cannot be empty"}), 400

        if not re.match("^[a-zA-Z0-9_-]*$", update_data['venue_id']):
            return jsonify({"error": "Venue ID must contain only alphanumeric characters, - or _"}), 400

        users_assigned = db.users.count_documents({"venue_id": venue_id})
        if users_assigned > 0 and venue_id != update_data['venue_id']:
            return jsonify({"error": "Cannot change venue ID when users are assigned to this venue"}), 400

    result = db.venue_settings.update_one(
        {"venue_id": venue_id},
        {"$set": cleaned_data}
    )

    if result.modified_count == 0:
        return jsonify({"message": "No changes were made"}), 200

    return jsonify({
        "message": "Venue updated successfully",
        "modified_count": result.modified_count
    }), 200

@venues_bp.route('/<venue_id>/delete', methods=['DELETE'])
@jwt_required()
def delete_venue(venue_id):
    claims = get_jwt()
    if claims.get('role') != 'administrator':
        return jsonify({"error": "Unauthorized"}), 403

    db = get_db()
    db.venue_settings.delete_one({"venue_id": venue_id})
    return jsonify({"message": "Venue deleted successfully"}), 200


@venues_bp.route('/settings/<venue_id>', methods=['GET', 'POST'])
@jwt_required()
def manage_venue_settings(venue_id):
    claims = get_jwt()
    if claims['venue_id'] != venue_id:
        return jsonify({"error": "Unauthorized"}), 403

    db = get_db()
    if request.method == 'GET':
        settings = db.venue_settings.find_one({"venue_id": venue_id}, {'_id': 0})
        if settings:
            return jsonify(settings), 200
        else:
            return jsonify({"error": "Settings not found"}), 404

    update_data = request.json
    db.venue_settings.update_one({"venue_id": venue_id}, {'$set': update_data}, upsert=True)
    return jsonify({"message": "Settings updated successfully"}), 200


@venues_bp.route('/settings/<venue_id>/binmapping', methods=['POST'])
@jwt_required()
def add_bin_mapping(venue_id):
    claims = get_jwt()
    if claims['venue_id'] != venue_id:
        return jsonify({"error": "Unauthorized"}), 403

    db = get_db()
    current_data = db.venue_settings.find_one({"venue_id": venue_id}, {'binMappings': 1, '_id': 0})
    current_mappings = current_data.get('binMappings', []) if current_data else []

    new_id = str(len(current_mappings) + 1)
    bin_mapping = request.json
    bin_mapping['id'] = new_id

    db.venue_settings.update_one({"venue_id": venue_id}, {'$push': {"binMappings": bin_mapping}}, upsert=True)
    return jsonify({"message": "Bin mapping added successfully", "id": new_id}), 200


@venues_bp.route('/settings/<venue_id>/binmapping/<bin_mapping_id>', methods=['DELETE'])
@jwt_required()
def delete_bin_mapping(venue_id, bin_mapping_id):
    claims = get_jwt()
    if claims['venue_id'] != venue_id:
        return jsonify({"error": "Unauthorized"}), 403

    db = get_db()
    db.venue_settings.update_one({"venue_id": venue_id}, {'$pull': {"binMappings": {"id": bin_mapping_id}}})
    return jsonify({"message": "Bin mapping deleted successfully"}), 200


@venues_bp.route('/settings/<venue_id>/overflow', methods=['POST'])
@jwt_required()
def add_overflow_location(venue_id):
    claims = get_jwt()
    if claims['venue_id'] != venue_id:
        return jsonify({"error": "Unauthorized"}), 403

    db = get_db()
    current_data = db.venue_settings.find_one({"venue_id": venue_id}, {'overflowLocations': 1, '_id': 0})
    current_overflows = current_data.get('overflowLocations', []) if current_data else []

    new_id = str(len(current_overflows) + 1)
    overflow_data = request.json
    overflow_data['id'] = new_id

    db.venue_settings.update_one({"venue_id": venue_id}, {'$push': {"overflowLocations": overflow_data}}, upsert=True)
    return jsonify({"message": "Overflow location added successfully", "id": new_id}), 200


@venues_bp.route('/settings/<venue_id>/overflow/<overflow_id>', methods=['DELETE'])
@jwt_required()
def delete_overflow_location(venue_id, overflow_id):
    claims = get_jwt()
    if claims['venue_id'] != venue_id:
        return jsonify({"error": "Unauthorized"}), 403

    db = get_db()
    db.venue_settings.update_one({"venue_id": venue_id}, {'$pull': {"overflowLocations": {"id": overflow_id}}})
    return jsonify({"message": "Overflow location deleted successfully"}), 200


@venues_bp.route('/settings/<venue_id>/schedule', methods=['POST'])
@jwt_required()
def update_schedule(venue_id):
    claims = get_jwt()
    if claims['venue_id'] != venue_id:
        return jsonify({"error": "Unauthorized"}), 403

    db = get_db()
    schedule_data = request.json
    db.venue_settings.update_one({"venue_id": venue_id}, {'$set': {"schedule": schedule_data}}, upsert=True)
    return jsonify({"message": "Schedule updated successfully"}), 200

# TODO: add routing for reset to defaults for venue settings, meaning, clear all settings for a venue, but keep the venue ID
@venues_bp.route('/settings/<venue_id>/reset', methods=['POST'])
@jwt_required()
def reset_settings(venue_id):
    db = get_db()

    venue = db.venue_settings.find_one({"venue_id": venue_id})
    if not venue:
        return jsonify({"message": "Venue not found"}), 404

    claims = get_jwt()
    if claims['venue_id'] != venue_id:
        return jsonify({"error": "Unauthorized"}), 403

    # check if the user is manaing that venue
    if claims['venue_id'] != venue_id:
        return jsonify({"error": "Unauthorized"}), 403

    db.venue_settings.update_one(
        {"venue_id": venue_id},
        {'$set': {
            "binMappings": [],
            "overflowLocations": [],
            "locationTransformations": [],
            "schedule": {
                "customTime": "00:00",
                "scheduleType": "none",
                "selectedDays": [],
            },
            "venue_message": [],
        }}
    )

    return jsonify({"message": "Settings have been reset successfully"}), 200
