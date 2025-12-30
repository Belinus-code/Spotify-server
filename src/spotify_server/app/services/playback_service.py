"""Module for handling user specific playback interactions with Spotify."""

from datetime import datetime, timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotify_server.app.models import User, Track
from spotify_server.app.services.user_repository import UserRepository


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
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def _get_oauth_manager(self):
        """Erstellt einen SpotifyOAuth Manager für Refresh-Operationen."""
        return SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        )

    def _get_user_spotify_client(self, user: User) -> spotipy.Spotify | None:
        """
        Erstellt eine Spotipy-Instanz für einen User.
        Prüft den Token und erneuert ihn bei Bedarf automatisch.
        """
        if isinstance(user, str):
            user = self.user_repository.get_user_by_id(user)
            if user is None:
                return None

        if not user.spotify_refresh_token:
            print(f"User {user.username} hat Spotify nicht verbunden.")
            return None

        # Prüfen, ob der Access Token abgelaufen ist (oder in den nächsten 60s abläuft)
        # Wir geben ihm 60s Puffer.
        now = datetime.utcnow()
        if user.spotify_token_expires_at and user.spotify_token_expires_at <= (now + timedelta(seconds=60)):
            print(f"[TOKEN] Token für User {user.username} ist abgelaufen. Erneuere...")
            try:
                oauth = self._get_oauth_manager()
                # refresh_access_token gibt ein Dict mit neuem access_token, expires_in, etc. zurück
                token_info = oauth.refresh_access_token(user.spotify_refresh_token)

                if token_info:
                    new_access_token = token_info['access_token']
                    new_expires_at = now + timedelta(seconds=token_info['expires_in'])
                    new_refresh_token = token_info.get('refresh_token')  # Manchmal gibt es auch einen neuen Refresh Token

                    # In DB speichern
                    self.user_repository.update_user_tokens(
                        user,
                        new_access_token,
                        new_expires_at,
                        new_refresh_token
                    )

                    print(f"[TOKEN] Token erfolgreich erneuert für {user.username}.")

            except Exception as e:
                print(f"[TOKEN ERROR] Fehler beim Erneuern des Tokens für User {user.user_id}: {e}")
                # Im Fehlerfall machen wir weiter und hoffen das Beste, oder returnen None
                return None

        return spotipy.Spotify(auth=user.spotify_access_token)

    def play_song(self, user: User, track_id: str):
        """Spielt einen bestimmten Song für einen User ab."""
        if type(user) is str:
            user = self.user_repository.get_user_by_id(user)
        sp = self._get_user_spotify_client(user)
        if sp:
            try:
                if type(track_id) is Track:
                    track_id = track_id.track_id
                track_uri = f"spotify:track:{track_id}"
                # Der 'uris'-Parameter erwartet eine Liste von Song-URIs
                sp.start_playback(uris=[track_uri])
            except spotipy.exceptions.SpotifyException as e:
                print(f"Fehler bei der Wiedergabe: {e}")
                return TimeoutError

    def pause_playback(self, user: User):
        """Pausiert die Wiedergabe für einen User."""
        sp = self._get_user_spotify_client(user)

        if sp:
            try:
                sp.pause_playback()
            except spotipy.exceptions.SpotifyException:
                return TimeoutError()

    def resume_playback(self, user: User):
        """Setzt die Wiedergabe für einen User fort."""
        sp = self._get_user_spotify_client(user)
        if sp:
            try:
                sp.start_playback()
            except spotipy.exceptions.SpotifyException:
                return TimeoutError()

    def toggle_play_pause(self, user: User):
        """
        Wechselt zwischen Pause und Wiedergabe für einen User.
        """
        sp = self._get_user_spotify_client(user)

        if sp is None:
            return

        try:
            sp.pause_playback()

        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 403 or e.http_status == 500:  # 500er kommen bei Spotify State-Fehlern auch mal vor
                try:
                    sp.start_playback()
                except spotipy.exceptions.SpotifyException:
                    pass
            else:
                print(f"[ERROR] Pause fehlgeschlagen mit unerwartetem Fehler: {e}", flush=True)

        except Exception as e:
            print(f"[ERROR] Allgemeiner Fehler bei toggle: {e}", flush=True)

    def get_current_id(self, user: User) -> str | None:
        """Holt die aktuelle Song-ID für einen User."""
        sp = self._get_user_spotify_client(user)
        if sp:
            current_playback = sp.current_playback()
            if current_playback and current_playback.get("item"):
                return current_playback["item"]["id"]
        return None
