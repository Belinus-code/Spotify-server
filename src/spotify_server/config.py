"""Konfiguration für die Flask-Anwendung."""

import os
from dotenv import load_dotenv

# Lade die Variablen aus der .env-Datei in die Umgebungsvariablen des Systems
load_dotenv()


class Config:
    """Konfiguration für die Flask-Anwendung."""

    # Flask Secret Key
    SECRET_KEY = os.getenv("FLASK_SECRET")

    # Spotify Konfiguration
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = os.getenv("REDIRECT_URL")

    # Datenbank-Konfiguration
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_NAME = os.getenv("DB_NAME")

    # Baue den Connection String dynamisch zusammen
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    )
    SQLALCHEMY_POOL_RECYCLE = 28000  # Pool-Recycling-Zeit in Sekunden
    SQLALCHEMY_TRACK_MODIFICATIONS = False
