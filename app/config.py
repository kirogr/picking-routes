import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = 604800  # 7 days in seconds
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/database")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    LOG_FILE = os.getenv("LOG_FILE", "app.log")