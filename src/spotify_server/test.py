from flask import Flask, render_template, request, redirect, session, flash
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotify_server.trainer import SpotifyTrainer
import re
from dotenv import load_dotenv
import os

app = Flask(__name__)
app.secret_key = "geheim"  # für Sessions

load_dotenv()

# Spotify API-Konfiguration
sp = spotipy.Spotify(
    auth_manager = SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("REDIRECT_URL"),
        scope="user-read-playback-state user-modify-playback-state"
))
trainer = SpotifyTrainer("training_data.json", sp)

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
    session["playlist_id"] = playlist_url.split("/")[-1].split("?")[0]
    session["user_id"] = request.form.get("user_id")
    try:
        sp.shuffle(state=True)
        sp.start_playback(context_uri=f"spotify:playlist:{session['playlist_id']}")  # Spielt Playlist ab
        skip()
    # pylint: disable=W0718
    except Exception as e:
        flash("Kein Aktives Spotify Gerät gefunden. Bitte spiele irgendetwas auf deinem Spotify ab, und versuche es erneut.", "error")
        print(e)

    return render_template("index.html", user_id=session["user_id"])

@app.route("/play_pause")
def play_pause():
    try:
        sp.pause_playback() if sp.current_playback()['is_playing'] else sp.start_playback()
    # pylint: disable=W0718
    except Exception as e:
        flash(str(e), "error")
        print(e)
    return render_template("index.html", user_id=session["user_id"])

@app.route("/skip")
def skip():
    try:
        sp.start_playback(uris=[f'spotify:track:{trainer.get_next_track(session["playlist_id"], session["user_id"])}'])

    # pylint: disable=W0718
    except Exception as e:
        flash(str(e), "error")
        print(e)
    return render_template("index.html", user_id=session["user_id"])

@app.route("/check_guess", methods=["POST"])
def check_guess():
    # Holen der aktuellen Wiedergabe-Informationen von Spotify
    guess_year = request.form.get("year_guess")
    guess_artist = request.form.get("artist_guess")
    guess_title = request.form.get("title_guess")
    session["user_id"] = request.form.get("user_id")

    current_playback = sp.current_playback()
    if current_playback is None:
        flash("Kein Song wird gerade abgespielt.", "warning")
        return render_template("index.html", year_guess=guess_year, 
                           artist_guess=guess_artist, 
                           title_guess=guess_title, 
                           user_id=session["user_id"])
    
    # Auslesen der benötigten Informationen
    track_id = current_playback['item']['id']
    track_data = trainer.get_track_data(track_id)
    year = track_data["year"]  # Jahr aus den Track-Daten
    artists = ", ".join(track_data["artists"])  # Alle Künstlernamen zu einem String verbinden
    title = track_data["name"]  # Songtitel
    title = clean_title(title)
    
    score = trainer.calculate_score({
        "name": title,
        "artists": track_data["artists"],
        "year": year,
        "guess_name": guess_title,
        "guess_artist": guess_artist,
        "guess_year": guess_year
    })
    flash(f"Score: {score}", "success")
    trainer.update_training(session["playlist_id"], track_id, score)
    return render_template("index.html", year_guess=(guess_year + " (" + str(year) + ")"), 
                           artist_guess=(guess_artist + " (" + str(artists) + ")"), 
                           title_guess=(guess_title + " (" + str(title) + ")"), 
                           user_id=session["user_id"])

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
    session["user_id"] = request.form.get("user_id")
    
    if not year:
        flash("Jahr muss angegeben werden!", "danger")
        return render_template("index.html", user_id=session["user_id"])
    
    # Jahr speichern
    trainer.update_or_create_track_year(track_id, int(year))
    flash(f"Jahr für {title} gespeichert!", "success")
    return render_template("index.html", user_id=session["user_id"])


@app.route("/save_current_track", methods=["POST"])
def save_current_track():
    current_playback = sp.current_playback()
    if not current_playback or not current_playback["is_playing"]:
        flash("Es läuft aktuell kein Song.", "error")
        return render_template("index.html", user_id=session["user_id"])

    playlist_id = session["playlist_id"]
    session["user_id"] = request.form.get("user_id")
    track_id = current_playback["item"]["id"]

    trainer.add_track_to_playlist(track_id, playlist_id)

    flash("Track erfolgreich gespeichert.", "success")
    return render_template("index.html", user_id=session["user_id"])

@app.route('/stats', methods=["POST"])
def stats():
    total_songs = trainer.get_active_track_count(session["playlist_id"], request.form.get("user_id"))
    known_songs = trainer.get_finished_track_count(session["playlist_id"], request.form.get("user_id"))
    total_trys = trainer.get_try_count(session["playlist_id"], request.form.get("user_id"))
    return render_template('stats.html', total=total_songs, known=known_songs, trys=total_trys)

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
