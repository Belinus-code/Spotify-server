from flask import Flask, render_template, request, redirect, session, flash
import json
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotify_server.trainer import SpotifyTrainer
import re

app = Flask(__name__)
app.secret_key = "geheim"  # für Sessions
TRACK_DATA_FILE = "track_data.json"
playlist_id = None

# Spotify API-Konfiguration
sp = spotipy.Spotify(
    auth_manager = SpotifyOAuth(
        client_id="9b5d8c07f8724ad9b6ad92a7bff7acc1",
        client_secret="8b9484a55f0046e4b0e4768bd52b96a5",
        redirect_uri="http:/http://37.120.186.189:5000/callback",
        scope="user-read-playback-state user-modify-playback-state"
))
trainer = SpotifyTrainer("training_data.json", sp)
trainer.load_training_data()  # Beispiel-Playlist-ID

@app.route("/")
def index():
    if "token_info" not in session:
        return redirect("/login")
    return render_template("index.html")

@app.route("/login")
def login():
    auth_url = sp.auth_manager.get_authorize_url()
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    token_info = sp.auth_manager.get_access_token(code)
    session["token_info"] = token_info
    return redirect("/")

@app.route("/set_playlist", methods=["POST"])
def set_playlist():
    playlist_url = request.form.get("playlist_url")
    playlist_id = playlist_url.split("/")[-1].split("?")[0]
    session["playlist_id"] = playlist_id  # Speichern der Playlist-ID in der Session
    try:
        sp.shuffle(state=True)
        sp.start_playback(context_uri=f"spotify:playlist:{playlist_id}")  # Spielt Playlist ab
        skip()
    except Exception as e:
        flash("Kein Aktives Spotify Gerät gefunden. Bitte spiele irgendetwas auf deinem Spotify ab, und versuche es erneut.", "error")
        print(e)

    return redirect("/")

@app.route("/play_pause")
def play_pause():
    try:
        sp.pause_playback() if sp.current_playback()['is_playing'] else sp.start_playback()
    except Exception as e:
        flash(str(e), "error")
        print(e)
    return redirect("/")

@app.route("/skip")
def skip():
    try:
        sp.start_playback(uris=[f'spotify:track:{trainer.get_next_track(session["playlist_id"])}'])
    except Exception as e:
        flash(str(e), "error")
        print(e)
    return redirect("/")

@app.route("/check_guess", methods=["POST"])
def check_guess():
    # Holen der aktuellen Wiedergabe-Informationen von Spotify
    guess_year = request.form.get("year_guess")
    guess_artist = request.form.get("artist_guess")
    guess_title = request.form.get("title_guess")

    current_playback = sp.current_playback()
    if current_playback is None:
        flash("Kein Song wird gerade abgespielt.", "warning")
        return render_template("index.html", year_guess=guess_year, 
                           artist_guess=guess_artist, 
                           title_guess=guess_title)
    
    # Auslesen der benötigten Informationen
    track_id = current_playback['item']['id']
    year = current_playback['item']['album']['release_date'][:4]  # Jahr aus dem Veröffentlichungsdatum
    artists = [artist['name'] for artist in current_playback['item']['artists']]
    artist = ", ".join(artists)  # Alle Künstlernamen zu einem String verbinden
    title = current_playback['item']['name']  # Songtitel
    title = clean_title(title)

    # Prüfen, ob das Jahr in der JSON-Datei gespeichert ist
    track_data = load_track_data()
    if track_id in track_data:
        year = track_data[track_id]  # Falls Jahr gespeichert, überschreibe es
    
    score = trainer.calculate_score({
        "name": title,
        "artists": artists,
        "year": year,
        "guess_name": guess_title,
        "guess_artist": guess_artist,
        "guess_year": guess_year
    })
    flash(f"Score: {score}", "success")
    trainer.update_training(session["playlist_id"], track_id, score)
    return render_template("index.html", year_guess=(guess_year + " (" + str(year) + ")"), 
                           artist_guess=(guess_artist + " (" + str(artist) + ")"), 
                           title_guess=(guess_title + " (" + str(title) + ")"))

@app.route("/save_year", methods=["POST"])
def save_year():
    # Holen der aktuellen Wiedergabe-Informationen von Spotify
    current_playback = sp.current_playback()
    
    if current_playback is None:
        flash("Kein Song wird gerade abgespielt.", "warning")
        return redirect("/")
    
    # Daten aus der aktuellen Wiedergabe holen
    track_id = current_playback['item']['id']
    title = current_playback['item']['name']  # Songtitel
    year = request.form.get("year")
    
    if not year:
        flash("Jahr muss angegeben werden!", "danger")
        return redirect("/")
    
    # Jahr speichern
    save_track_data(track_id, int(year))
    flash(f"Jahr für {title} gespeichert!", "success")
    return redirect("/")
@app.route("/save_current_track", methods=["POST"])
def save_current_track():
    current_playback = sp.current_playback()
    if not current_playback or not current_playback["is_playing"]:
        flash("Es läuft aktuell kein Song.", "error")
        return redirect("/")

    playlist_id = session["playlist_id"]

    track_id = current_playback["item"]["id"]

    # Lade bestehende interne Playlists
    try:
        with open("internal_playlists.json", "r") as f:
            internal_playlists = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        internal_playlists = {}

    # Track zur Playlist-ID hinzufügen
    if playlist_id not in internal_playlists:
        internal_playlists[playlist_id] = []

    if track_id not in internal_playlists[playlist_id]:
        internal_playlists[playlist_id].append(track_id)

    # Speichern
    with open("internal_playlists.json", "w") as f:
        json.dump(internal_playlists, f, indent=2)

    flash("Track erfolgreich gespeichert.", "success")
    return redirect("/")

# Hilfsfunktion, um die Track-Daten zu laden
def load_track_data():
    if os.path.exists(TRACK_DATA_FILE):
        with open(TRACK_DATA_FILE, "r") as file:
            return json.load(file)
    return {}

# Hilfsfunktion, um die Track-Daten zu speichern
def save_track_data(track_id, year):
    track_data = load_track_data()
    track_data[track_id] = year
    with open(TRACK_DATA_FILE, "w") as file:
        json.dump(track_data, file)

def clean_title(title):
    # Alles in Klammern entfernen
    title = re.sub(r"\(.*?\)", "", title)
    # Alles hinter einem Bindestrich entfernen
    title = title.split("-")[0]
    # Whitespace bereinigen
    return title.strip()

if __name__ == "__main__":
    app.run(host="::", port=5000)

def cli():
    app.run(host="::", port=5000)
