"""Module für die Verwaltung von TrainingData-Lernkarten in der Datenbank."""

import random
from sqlalchemy import func
from spotify_server.extensions import db
from spotify_server.app.models import (
    TrainingData,
)  # Importiere das eben erstellte Model


class TrainingRepository:
    """
    Verwaltet alle Datenbankoperationen für die TrainingData-Lernkarten.
    """

    def create_new_card(
        self, user_id: str, playlist_id: str, track_id: str
    ) -> TrainingData:
        """
        Erstellt eine neue Lernkarte für einen Song, falls sie noch nicht existiert.

        Wenn bereits eine Karte für diese User/Playlist/Track-Kombination existiert,
        wird die bestehende Karte zurückgegeben, um Duplikate zu vermeiden.

        Args:
            user_id: Die ID des Benutzers.
            playlist_id: Die ID der Playlist.
            track_id: Die ID des Tracks.

        Returns:
            Die neue oder bereits existierende TrainingData-Instanz.
        """
        # Prüfen, ob eine Karte bereits existiert
        existing_card = self.get_card(user_id, playlist_id, track_id)
        if existing_card:
            print(f"Karte für Track {track_id} existiert bereits für User {user_id}.")
            return existing_card

        
        # Wenn keine Karte existiert, eine neue erstellen
        print(f"Erstelle neue Karte für Track {track_id} für User {user_id}.")
        new_card = TrainingData(
            user_id=user_id,
            playlist_id=playlist_id,
            track_id=track_id,
            correct_guesses=0,
            correct_in_row=0,
            repeat_in_n=random.randint(1, 6),  # Startwert für die Wiederholung
            revisions=0,
            is_done=False,
        )

        db.session.add(new_card)
        db.session.commit()

        return new_card

    def get_card(
        self, user_id: str, playlist_id: str, track_id: str
    ) -> TrainingData | None:
        """
        Holt eine spezifische Lernkarte aus der Datenbank.

        Args:
            user_id: Die ID des Benutzers.
            playlist_id: Die ID der Playlist.
            track_id: Die ID des Tracks.

        Returns:
            Die gefundene TrainingData-Instanz oder None.
        """
        # .get() ist optimiert für die Suche nach Primärschlüsseln, auch bei zusammengesetzten.
        return TrainingData.query.get((user_id, playlist_id, track_id))

    def save_card(self):
        """
        Speichert die Änderungen an einer bestehenden Lernkarte.
        """

        # Da das Objekt bereits aus der DB geladen wurde, reicht ein commit.
        # .add() ist nur nötig, wenn das Objekt neu ist oder aus der Session entfernt wurde.
        db.session.commit()

    def get_active_songs(self, user_id: str, playlist_id: str) -> list[TrainingData]:
        """
        Holt alle Songs für eine bestimmte User/Playlist-Kombination die dran sind.

        Args:
            user_id: Die ID des Benutzers.
            playlist_id: Die ID der Playlist.

        Returns:
            Eine Liste von TrainingData-Instanzen für aktive Songs.
        """
        return TrainingData.query.filter(
            TrainingData.user_id == user_id,
            TrainingData.playlist_id == playlist_id,
            TrainingData.repeat_in_n <= 0,
        ).all()

    def get_active_song_ids(self, user_id: str, playlist_id: str) -> list[str]:
        """
        Holt die Track-IDs aller Songs, die für eine bestimmte User/Playlist-Kombination fällig sind.
        Diese Methode ist performanter als get_active_songs, wenn nur die IDs benötigt werden.
        """
        # .with_entities() ist optimiert, um nur spezifische Spalten zu laden.
        query_result = (
            db.session.query(TrainingData.track_id)
            .filter(
                TrainingData.user_id == user_id,
                TrainingData.playlist_id == playlist_id,
                TrainingData.repeat_in_n <= 0,
            )
            .all()
        )

        # Das Ergebnis ist eine Liste von Tupeln, z.B. [('track_id_1',), ('track_id_2',)].
        # Wir wandeln sie in eine einfache Liste von Strings um.
        return [item[0] for item in query_result]

    def get_all_cards(self, user_id: str, playlist_id: str) -> list[TrainingData]:
        """
        Holt alle Lernkarten für eine bestimmte User/Playlist-Kombination.

        Args:
            user_id: Die ID des Benutzers.
            playlist_id: Die ID der Playlist.

        Returns:
            Eine Liste von TrainingData-Instanzen für alle Karten.
        """
        return TrainingData.query.filter(
            TrainingData.user_id == user_id,
            TrainingData.playlist_id == playlist_id,
        ).all()

    def get_all_card_ids(self, user_id: str, playlist_id: str) -> list[str]:
        """
        Holt alle Lernkarten für eine bestimmte User/Playlist-Kombination.

        Args:
            user_id: Die ID des Benutzers.
            playlist_id: Die ID der Playlist.

        Returns:
            Eine Liste von TrainingData-Instanzen für alle Karten.
        """
        query_result = (
            db.session.query(TrainingData.track_id)
            .filter(
                TrainingData.user_id == user_id, TrainingData.playlist_id == playlist_id
            )
            .all()
        )

        # Das Ergebnis ist eine Liste von Tupeln, z.B. [('track_id_1',), ('track_id_2',)].
        # Wir wandeln sie in eine einfache Liste von Strings um.
        return [item[0] for item in query_result]

    def count_tracks_below_threshold(
        self, user_id: str, playlist_id: str, threshold: int
    ) -> int:
        """
        Zählt die Anzahl der Tracks, deren 'correct_in_row' unter einem Schwellenwert liegt.
        """
        return TrainingData.query.filter(
            TrainingData.user_id == user_id,
            TrainingData.playlist_id == playlist_id,
            TrainingData.correct_in_row < threshold,
        ).count()

    def get_total_revisions(self, user_id: str, playlist_id: str) -> int:
        """
        Ermittelt die Gesamtzahl aller Wiederholungen (Summe der 'revisions') für einen User in einer Playlist.
        """
        # Für Aggregatfunktionen wie sum() wird db.session.query() verwendet.
        total = (
            db.session.query(func.sum(TrainingData.revisions))
            .filter(
                TrainingData.user_id == user_id, TrainingData.playlist_id == playlist_id
            )
            .scalar()
        )

        # .scalar() gibt None zurück, wenn keine Zeilen gefunden werden. Wir geben stattdessen 0 zurück.
        return total or 0

    def get_active_track_count(self, user_id: str, playlist_id: str) -> int:
        """
        Zählt alle Tracks, für die ein Training in einer Playlist für einen User begonnen wurde.
        """
        return TrainingData.query.filter(
            TrainingData.user_id == user_id, TrainingData.playlist_id == playlist_id
        ).count()

    def get_finished_track_count(self, user_id: str, playlist_id: str) -> int:
        """
        Zählt alle Tracks, die in einer Playlist für einen User als 'erledigt' markiert sind.
        """
        return TrainingData.query.filter(
            TrainingData.user_id == user_id,
            TrainingData.playlist_id == playlist_id,
            TrainingData.is_done == True,  # oder einfach nur TrainingData.is_done
        ).count()
