"""Module for handling any not user related spotify interactions."""

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


class SpotifyService:
    """
    Kapselt die gesamte Kommunikation mit der Spotify API.
    """

    def __init__(self, client_id: str, client_secret: str):
        """
        Initialisiert den Service und authentifiziert sich bei der Spotify API.
        """
        if not client_id or not client_secret:
            raise ValueError("Spotify Client ID und Secret müssen konfiguriert sein.")

        # Nutzt den "Client Credentials Flow" für Server-zu-Server-Anfragen
        auth_manager = SpotifyClientCredentials(
            client_id=client_id, client_secret=client_secret
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)
        print("Spotify Service initialisiert.")

    def get_song_details(self, spotify_id: str) -> dict | None:
        """
        Holt die Details für einen einzelnen Song anhand seiner Spotify ID.

        Gibt ein sauberes Dictionary mit den wichtigsten Daten zurück oder None bei einem Fehler.
        """
        try:
            track_result = self.sp.track(spotify_id)

            if not track_result:
                return None

            # Extrahiere nur die Daten, die wir wirklich brauchen.
            # Das entkoppelt den Rest der App von der komplexen Spotify-Struktur.
            if track_result["name"] is None:
                raise Exception

            details = {
                "title": track_result["name"],
                "artists": [artist["name"] for artist in track_result["artists"]],
                "popularity": track_result["popularity"],
                "year": int(track_result["album"]["release_date"][:4]),
            }
            print(details, flush=True)
            return details

        except spotipy.exceptions.SpotifyException as e:
            print(f"Fehler bei der Spotify-Anfrage für ID {spotify_id}: {e}")
            return None

    def get_playlist_tracks(self, playlist_id: str) -> list[str]:
        """
        Holt die IDs aller Songs in einer Playlist anhand ihrer Spotify ID.
        Behandelt automatisch die Paginierung für Playlists mit mehr als 100 Songs.

        Gibt eine Liste von Track-IDs (str) zurück oder eine leere Liste bei einem Fehler.
        """
        all_track_ids = []
        try:
            # Fordere nur die benötigten Felder an, um die Anfrage zu beschleunigen.
            results = self.sp.playlist_tracks(playlist_id, fields="items.track.id,next")
            if results is None:
                return []

            # Erste Seite der Ergebnisse verarbeiten
            for item in results.get("items", []):
                # Stelle sicher, dass der Track existiert und eine ID hat
                if item.get("track") and item["track"].get("id"):
                    # KORREKTUR: Gib die ID zurück, nicht den Namen
                    all_track_ids.append(item["track"]["id"])

            # Weitere Seiten abrufen, solange es sie gibt
            while results.get("next"):
                results = self.sp.next(results)
                for item in results.get("items", []):
                    if item.get("track") and item["track"].get("id"):
                        all_track_ids.append(item["track"]["id"])

            return all_track_ids

        except spotipy.exceptions.SpotifyException as e:
            print(f"Fehler bei der Spotify-Anfrage für Playlist {playlist_id}: {e}")
            return []

    def get_playlist_details(self, playlist_id: str) -> dict:
        """
        Holt Details zu einer bestimmten Playlist, insbesondere den Namen.

        Args:
            playlist_id: Die Spotify-ID der Playlist.

        Returns:
            Ein Dictionary mit den Playlist-Details (z.B. {'name': '...'}),
            oder ein leeres Dictionary bei einem Fehler.
        """
        try:
            # Ruft die Details für eine einzelne Playlist ab.
            # fields="name" sorgt dafür, dass nur das Namensfeld geladen wird.
            playlist_data = self.sp.playlist(playlist_id, fields="name")

            if playlist_data and "name" in playlist_data:
                return {"name": playlist_data["name"]}

            return {}
        except spotipy.exceptions.SpotifyException as e:
            print(
                f"Fehler bei der Spotify-Anfrage für Playlist-Details {playlist_id}: {e}"
            )
            return {}
