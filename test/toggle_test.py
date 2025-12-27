# test/test_toggle.py
import os
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# 1. Konfiguration laden
load_dotenv()  # Liest deine .env Datei

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:5000/callback"

# ACHTUNG: Hier musst du einen gültigen Refresh Token eines Users einfügen,
# den du testen willst. Hol ihn dir z.B. kurz aus der DB oder lass ihn dir printen.
REFRESH_TOKEN = "AQDErE_miJZti-moEuojAT4Sbdxb1sfJZAjxex3sJvidPaP9tIRwOv_mx2plqQSd3GBc_9p9Z2jpFduJ5tLesLM42EiJ5mRkJDx27WtBlRgIfJs0yOd1fLSL-qeeaDkwDMo"


def get_client():
    """Erstellt einen frischen Spotipy Client."""
    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
    )
    # Token refreshen
    token_info = auth_manager.refresh_access_token(REFRESH_TOKEN)
    return spotipy.Spotify(auth=token_info['access_token'])


def test_toggle_logic():
    print("--- Starte Toggle Test ---")
    sp = get_client()

    start_total = time.time()

    # Wir simulieren den "Optimistischen Toggle":
    # Annahme: Wir wissen nicht, ob es läuft, aber wir raten "Es läuft -> Pause".

    print("Versuche PAUSE...", end="", flush=True)
    try:
        t1 = time.time()
        sp.pause_playback()
        print(f" ERFOLG! ({(time.time() - t1) * 1000:.2f}ms)")
    except spotipy.exceptions.SpotifyException as e:
        print(f" FEHLGESCHLAGEN ({(time.time() - t1) * 1000:.2f}ms)")
        print(f"  -> Fehler-Code: {e.http_status}")

        # Fallback: Play
        print("Versuche PLAY (Fallback)...", end="", flush=True)
        try:
            t2 = time.time()
            sp.start_playback()
            print(f" ERFOLG! ({(time.time() - t2) * 1000:.2f}ms)")
        except Exception as e2:
            print(f" AUCH FEHLGESCHLAGEN: {e2}")

    print(f"--- Gesamtzeit: {(time.time() - start_total) * 1000:.2f}ms ---")


if __name__ == "__main__":
    if REFRESH_TOKEN == "DEIN_REFRESH_TOKEN_HIER_EINFUEGEN":
        print("BITTE REFRESH_TOKEN IM SKRIPT EINTRAGEN!")
    else:
        test_toggle_logic()
