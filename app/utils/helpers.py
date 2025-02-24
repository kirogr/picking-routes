from datetime import datetime
import pytz

def get_current_time():
    tz = pytz.timezone('Asia/Jerusalem')
    return datetime.now(tz)

# todo: the functions below should have a different class.

def logdb_auth_history(db, action, message, status="success", scheme="auth"):
    db.history.insert_one({
        "scheme": scheme,
        "action": action,
        "message": message,
        "status": status,
        "timestamp": get_current_time()
})

def logdb_users_history(db, user, action, target, message, status="success", scheme="users"):
    db.history.insert_one({
        "scheme": scheme,
        "user": user,
        "action": action,
        "target": target,
        "message": message,
        "status": status,
        "timestamp": get_current_time()
    })

def logdb_venues_history(db, user, action, target, message, status="success", scheme="venues"):
    db.history.insert_one({
        "scheme": scheme,
        "user": user,
        "action": action,
        "target": target,
        "message": message,
        "status": status,
        "timestamp": get_current_time()
    })