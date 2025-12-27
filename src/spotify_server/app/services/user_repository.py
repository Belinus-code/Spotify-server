import uuid
from typing import Optional
from spotify_server.app.models import User
from spotify_server.extensions import db


class UserRepository:
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return User.query.get(user_id)

    def get_user_by_spotify_id(self, spotify_id: str) -> Optional[User]:
        return User.query.filter_by(spotify_id=spotify_id).first()

    def create_or_update_spotify_user(
        self, spotify_id: str, display_name: str, access_token: str, refresh_token: str, expires_at
    ) -> User:
        """
        Kern-Logik für den Login:
        1. Sucht User anhand der Spotify ID.
        2. Wenn nicht gefunden -> Erstellen.
        3. Wenn gefunden -> Tokens aktualisieren.
        """
        user = self.get_user_by_spotify_id(spotify_id)

        if not user:
            # Neuen User erstellen
            print(f"[AUTH] Erstelle neuen User für Spotify ID: {spotify_id}")
            user = User(
                user_id=str(uuid.uuid4()),
                spotify_id=spotify_id,
                username=display_name if display_name else f"User {spotify_id[:5]}"
            )
            db.session.add(user)
        else:
            # Existierenden User aktualisieren (Name könnte sich geändert haben)
            if display_name and user.username != display_name:
                user.username = display_name

        # Tokens und Ablaufdatum immer aktualisieren
        user.spotify_access_token = access_token

        # Spotify sendet den Refresh Token nur beim ersten Login oder wenn er rotiert wird
        if refresh_token:
            user.spotify_refresh_token = refresh_token

        user.spotify_token_expires_at = expires_at

        db.session.commit()
        return user
