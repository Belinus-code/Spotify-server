"""Module for managing song data in the database and interacting with Spotify."""

from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from spotify_server.extensions import db
from spotify_server.app.models import (
    Track,
    Artist,
    PlaylistTrack,
    Playlist,
    TrainingData,
)  # <-- Importiere deine Model-Klassen
from spotify_server.app.services.spotify_service import (
    SpotifyService,
)  # <-- Importiere den SpotifyService
from spotify_server.app.dto import SongDTO


class SongRepository:
    def __init__(self, spotify_service: SpotifyService):
        self.spotify_service = spotify_service

    def get_song(self, track_id: str) -> Track:

        if type(track_id) is Track:
            track_id = track_id.track_id
        song = Track.query.get(track_id)

        if song:
            return song  # Song existiert bereits in der DB

        else:
            song_details = self.spotify_service.get_song_details(track_id)
            if song_details is None:
                raise Exception

            # Erstelle ein neues Track-Objekt, aber speichere es noch nicht.
            new_track = Track(
                track_id=track_id,
                name=song_details["title"],
                year=song_details["year"],
                popularity=song_details["popularity"],
            )
            db.session.add(new_track)

            # Verarbeite die Künstler: Finde bestehende oder erstelle neue.
            processed_artist_names = []
            for artist_name in song_details["artists"]:
                # Prüfe, ob der Künstler bereits in der DB existiert.
                artist = Artist.query.filter_by(name=artist_name).first()
                if not artist:
                    # Wenn nicht, erstelle ein neues Artist-Objekt.
                    artist = Artist(name=artist_name)
                    db.session.add(artist)

                # Füge den gefundenen oder neuen Künstler zur Track-Beziehung hinzu.
                new_track.artists.append(artist)
                processed_artist_names.append(artist.name)

            # Speichere alle Änderungen (neuer Track, neue Künstler) in die DB.
            db.session.commit()

            # Gib das DTO mit den frisch geholten Daten zurück.
            return new_track

    def save_new_song(self, new_song: Track):
        """Speichert einen neuen Song in der Datenbank."""
        db.session.add(new_song)
        db.session.commit()

    def save_changes(self):
        """Speichert alle Änderungen in der Datenbank."""
        db.session.commit()

    def update_song(self, song_dto: SongDTO):
        """
        Aktualisiert einen bestehenden Song in der Datenbank.

        Sucht einen Track anhand seiner ID und überschreibt seine Daten mit den
        Werten aus dem übergebenen SongDTO. Die Künstlerliste wird dabei
        vollständig synchronisiert.

        Args:
            song_dto: Das DTO-Objekt mit den neuen Daten.

        Raises:
            ValueError: Wenn kein Song mit der gegebenen track_id gefunden wird.
        """
        # Hole den zu aktualisierenden Song aus der Datenbank.
        song = Track.query.get(song_dto.track_id)

        if not song:
            # Wirf einen Fehler, wenn der Song nicht existiert.
            raise ValueError(
                f"Update fehlgeschlagen: Track mit ID {song_dto.track_id} nicht gefunden."
            )

        # Aktualisiere die einfachen Attribute des Songs.
        song.name = song_dto.title
        song.year = song_dto.year

        # Synchronisiere die Künstler-Beziehung.
        # 1. Bestehende Künstlerverknüpfungen für diesen Song löschen.
        song.artists.clear()

        # 2. Die Künstlerliste aus dem DTO neu aufbauen.
        processed_artist_names = []
        for artist_name in song_dto.artists:
            # Prüfe, ob der Künstler bereits existiert, sonst erstelle ihn.
            artist = Artist.query.filter_by(name=artist_name).first()
            if not artist:
                artist = Artist(name=artist_name)
                db.session.add(artist)

            # Füge die Verknüpfung zum Song hinzu.
            song.artists.append(artist)
            processed_artist_names.append(artist.name)

        # Speichere die Änderungen in der Datenbank.
        db.session.commit()

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """
        Holt die Track-Objekte einer Playlist aus der DB oder lädt sie von Spotify.

        Prüft, ob die Playlist bereits vollständig in der Datenbank existiert.
        Wenn nicht, werden die Track-IDs von Spotify geladen, jeder einzelne
        Track wird über die 'get_song'-Logik verarbeitet (in die DB geschrieben) und
        anschließend mit der Playlist in der Datenbank verknüpft.

        Args:
            playlist_id: Die Spotify-ID der Playlist.

        Returns:
            Eine Liste der Track-Objekte, die zur Playlist gehören.
        """
        # Prüfe, ob die Playlist bereits in der DB existiert.
        # .options(joinedload(Playlist.tracks)) optimiert die Abfrage, um die verknüpften
        # Track-Objekte direkt mitzuladen und weitere DB-Anfragen zu vermeiden.
        playlist = Playlist.query.options(joinedload(Playlist.tracks)).get(playlist_id)

        # Wenn die Playlist existiert und bereits Tracks zugeordnet sind, gib die Objekte zurück.
        if playlist and playlist.tracks:
            print(f"Lade Tracks für Playlist {playlist_id} aus der Datenbank.")
            return [pt.track for pt in playlist.tracks]

        # Wenn die Playlist nicht (vollständig) existiert, lade die IDs von Spotify.
        print(f"Lade Tracks für Playlist {playlist_id} von der Spotify-API.")
        track_ids_from_spotify = self.spotify_service.get_playlist_tracks(playlist_id)
        if not track_ids_from_spotify:
            return []  # Playlist ist leer oder konnte nicht geladen werden.

        # Wenn die Playlist selbst noch nicht existiert, erstelle sie.
        if not playlist:
            try:
                playlist_details = self.spotify_service.get_playlist_details(
                    playlist_id
                )
                playlist_name = playlist_details.get("name", "Unbekannte Playlist")
            except (AttributeError, TypeError):
                playlist_name = "Unbekannte Playlist"

            playlist = Playlist(playlist_id=playlist_id, name=playlist_name)
            db.session.add(playlist)

        # Stelle sicher, dass alle Tracks in der DB existieren und erstelle die Verknüpfungen.
        final_track_objects = []
        for track_id in track_ids_from_spotify:
            # get_song stellt sicher, dass der Track in der DB ist und gibt das Objekt zurück.
            track = self.get_song(track_id)  # Annahme: diese Methode existiert
            if track:
                final_track_objects.append(track)
                # Erstelle die Verknüpfung in der PlaylistTrack-Tabelle, falls sie noch nicht existiert.
                association_exists = PlaylistTrack.query.get((playlist_id, track_id))
                if not association_exists:
                    association = PlaylistTrack(
                        playlist_id=playlist_id, track_id=track_id
                    )
                    db.session.add(association)

        # Speichere alle neuen Einträge (Playlist, Tracks, Artists, Verknüpfungen).
        db.session.commit()

        return final_track_objects

    def find_most_popular_untrained_track(
        self, user_id: str, playlist_id: str
    ) -> Track | None:
        """
        Findet den populärsten Track in einer Playlist, für den ein User noch keine
        Lernkarte hat, mit einer einzigen, effizienten Datenbankabfrage.
        """
        # Diese Abfrage führt folgende Schritte aus:
        # 1. JOIN Track mit PlaylistTrack, um die Playlist-Zugehörigkeit zu prüfen.
        # 2. OUTERJOIN mit TrainingData für den spezifischen User.
        # 3. FILTER auf die korrekte Playlist-ID.
        # 4. FILTER auf die Zeilen, bei denen der OUTERJOIN fehlschlug (TrainingData.user_id IS NULL),
        #    was bedeutet, dass für diesen Track keine Karte existiert.
        # 5. ORDER BY Popularität absteigend.
        # 6. LIMIT 1, um nur den besten Treffer zu erhalten.

        most_popular_track = (
            Track.query.join(PlaylistTrack, Track.track_id == PlaylistTrack.track_id)
            .outerjoin(
                TrainingData,
                and_(
                    Track.track_id == TrainingData.track_id,
                    TrainingData.user_id == user_id,
                ),
            )
            .filter(
                PlaylistTrack.playlist_id == playlist_id, TrainingData.user_id.is_(None)
            )
            .order_by(Track.popularity.desc())
            .first()
        )

        return most_popular_track

    def get_dto_by_track(self, track: Track) -> SongDTO:
        """
        Wandelt ein Track-Objekt in ein DTO um.
        """
        return SongDTO(
            track_id=track.track_id,
            title=track.name,
            artists=[artist.name for artist in track.artists],
            year=track.year,
            popularity=track.popularity,
        )
