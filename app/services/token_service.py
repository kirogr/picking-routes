import time
from app.services.database import get_db
import requests

def read_tokens_from_db():
    db = get_db()
    token_data = db.token.find_one({})
    if token_data:
        token_data.pop('_id', None)
    return token_data

def write_tokens_to_db(token_data):
    db = get_db()
    db.token.replace_one({}, token_data, upsert=True)

def refresh_access_token():
    token_data = read_tokens_from_db()
    refresh_token = token_data.get('refresh_token') if token_data else None

    if not refresh_token:
        print("No refresh token found, please provide the initial refresh token.")
        return

    refresh_url = "<API_HOLDER>"
    payload = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(refresh_url, data=payload, headers=headers)

    if response.status_code == 200:
        data = response.json()
        token_data = {
            'access_token': data['access_token'],
            'refresh_token': data['refresh_token'],
            'expires_at': time.time() + data['expires_in']
        }
        write_tokens_to_db(token_data)
        print("Access token refreshed successfully.")
    else:
        print(f"Failed to refresh access token: {response.status_code}, {response.text}")

def get_access_token():
    token_data = read_tokens_from_db()
    if not token_data:
        print("No token data found, fetching new token...")
        refresh_access_token()
        token_data = read_tokens_from_db()

    current_time = time.time()
    if current_time >= token_data['expires_at']:
        print("Access token has expired, refreshing...")
        refresh_access_token()
        token_data = read_tokens_from_db()

    return token_data['access_token']