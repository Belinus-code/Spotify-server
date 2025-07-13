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
            details = {
                "title": track_result["name"],
                "artists": [artist["name"] for artist in track_result["artists"]],
                "year": int(track_result["album"]["release_date"][:4]),
            }
            return details

        except spotipy.exceptions.SpotifyException as e:
            print(f"Fehler bei der Spotify-Anfrage für ID {spotify_id}: {e}")
            return None

    def get_playlist_tracks(self, playlist_id: str) -> list[str]:
        """
        Holt die Titel der Songs in einer Playlist anhand ihrer Spotify ID.

        Gibt eine Liste von Songtiteln zurück oder eine leere Liste bei einem Fehler.
        """
        try:
            playlist = self.sp.playlist_tracks(playlist_id)
            tracks = playlist.get("items", [])
            return [track["track"]["name"] for track in tracks if track["track"]]
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
