import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///agrichain_crm.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
    HOST = os.environ.get('HOST', 'localhost:5000')
    BREACH_DAYS_THRESHOLD = int(os.environ.get('BREACH_DAYS_THRESHOLD', 7))
    WTF_CSRF_ENABLED = True
