"""Modul für die Authentifizierungs-Routen der Spotify-Server-App."""

from flask import (
    Blueprint,
    redirect,
    request,
    session,
    url_for,
    render_template,
    send_from_directory,
)
from datetime import datetime
import spotipy


# Annahme: Deine User- und DB-Objekte sind hier importierbar
from spotify_server.app.models import User
from spotify_server.extensions import db


def create_auth_blueprint(playback_service):
    """Factory, um das Auth-Blueprint zu erstellen."""

    auth_bp = Blueprint("auth", __name__)

    @auth_bp.route("/")
    def index():
        if "token_info" not in session:
            return redirect(url_for("auth.login"))

        token_info = session["token_info"]
        if datetime.utcnow() > datetime.fromtimestamp(token_info["expires_at"]):
            return redirect(url_for("auth.login"))

        return render_template("index.html")

    @auth_bp.route("/login")
    def login():
        """Leitet den User zur Spotify-Login-Seite weiter."""
        # Holt die Authorisierungs-URL vom PlaybackService
        auth_url = playback_service.auth_manager.get_authorize_url()
        return redirect(auth_url)

    @auth_bp.route("/callback")
    def callback():
        """
        Wird von Spotify nach dem Login aufgerufen.
        Verarbeitet die Tokens und speichert sie.
        """
        # Tausche den Code aus der URL gegen Access- und Refresh-Tokens
        code = request.args.get("code")
        token_info = playback_service.auth_manager.get_access_token(code)

        # Speichere die Tokens in der Session für die aktuelle Sitzung
        # Wichtig: expires_at ist ein Unix-Timestamp, den wir speichern
        token_info["expires_at"] = (
            datetime.utcnow().timestamp() + token_info["expires_in"]
        )
        session["token_info"] = token_info

        # Identifiziere den User bei Spotify, um ihn in unserer DB zu finden oder anzulegen
        sp = spotipy.Spotify(auth=token_info["access_token"])
        spotify_user_info = sp.current_user()
        user_id = spotify_user_info["id"]

        # Finde oder erstelle den User in unserer Datenbank
        user = User.query.get({"user_id": user_id})
        if not user:
            user = User(
                user_id=user_id,
                username=spotify_user_info.get("display_name", user_id),
            )
            db.session.add(user)

        # Speichere die langlebigen Tokens in der Datenbank
        user.spotify_access_token = token_info["access_token"]
        user.spotify_refresh_token = token_info.get(
            "refresh_token", user.spotify_refresh_token
        )  # Nur updaten, wenn ein neuer kommt
        user.spotify_token_expires_at = datetime.fromtimestamp(token_info["expires_at"])

        db.session.commit()

        # Speichere unsere interne User-ID in der Session
        session["user_id"] = user.user_id

        # Leite zur Hauptseite zurück
        return redirect(url_for("auth.index"))

    @auth_bp.route("/logout")
    def logout():
        """Löscht die Session und loggt den User aus."""
        session.clear()
        # Optional: Den User zur Spotify-Logout-Seite leiten
        # return redirect("https://www.spotify.com/logout/")
        return redirect(url_for("auth.login"))

    # Route für das Favicon, hier logisch platziert
    @auth_bp.route("/favicon.ico")
    def favicon():
        # Annahme: Der static_folder ist im app-Objekt korrekt konfiguriert
        return send_from_directory("static", "favicon.png")

    return auth_bp
