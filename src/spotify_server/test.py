from flask import Flask, render_template, request, redirect, session, flash
import json
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotify_server.trainer import SpotifyTrainer

app = Flask(__name__)
app.secret_key = "geheim"  # für Sessions
TRACK_DATA_FILE = "track_data.json"
playlist_id = None

# Spotify API-Konfiguration
sp = spotipy.Spotify(
    auth_manager = SpotifyOAuth(
        client_id="9b5d8c07f8724ad9b6ad92a7bff7acc1",
        client_secret="8b9484a55f0046e4b0e4768bd52b96a5",
        redirect_uri="http://www.argumente-gegen-rechts.de:5000/callback",
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
    playlist_id = playlist_url.split("/")[-1]
    try:
        sp.shuffle(state=True)
        sp.start_playback(context_uri=f"spotify:playlist:{playlist_id}")  # Spielt Playlist ab
    except Exception as e:
        flash("Kein Aktives Spotify Gerät gefunden. Bitte spiele irgendetwas auf deinem Spotify ab, und versuche es erneut.", "error")
        print(e)

    return redirect("/")

@app.route("/play_pause")
def play_pause():
    sp.pause_playback() if sp.current_playback()['is_playing'] else sp.start_playback()
    return redirect("/")

@app.route("/skip")
def skip():
    sp.start_playback(uris=[f'spotify:track:{trainer.get_next_track(playlist_id)}'])
    return redirect("/")

@app.route("/check_guess", methods=["POST"])
def check_guess():
    # Holen der aktuellen Wiedergabe-Informationen von Spotify
    current_playback = sp.current_playback()
    
    if current_playback is None:
        flash("Kein Song wird gerade abgespielt.", "warning")
        return redirect("/")
    
    # Auslesen der benötigten Informationen
    track_id = current_playback['item']['id']
    year = current_playback['item']['album']['release_date'][:4]  # Jahr aus dem Veröffentlichungsdatum
    artists = [artist['name'] for artist in current_playback['item']['artists']]
    artist = ", ".join(artists)  # Alle Künstlernamen zu einem String verbinden
    title = current_playback['item']['name']  # Songtitel

    # Prüfen, ob das Jahr in der JSON-Datei gespeichert ist
    track_data = load_track_data()
    if track_id in track_data:
        year = track_data[track_id]  # Falls Jahr gespeichert, überschreibe es
    
    # Flash-Nachricht mit den Ergebnissen
    flash(f"Jahr: {year}, Interpret: {artist}, Titel: {title}", "song_info")
    
    # Die Daten an das Template weitergeben
    return render_template("index.html", year_guess=year, artist_guess=artist, title_guess=title)

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

if __name__ == "__main__":
    app.run(host="::", port=5000)
