import json

from app.services.database import get_db
from app.services.token_service import get_access_token
from datetime import datetime, timedelta
import pytz
import requests


def fetch_unassigned_items(venue_id):
    # validate if the venue exists
    db = get_db()
    venue_settings = db.venue_settings.find_one({"venue_id": venue_id})
    if not venue_settings:
        print(f"Venue not found: {venue_id} in fetch_unassigned_items")
        return None

    BASE_URL = venue_settings['endpoints']['BASE_URL']
    UNASSIGNED_ITEMS_ENDPOINT = venue_settings['endpoints']['UNASSIGNED_ITEMS_ENDPOINT']
    url = f"{BASE_URL}{UNASSIGNED_ITEMS_ENDPOINT}"
    access_token = get_access_token()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching unassigned items: {response.status_code}, {response.text}")
        response.raise_for_status()


def fetch_itemconfigs(venue_id):
    db = get_db()
    venue_settings = db.venue_settings.find_one({"venue_id": venue_id})
    if not venue_settings:
        print(f"Venue not found: {venue_id} in fetch_itemconfigs")
        return None

    BASE_URL = venue_settings['endpoints']['BASE_URL']
    ITEM_CONFIG_ENDPOINT = venue_settings['endpoints']['ITEM_CONFIG_ENDPOINT']
    MENU_ID = venue_settings['endpoints']['MENU_ID']

    url = f"{BASE_URL}{ITEM_CONFIG_ENDPOINT}?menuId={MENU_ID}"
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching itemconfigs: {response.status_code}, {response.text}")
        response.raise_for_status()


def process_unassigned_items(venue_id, unassigned_items, item_configs, picking_areas):
    db = get_db()
    venue_settings = db.venue_settings.find_one({"venue_id": venue_id})
    if not venue_settings:
        print(f"Venue not found: {venue_id} in process_unassigned_items (subfunction)")
        return

    picking_area_map = {area["name"].upper(): area["id"] for area in picking_areas}
    unassigned_items = unassigned_items['data']  # the data is in the 'data' field
    binMappings = venue_settings['binMappings']
    renamed_locations = {}
    for mapping in binMappings:
        bin_location = mapping['binLocation']
        picking_area = mapping['pickingArea']
        renamed_locations[bin_location] = picking_area

    itemconfigs_map = {item["itemId"]: item for item in item_configs}
    picking_area_names = {area["id"]: area["name"] for area in picking_areas}

    assigned_items = []
    unavailable_items = []

    db.venue_settings.update_one(
        {"venue_id": venue_id},
        {"$set": {"unallocatedItems": []}}
    )

    for unassigned in unassigned_items:
        item_id = unassigned["id"]
        item = itemconfigs_map.get(item_id)

        if not item:
            unavailable_items.append(unassigned)
            continue

        storage_location = item.get("storageLocation", "")
        picking_area_id = get_best_picking_area(venue_id, storage_location, picking_area_map, renamed_locations)

        if storage_location and picking_area_id is None:
            print(f"{item_id} not assigned due to unallocated picking route.")

            db.venue_settings.update_one(
                {"venue_id": venue_id},
                {"$push": {"unallocatedItems": item_id}}
            )


        if picking_area_id:
            assigned_items.append({
                "itemId": item_id,
                "pickingAreaId": picking_area_id,
                "pickingAreaName": picking_area_names.get(picking_area_id, "Unknown"),
                "storageLocation": storage_location,
            })
        else:
            unavailable_items.append(unassigned)

    return assigned_items, unavailable_items

def normalize_location(location):
    if "-" in location:
        return "-".join(location.split("-")[:2])
    return location

def get_best_picking_area(venue_id, storage_location, picking_area_map, renamed_locations):
    db = get_db()
    venue_settings = db.venue_settings.find_one({"venue_id": venue_id})
    if not venue_settings:
        print(f"Venue not found: {venue_id} in get_best_picking_area (sub-subfunction)")
        return

    location_transformations_dict = venue_settings['locationTransformations']
    overflow_locations_set = venue_settings['overflowLocations']

    locations = storage_location.replace(",", "/").split("/")


    for loc in locations:
        loc = loc.split("(")[0].strip().upper()
        # print(f"Processing location: {loc}")

        # if the location is in overflow locations set, skip this location and move to the next
        if loc in overflow_locations_set:
            # print(f"[*] Skipping overflow location: {loc}")
            continue

        for transformation in location_transformations_dict:
            original = transformation['original']
            transformed = transformation['transformed']

            if loc.startswith(original):
                loc = transformed
                print(f"[*] Transformed location: {loc}")
                break


        loc = renamed_locations.get(loc, loc)
        normalized = normalize_location(loc)
        # print(f"Normalized location: {normalized}") # debug

        picking_area_id = picking_area_map.get(normalized)
        if picking_area_id:
            return picking_area_id

    return None


def fetch_all_items_information(venue_id):
    db = get_db()
    venue_settings = db.venue_settings.find_one({"venue_id": venue_id})
    if not venue_settings:
        print(f"Venue not found: {venue_id} in fetch_all_items_information")
        return None

    ALL_ITEMS_INFORMATION_ENDPOINT = venue_settings['endpoints']['ALL_ITEMS_INFORMATION_ENDPOINT']
    url = f"{ALL_ITEMS_INFORMATION_ENDPOINT}"
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching all items information: {response.status_code}, {response.text}")
        response.raise_for_status()

def get_picking_areas(venue_id):
    db = get_db()
    picking_areas = db.picking_areas.find_one({"venue_id": venue_id})

    if not picking_areas:
        picking_areas = None
    else:
        if isinstance(picking_areas['last_updated'], str):
            last_updated = datetime.fromisoformat(picking_areas['last_updated']).astimezone(pytz.utc)
        else:
            if picking_areas['last_updated'].tzinfo is None:
                last_updated = picking_areas['last_updated'].astimezone(pytz.utc)
            else:
                last_updated = picking_areas['last_updated']

        current_time = datetime.now(pytz.utc)
        expiration_time = current_time - timedelta(days=3)

        if last_updated < expiration_time:
            picking_areas = None

    if not picking_areas:
        venue_settings = db.venue_settings.find_one({"venue_id": venue_id})

        if not venue_settings:
            print(f"Venue settings not found for venue ID: {venue_id}")
            return None

        BASE_URL = venue_settings['endpoints']['BASE_URL']
        VENUE_ID = venue_settings['endpoints']['VENUE_ID']
        url = f"{BASE_URL}/v1/venues/{VENUE_ID}/picking-areas"
        print(f"Fetching picking areas from {url}")
        access_token = get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            picking_areas = response.json()

            for area in picking_areas["data"]:
                area.pop("order", None)
                area.pop("itemsCount", None)

            tz = pytz.timezone('Asia/Jerusalem')
            now = datetime.now(tz)
            db.picking_areas.update_one(
                {"venue_id": venue_id},
                {"$set": {"picking_areas": picking_areas["data"], "last_updated": now}},
                upsert=True
            )

            return picking_areas
        else:
            print(f"Error fetching picking areas: {response.status_code}, {response.text}")
            return None
    else:
        return picking_areas


def process_and_attach_items(venue_id):
    db = get_db()
    venue_settings = db.venue_settings.find_one({"venue_id": venue_id})
    if not venue_settings:
        print(f"Venue not found: {venue_id} in process_and_attach_items")
        return

    db = get_db()

    # first, get the picking areas
    picking_areas = get_picking_areas(venue_id)

    if not picking_areas:
        print(f"No picking areas found for venue: {venue_id} in process_and_attach_items")
        return

    # get the item configs
    item_configs = fetch_itemconfigs(venue_id)
    if not item_configs:
        print(f"No item configs found for venue: {venue_id} in process_and_attach_items")
        return

    db.item_configs.update_one(
        {"venue_id": venue_id},
        {
            "$set": {
                "item_configs": item_configs,
                "last_updated": datetime.now(pytz.utc)
            }
        },
        upsert=True
    )

    # get the unassigned items
    unassigned_items = fetch_unassigned_items(venue_id)
    if not unassigned_items:
        print(f"No unassigned items found for venue: {venue_id} in process_and_attach_items")
        return

    db.unassigned_items.update_one(
        {"venue_id": venue_id},
        {
            "$set": {
                "unassigned_items": unassigned_items,
                "last_updated": datetime.now(pytz.utc)
            }
        },
        upsert=True
    )

    assigned_items, unavailable_items = process_unassigned_items(venue_id, unassigned_items, item_configs, picking_areas['picking_areas'])

    # load all items information
    all_items_information = fetch_all_items_information(venue_id)
    if not all_items_information:
        print(f"No all items information found for venue: {venue_id} in process_and_attach_items")
        return

    # create a specific volume (file) in which we will store all items information
    with open(f"{venue_id}.json", 'w') as file:
        json.dump(all_items_information, file)

    attach_items_to_picking_routes(venue_id, assigned_items)

def attach_items_to_picking_routes(venue_id, assigned_items):
    db = get_db()
    venue_settings = db.venue_settings.find_one({"venue_id": venue_id})
    if not venue_settings:
        print(f"Venue not found: {venue_id}")
        return

    BASE_URL = venue_settings['endpoints']['BASE_URL']
    VENUE_ID = venue_settings['endpoints']['VENUE_ID']
    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}

    print("Total items to assign:", len(assigned_items))

    for item in assigned_items:
        picking_area_id = item["pickingAreaId"]
        url = f"{BASE_URL}/v1/venues/{VENUE_ID}/picking-areas/{picking_area_id}/items"
        payload = {"data": [item["itemId"]]}
        print(f"Assigning item {item['itemId']} to picking area {picking_area_id}")
        # response = requests.post(url, headers=headers, json=payload)
        # if response.status_code in [200, 207]:
        #     print(f"Assigned item {item['itemId']} to picking area {picking_area_id}")
        # else:
        #     print(f"Failed to assign item {item['itemId']}: {response.text}")


def reprocess_items(venue_id):
    db = get_db()
    venue_settings = db.venue_settings.find_one({"venue_id": venue_id})
    if not venue_settings:
        return {"error": "Venue not found"}

    process_and_attach_items(venue_id)

    return {"message": "Items reprocessed successfully"}