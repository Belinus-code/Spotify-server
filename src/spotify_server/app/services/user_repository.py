"""UserRepository for managing user data in the database."""

from spotify_server.app.models import User

# from spotify_server.extensions import db


class UserRepository:
    """
    Verwaltet alle Datenbankoperationen für das User-Modell.
    """

    def get_user_by_id(self, user_id: str) -> User | None:
        """
        Holt ein User-Objekt anhand seiner ID (Primärschlüssel) aus der Datenbank.

        Args:
            user_id: Die ID des Benutzers (entspricht der Spotify-ID).

        Returns:
            Das gefundene User-Objekt oder None.
        """
        # .get() ist die optimierte Methode für die Suche nach einem Primärschlüssel.
        return User.query.get({"user_id": user_id})
