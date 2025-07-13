"""Module for handling user specific playback interactions with Spotify."""

from datetime import datetime, timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotify_server.app.models import User
from spotify_server.app.services.user_repository import UserRepository
from spotify_server.extensions import db


class PlaybackService:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        user_repository: UserRepository,
    ):
        # Diese Konfiguration wird für den OAuth-Flow benötigt
        self.auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-modify-playback-state user-read-playback-state",
        )
        self.user_repository = user_repository

    def _get_user_spotify_client(self, user: User) -> spotipy.Spotify | None:
        """
        Erstellt eine Spotipy-Instanz für einen User.
        Prüft den Token und erneuert ihn bei Bedarf automatisch.
        """
        if type(user) is str:
            user = self.user_repository.get_user_by_id(user)

        if not user.spotify_refresh_token:
            print(f"User {user.username} hat Spotify nicht verbunden.")
            return None

        # Prüfen, ob der Access Token abgelaufen ist
        if datetime.utcnow() >= user.spotify_token_expires_at:
            print("Spotify Access Token ist abgelaufen. Erneuere...")
            try:
                # Token mit dem Refresh Token erneuern
                new_token_info = self.auth_manager.refresh_access_token(
                    user.spotify_refresh_token
                )

                # Neue Token-Daten in der DB speichern
                user.spotify_access_token = new_token_info["access_token"]
                user.spotify_refresh_token = new_token_info.get(
                    "refresh_token", user.spotify_refresh_token
                )  # Spotify sendet nicht immer einen neuen Refresh Token
                user.spotify_token_expires_at = datetime.utcnow() + timedelta(
                    seconds=new_token_info["expires_in"]
                )

                db.session.commit()
                print("Token erfolgreich erneuert und gespeichert.")
            # pylint: disable=W0718
            except Exception as e:
                print(f"Fehler beim Erneuern des Tokens für User {user.id}: {e}")
                return None

        # Erstelle den Client mit dem gültigen Access Token
        return spotipy.Spotify(auth=user.spotify_access_token)

    def play_song(self, user: User, track_id: str):
        """Spielt einen bestimmten Song für einen User ab."""
        sp = self._get_user_spotify_client(user)
        if sp:
            try:
                if type(user) is str:
                    user = self.user_repository.get_user_by_id(user)
                track_uri = f"spotify:track:{track_id}"
                # Der 'uris'-Parameter erwartet eine Liste von Song-URIs
                sp.start_playback(uris=[track_uri])
            except spotipy.exceptions.SpotifyException as e:
                print(f"Fehler bei der Wiedergabe: {e}")

    def pause_playback(self, user: User):
        """Pausiert die Wiedergabe für einen User."""
        sp = self._get_user_spotify_client(user)
        if sp:
            sp.pause_playback()

    def resume_playback(self, user: User):
        """Setzt die Wiedergabe für einen User fort."""
        sp = self._get_user_spotify_client(user)
        if sp:
            sp.start_playback()

    def toggle_play_pause(self, user: User):
        """Wechselt zwischen Pause und Wiedergabe für einen User."""
        sp = self._get_user_spotify_client(user)
        try:
            (
                sp.pause_playback()
                if sp.current_playback()["is_playing"]
                else sp.start_playback()
            )
        # pylint: disable=W0718
        except Exception:
            pass

    def get_current_id(self, user: User) -> str | None:
        """Holt die aktuelle Song-ID für einen User."""
        sp = self._get_user_spotify_client(user)
        if sp:
            current_playback = sp.current_playback()
            if current_playback and current_playback.get("item"):
                return current_playback["item"]["id"]
        return None
