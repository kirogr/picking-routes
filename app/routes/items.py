import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt
from app.services.database import get_db
from app.services.item_service import reprocess_items
from datetime import datetime, timedelta
import pytz

items_bp = Blueprint('items', __name__)

@items_bp.route('/overview', methods=['GET'])
@jwt_required()
def get_overview():
    claims = get_jwt()
    venue_id = claims.get('venue_id')

    if not venue_id:
        return jsonify({"error": "Invalid venue ID"}), 400

    db = get_db()
    unassigned_items = db.unassigned_items.find_one({"venue_id": venue_id})
    item_configs = db.item_configs.find_one({"venue_id": venue_id})

    if not unassigned_items or not item_configs:
        return jsonify({"error": "No data available"}), 404

    # check if there is a message in the database for the venue
    settings = db.venue_settings.find_one({"venue_id": venue_id})
    message = settings.get("venue_message", "")

    return jsonify({
        "venue": venue_id,
        "overviewMessage": message,
        "totalItems": len(item_configs.get("item_configs", [])),
        "unassignedItems": len(unassigned_items.get("unassigned_items", []))
    }), 200

@items_bp.route('/history', methods=['GET'])
@jwt_required()
def get_history():
    try:
        db = get_db()
        claims = get_jwt()
        user = db.users.find_one({"username": claims['sub']})

        if not user:
            return jsonify({"error": "User not found"}), 404

        tz = pytz.timezone('Asia/Jerusalem')
        results = db.item_updates.find({
            "venue": user['venue_id']
        }).sort("timestamp", -1)

        history_data = {}
        for item in results:
            adjusted_timestamp = item['timestamp'] + timedelta(hours=2)
            local_timestamp = adjusted_timestamp.astimezone(tz)
            date_key = local_timestamp.strftime('%Y-%m-%d')
            if date_key not in history_data:
                history_data[date_key] = {'date': date_key, 'items': []}
            history_data[date_key]['items'].append({
                "id": item["item_id"],
                "image": item["image_url"],
                "name": item["product_name"],
                "gtin": item["gtin"],
                "previousPickingArea": item.get("previous_picking_area", "Unassigned Items"),
                "pickingArea": item["picking_area_name"],
                "updatedAt": local_timestamp.isoformat()
            })

        sorted_history = sorted(history_data.values(), key=lambda x: x['date'], reverse=True)
        return jsonify(sorted_history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@items_bp.route('/logs', methods=['GET'])
@jwt_required()
def get_logs():
    claims = get_jwt()

    if claims['role'] != 'administrator':
        return jsonify({"error": "Unauthorized"}), 403

    # validate with the db that the user is administrator
    db = get_db()
    user = db.users.find_one({"username": claims['sub']})
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user['role'] != 'administrator':
        return jsonify({"error": "Unauthorized"}), 403

    if not os.path.exists('app.log'):
        return jsonify({"error": "Log file not found"}), 404

    logs = []
    try:
        with open('app.log', 'r', encoding='utf-8') as file:
            for line in file:
                entry = parse_log_line(line)
                if entry:
                    logs.append(entry)

        logs.reverse()
        return jsonify(logs)
    except FileNotFoundError:
        return jsonify({"error": "Log file not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def parse_log_line(line):
    try:
        type = "info"
        return {
            "type": type,
            "timestamp": 0,
            "message": line.strip()
        }
    except Exception as e:
        print(f"Failed to parse line: {line}. Error: {e}")
        return None

@items_bp.route('/overview/last-assigned', methods=['GET'])
@jwt_required()
def last_assigned_items():
    claims = get_jwt()
    venue_id = claims.get('venue_id')

    if not venue_id:
        return jsonify({"error": "Invalid venue ID"}), 400

    db = get_db()
    tz = pytz.timezone('Asia/Jerusalem')
    now = datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = start_of_day - timedelta(days=10)
    start_date_utc = start_date.astimezone(pytz.utc)

    results = db.item_updates.find({
        "timestamp": {"$gte": start_date_utc},
        "venue": venue_id
    }).sort("timestamp", -1)

    items = []
    for item in results:
        if 'timestamp' in item and item['timestamp'].tzinfo is None:
            item['timestamp'] = item['timestamp'].replace(tzinfo=pytz.utc)
        updated_at = item['timestamp'].astimezone(tz)

        items.append({
            "id": item["item_id"],
            "image": item.get("image_url", "default-image.jpg"),
            "name": item["product_name"],
            "gtin": item.get("gtin", "N/A"),
            "previousPickingArea": item.get("previous_picking_area", "Unassigned Items"),
            "pickingArea": item["picking_area_name"],
            "updatedAt": updated_at.isoformat()
        })

    return jsonify(items), 200

@items_bp.route('/reprocess-items', methods=['POST'])
@jwt_required()
def reprocess_items_route():
    claims = get_jwt()
    venue_id = claims.get('venue_id')
    if not venue_id:
        return jsonify({"error": "Venue ID not found in token"}), 400

    result = reprocess_items(venue_id)
    return jsonify(result), 200
