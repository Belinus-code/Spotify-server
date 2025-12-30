"""Module für die Trainings-Logik des Spotify-Servers."""

import random
import re
from rapidfuzz import fuzz
from spotify_server.app.models import Track, User
from spotify_server.app.services.song_repository import SongRepository
from spotify_server.app.services.training_repository import TrainingRepository
from spotify_server.app.services.playback_service import PlaybackService
from spotify_server.app.services.user_repository import UserRepository


class TrainingService:
    """
    Enthält die Kernlogik des Trainers.
    """

    def __init__(
        self,
        song_repository: SongRepository,
        training_repository: TrainingRepository,
        playback_service: PlaybackService,
        user_repository: UserRepository,
    ):
        self.song_repository = song_repository
        self.training_repository = training_repository
        self.playback_service = playback_service
        self.user_repository = user_repository

    def init_training(self, user_id: str, playlist_id: str):
        """
        Initialisiert eine Trainings-Session für einen User und eine Playlist.

        Es werden die 20 populärsten Songs aus der Playlist ausgewählt, für die
        noch keine Lernkarte existiert, und neue Lernkarten dafür angelegt.
        """
        print(
            f"Initialisiere Training für User {user_id} mit Playlist {playlist_id}..."
        )

        # Annahme: song_repository kann alle Tracks einer Playlist holen.
        # Dies könnte auch in einem separaten PlaylistRepository liegen.
        all_tracks_in_playlist = self.song_repository.get_playlist_tracks(
            playlist_id=playlist_id
        )

        if not all_tracks_in_playlist:
            print(
                "Keine Tracks in der Playlist gefunden oder Playlist existiert nicht."
            )
            return

        # Finde heraus, für welche Tracks bereits Karten existieren
        trained_track_ids = {
            card.track_id
            for card in self.training_repository.get_all_cards(user_id, playlist_id)
        }

        # Filtere die Tracks, für die noch keine Karte existiert
        untrained_tracks = [
            track
            for track in all_tracks_in_playlist
            if track.track_id not in trained_track_ids
        ]

        if not untrained_tracks:
            return

        # Sortiere die neuen Tracks nach Popularität (absteigend)
        untrained_tracks.sort(key=lambda track: track.popularity, reverse=True)

        # Wähle die Top 20 (oder weniger, falls nicht so viele übrig sind)
        tracks_to_add = untrained_tracks[:20]

        # Erstelle für jeden dieser Tracks eine neue Lernkarte
        for track in tracks_to_add:
            self.training_repository.create_new_card(
                user_id=user_id, playlist_id=playlist_id, track_id=track.track_id
            )

        print(f"{len(tracks_to_add)} neue Lernkarten wurden erstellt.")

    def add_new_song(self, user_id: str, playlist_id: str) -> str | None:
        """
        Wählt den populärsten Song aus einer Playlist, für den der User noch keine Lernkarte hat,
        indem eine einzige, optimierte Datenbankabfrage genutzt wird.
        """
        # Delegiere die gesamte Logik an die neue Repository-Methode.
        if type(user_id) is User:
            user_id = user_id.user_id

        most_popular_track = self.song_repository.find_most_popular_untrained_track(
            user_id=user_id, playlist_id=playlist_id
        )

        if most_popular_track:
            return most_popular_track.track_id
        else:
            print(
                f"User {user_id} lernt bereits alle Songs aus Playlist {playlist_id}."
            )
            return None

    def calculate_score(self, user_guess: dict, user_id: str) -> int:
        """
        Berechnet den Score basierend auf der Antwort des Nutzers.
        """
        # Hier kommt deine Logik zum Berechnen der Punkte
        track_id = self.playback_service.get_current_id(user_id)
        if not track_id:
            raise LookupError("Kein aktueller Track gefunden.")

        song = self.song_repository.get_song(track_id)
        if not song:
            raise LookupError(f"Song mit ID {track_id} nicht gefunden.")
        song = self.song_repository.get_dto_by_track(song)

        if user_guess["name"] is not None:
            name_sim = fuzz.ratio(
                self.clean_title(song.title).lower(), user_guess["name"].lower()
            )
        else:
            name_sim = 0
        artist_sim = 0
        for artist in song.artists:
            artist_sim = max(
                artist_sim,
                fuzz.ratio(artist.lower(), user_guess["artist"].lower()),
            )
        year_diff = abs(int(song.year) - int(user_guess["year"]))

        score = (5 - min(5, year_diff)) / 2
        if name_sim > 60:
            score += 1.25
        else:
            score += (name_sim / 100) * 0.3
        if artist_sim > 60:
            score += 1.25
        else:
            score += (artist_sim / 100) * 0.3

        if score == 5 and (artist_sim < 80 or name_sim < 80):
            score = 4

        score_result = {
            "score": int(score) if score > 0 else 0,
            "correct_year": song.year,
            "correct_artist": ", ".join(song.artists),  # Fügt mehrere Künstler zusammen
            "correct_title": song.title,
        }

        # 5. Gib das fertige Dictionary zurück
        return score_result

    def choose_next_song(self, user: User, playlist_id: str) -> Track | None:
        """
        Wählt nach einer bestimmten Logik die nächste zu wiederholende Lernkarte aus.
        (Diese Funktion wird von dir implementiert)
        """
        # Hier kommt deine Logik zur Auswahl des nächsten Songs
        # z.B. basierend auf 'repeat_in_n' oder anderen Kriterien
        songs = self.training_repository.get_all_cards(user.user_id, playlist_id)
        if not songs:
            self.init_training(user.user_id, playlist_id)

        active_songs = self.training_repository.get_active_songs(
            user_id=user.user_id, playlist_id=playlist_id
        )

        while active_songs is None or len(active_songs) == 0:
            for song in songs:
                song.repeat_in_n -= 1
            active_songs = self.training_repository.get_active_songs(
                user_id=user.user_id, playlist_id=playlist_id
            )
        self.song_repository.save_changes()  # Speichert die Änderungen in der Datenbank

        return random.choice(active_songs)

    def update_training(
        self, playlist_id: str, track_id: str, score: int, user_id: int = 0
    ):

        training_card = self.training_repository.get_card(
            playlist_id=playlist_id, track_id=track_id, user_id=user_id
        )

        user = self.user_repository.get_user_by_id(user_id)

        if training_card is None:
            print("Kein Trainingseintrag gefunden. Breche ab.")
            print(
                f"Playlist ID: {playlist_id}, Track ID: {track_id}, User ID: {user_id}"
            )
            return

        if training_card.repeat_in_n != 0:
            print("Karte ist nicht fällig für ein Update. Breche ab.")
            return

        if training_card.correct_guesses < 0:
            training_card.correct_guesses = 0

        if training_card.correct_in_row < 0:
            training_card.correct_in_row = 0

        # Update Score Logic
        if score == 5:
            user.current_streak += 1
            training_card.correct_guesses += 1
            training_card.correct_in_row += 1
            INTERVAL_MODIFIER_BASE = 1.35
            INTERVAL_MODIFIER = random.uniform(
                INTERVAL_MODIFIER_BASE - 0.1, INTERVAL_MODIFIER_BASE + 0.3
            )

            base_gap = round(10 * (INTERVAL_MODIFIER**training_card.correct_in_row)) + 3
            random_fuzz = random.randint(0, max(1, int(base_gap * 0.05)))
            base_gap += random_fuzz

            below_threshold_count = (
                self.training_repository.count_tracks_below_threshold(
                    playlist_id=playlist_id, user_id=user_id, threshold=3
                )
            )

            if (
                base_gap > 25
                and (not training_card.is_done
                     and below_threshold_count < 15)
                or self.training_repository.get_active_track_count(user_id, playlist_id) - self.training_repository.get_finished_track_count(user_id, playlist_id) < 15
            ):
                training_card.is_done = True
                self.add_new_song(
                    playlist_id=playlist_id, user_id=user_id
                )

        elif score == 4:
            base_gap = 10 + random.randint(0, 3)
        elif score == 3:
            base_gap = random.randint(6, 8)
        elif score == 2:
            base_gap = random.randint(4, 6)
        elif score == 1:
            base_gap = random.randint(2, 4)
        else:
            base_gap = random.randint(1, 3)

        if score < 4:
            training_card.correct_guesses = max(0, training_card.correct_in_row - 1)
            training_card.correct_in_row = 0

        if score < 5:
            if user.current_streak > user.max_streak:
                user.max_streak = user.current_streak
            user.current_streak = 0

        training_card.repeat_in_n = base_gap
        training_card.revisions += 1

        if training_card.correct_guesses < 0:
            print("Trotz Korrektur ist correct_guesses negativ. Bitte überprüfen.")

        if training_card.correct_in_row < 0:
            print("Trotz Korrektur ist correct_in_row negativ. Bitte überprüfen.")

        self.training_repository.save_card()

    def clean_title(self, title):
        """Bereinigt den Titel eines Songs von unnötigen Informationen."""

        # Alles in Klammern entfernen
        title = re.sub(r"\(.*?\)", "", title)
        # Alles hinter einem Bindestrich entfernen
        title = title.split("-")[0]
        # Whitespace bereinigen
        return title.strip()
