from datetime import datetime, timedelta
from flask import Blueprint, redirect, request, session, url_for, render_template
from spotipy.oauth2 import SpotifyOAuth
import spotipy

from spotify_server.config import Config
from spotify_server.app.services.user_repository import UserRepository

bp = Blueprint("auth", __name__)
user_repo = UserRepository()


def get_spotify_auth():
    """Konfiguriert den OAuth Manager."""
    return SpotifyOAuth(
        client_id=Config.SPOTIFY_CLIENT_ID,
        client_secret=Config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=Config.SPOTIFY_REDIRECT_URI,
        # Scopes: Playback steuern, Private Playlists lesen, User Details lesen
        scope="user-read-private user-read-email user-modify-playback-state user-read-playback-state playlist-read-private",
        show_dialog=True  # WICHTIG: Erzwingt das Spotify-Login-Fenster (für Account-Wechsel)
    )


@bp.route("/", methods=["GET"])
def index():
    """Startseite."""
    user = None
    if "user_id" in session:
        user = user_repo.get_user_by_id(session["user_id"])

    return render_template("index.html", user=user)


@bp.route("/login")
def login():
    """Startet den Login-Prozess -> Redirect zu Spotify."""
    auth_manager = get_spotify_auth()
    auth_url = auth_manager.get_authorize_url()
    return redirect(auth_url)


@bp.route("/logout")
def logout():
    """Beendet die Session."""
    session.clear()
    return redirect(url_for("auth.index"))


@bp.route("/callback")
def callback():
    """
    Rückkehr von Spotify.
    Holt Token, Identifiziert User via API und loggt ihn ein.
    """
    auth_manager = get_spotify_auth()
    code = request.args.get("code")

    if not code:
        # Falls User "Abbrechen" geklickt hat
        return redirect(url_for("auth.index"))

    try:
        # 1. Access Token tauschen
        token_info = auth_manager.get_access_token(code)
        access_token = token_info["access_token"]

        # 2. User-Daten von Spotify laden (wir brauchen die ID!)
        sp = spotipy.Spotify(auth=access_token)
        spotify_user_data = sp.current_user()

        spotify_id = spotify_user_data["id"]
        # Falls kein Display Name gesetzt ist, fallback auf ID
        display_name = spotify_user_data.get("display_name") or spotify_id

        # Ablaufzeit berechnen
        expires_at = datetime.utcnow() + timedelta(seconds=token_info["expires_in"])

        # 3. User in DB anlegen oder updaten
        user = user_repo.create_or_update_spotify_user(
            spotify_id=spotify_id,
            display_name=display_name,
            access_token=access_token,
            refresh_token=token_info.get("refresh_token"),
            expires_at=expires_at
        )

        # 4. User ID in die Flask Session schreiben -> Eingeloggt
        session["user_id"] = user.user_id

        return redirect(url_for("auth.index"))

    except Exception as e:
        print(f"[AUTH ERROR] Fehler im Callback: {e}")
        return f"Fehler beim Login: {e}", 500
