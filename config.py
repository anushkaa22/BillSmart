from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = "change-this-in-production"
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'inventory.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
