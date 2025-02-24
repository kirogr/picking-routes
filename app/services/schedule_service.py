from apscheduler.schedulers.background import BackgroundScheduler
from app.services.database import get_db
from app.services.item_service import process_and_attach_items
from datetime import datetime, timedelta
import pytz

DAY_MAPPING = {
    "sunday": "sun", "monday": "mon", "tuesday": "tue", "wednesday": "wed",
    "thursday": "thu", "friday": "fri", "saturday": "sat"
}

def add_or_update_job(scheduler, venue):
    venue_id = venue["venue_id"]
    schedule_info = venue.get("schedule", {})
    schedule_type = schedule_info.get("scheduleType", "every_hour")
    custom_time = schedule_info.get("customTime", "00:00")
    selected_days = schedule_info.get("selectedDays", [])
    
    mapped_days = [DAY_MAPPING[day.lower()] for day in selected_days if day.lower() in DAY_MAPPING]
    hours, minutes = map(int, custom_time.split(":"))
    job_id = f"{venue_id}_schedule"
    
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        print(f"Removed old job for {venue_id}")
    
    if schedule_type == "every_hour":
        scheduler.add_job(process_and_attach_items, 'cron', minute=0, id=job_id, args=[venue_id])
    elif schedule_type == "custom_time":
        scheduler.add_job(process_and_attach_items, 'cron', hour=hours, minute=minutes, day_of_week=','.join(mapped_days), id=job_id, args=[venue_id])
    
    print(f"Updated schedule for venue: {venue_id}, Type: {schedule_type}, Time: {custom_time}, Days: {mapped_days}")

def setup_schedulers(scheduler):
    db = get_db()
    venues = db.venue_settings.find()
    for venue in venues:
        add_or_update_job(scheduler, venue)
    if not scheduler.running:
        scheduler.start()