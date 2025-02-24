from pymongo import MongoClient
from flask import g
from app.config import Config

def get_db():
    if 'db' not in g:
        client = MongoClient(Config.MONGO_URI)
        g.db = client.get_database()
    return g.db
