import random
import os
from sqlalchemy import create_engine, and_, func, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from rapidfuzz import fuzz
from spotify_server.models import PlaylistTrack, TrainingData, Track, Artist, TrackArtist
from dotenv import load_dotenv
import logging


class SpotifyTrainer:
    def __init__(self, training_data_file, sp):
        load_dotenv()
        self.training_data_file = training_data_file
        self.training_data = {}
        self.sp = sp
        self.db_url = os.getenv("DB_URL")
        self.engine = create_engine(self.db_url, pool_pre_ping=True, pool_recycle=300)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        
    def get_playlist_tracks(self, playlist_id):
        self.refresh_session()
        try:
            tracks = self.session.query(PlaylistTrack).filter_by(playlist_id=playlist_id).all()

            # Falls keine Einträge in der Playlist vorhanden sind, lade sie von Spotify
            if not tracks:
                logging.info(f"Playlist {playlist_id} nicht in DB gefunden  lade von Spotify.")
                try:
                    spotify_tracks = self.sp.playlist_tracks(playlist_id)["items"]
                    for item in spotify_tracks:
                        track = item.get("track")
                        if track and "id" in track:
                            self.get_track_data(track["id"])  # Erstellt SQL-Eintrag falls nötig
                    # Danach erneut aus DB lesen
                    tracks = self.session.query(PlaylistTrack).filter_by(playlist_id=playlist_id).all()
                except Exception as e:
                    logging.error(f"Fehler beim Nachladen der Playlist {playlist_id} von Spotify: {e}")
                    return []

            return tracks

        except SQLAlchemyError as e:
            logging.error(f"Datenbankfehler in get_playlist_tracks({playlist_id}): {e}")
            self.session.rollback()
            return []

        except Exception as e:
            logging.error(f"Allgemeiner Fehler in get_playlist_tracks({playlist_id}): {e}")
            return []
    
    def initialize_training_data(self, playlist_id: str, user_id: int):
        self.refresh_session()
        # 1. Alle Tracks aus der Playlist abrufen
        playlist_tracks = self.get_playlist_tracks(playlist_id)

        # 2. Zufällige Auswahl von Tracks (max. 20)
        selected_tracks = random.sample(playlist_tracks, min(20, len(playlist_tracks)))

        for track in selected_tracks:
            # 3. Neues Trainingseintrag erstellen
            training_data_entry = TrainingData(
                playlist_id=playlist_id,
                track_id=track.track_id,  # Track ID aus der PlaylistTrack-Tabelle
                user_id=user_id,
                correct_guesses=0,
                repeat_in_n=random.randint(1, 20),  # Zufälliger Wert für den initialen Abstand
                revisions=0
            )

            self.session.add(training_data_entry)

        self.session.commit()

    def get_next_track(self, playlist_id: str, user_id: int, current_track_id: str = None):
        self.refresh_session()
        session = self.session  # Session aus der Klasse

        # 1. Alle Trainingsdaten mit repeat_in_n <= 0 laden (aktive Songs)
        active_songs = session.query(TrainingData).filter(
            and_(
                TrainingData.playlist_id == playlist_id,
                TrainingData.user_id == user_id,
                TrainingData.repeat_in_n <= 0
            )
        ).all()

        debug_counter = 0

        if not active_songs:
            # 2. Wenn keine aktiven Songs: alle repeat_in_n um 1 verringern
            all_songs = session.query(TrainingData).filter(
                and_(
                    TrainingData.playlist_id == playlist_id,
                    TrainingData.user_id == user_id
                )
            ).all()
            for data in all_songs:
                data.repeat_in_n -= 1
                debug_counter += 1
            session.commit()

            if len(all_songs) == 0:
                # Wenn keine Songs vorhanden sind, neue Tracks initialisieren
                self.initialize_training_data(playlist_id, user_id)
                print(f"Keine aktiven Songs gefunden. Playlist wird initialisiert: {playlist_id}")

            # Rekursiver Retry
            return self.get_next_track(playlist_id, user_id)

        # 3. Zufälligen Song auswählen und repeat_in_n neu setzen
        song_data = random.choice(active_songs)
        session.commit()

        if current_track_id and song_data.track_id == current_track_id:
            print(f"Error: Gleicher Track hintereinander. Counter: {debug_counter}")
        return song_data.track_id

    def update_training(self, playlist_id: str, track_id: str, score: int, user_id: int = 0):
        self.refresh_session()
        session = self.session

        training_entry = session.query(TrainingData).filter_by(
            playlist_id=playlist_id,
            track_id=track_id,
            user_id=user_id
        ).first()

        if training_entry is None:
            print("Kein Trainingseintrag gefunden. Breche ab.")
            print(f"Playlist ID: {playlist_id}, Track ID: {track_id}, User ID: {user_id}")
            return
        
        if training_entry.correct_guesses < 0:
            training_entry.correct_guesses = 0

        if training_entry.correct_in_row < 0:
            training_entry.correct_in_row = 0

        # Update Score Logic
        if score == 5:
            training_entry.correct_guesses += 1
            training_entry.correct_in_row += 1
            base_gap = 10 + training_entry.correct_guesses * 5

            below_threshold_count = session.query(TrainingData).filter(
                and_(
                    TrainingData.playlist_id == playlist_id,
                    TrainingData.user_id == user_id,
                    TrainingData.correct_guesses < 3
                )
            ).count()

            if base_gap > 25 and not training_entry.is_done and below_threshold_count < 15:
                training_entry.is_done = True
                self.choose_new_track(playlist_id, user_id)  # Funktion muss angepasst werden

        elif score == 4:
            base_gap = 10
        elif score == 3:
            base_gap = random.randint(6, 8)
        elif score == 2:
            base_gap = random.randint(4, 6)
        elif score == 1:
            base_gap = random.randint(2, 4)
        else:
            base_gap = random.randint(1, 3)

        if score < 4:
            training_entry.correct_guesses = max(0, training_entry.correct_guesses - 1)
            training_entry.correct_in_row = 0

        training_entry.repeat_in_n = base_gap
        training_entry.revisions += 1

        if training_entry.correct_guesses < 0:
            print("Trotz Korrektur ist correct_guesses negativ. Bitte überprüfen.")

        if training_entry.correct_in_row < 0:
            print("Trotz Korrektur ist correct_in_row negativ. Bitte überprüfen.")

        session.commit()

    def choose_new_track(self, playlist_id: str, user_id: int = 0):
        self.refresh_session()
        session = self.session

        # Alle Track-IDs aus der Playlist
        playlist_track_ids = session.query(PlaylistTrack.track_id).filter_by(
            playlist_id=playlist_id
        ).subquery()

        # IDs, für die schon Trainingsdaten existieren
        trained_track_ids = session.query(TrainingData.track_id).filter_by(
            playlist_id=playlist_id,
            user_id=user_id
        ).subquery()

        # Finde untrainierte Tracks mit ihrer Popularität, sortiert absteigend
        most_popular_untrained_track = session.query(Track.track_id).filter(
            Track.track_id.in_(session.query(playlist_track_ids.c.track_id)),
            ~Track.track_id.in_(session.query(trained_track_ids.c.track_id))
        ).order_by(Track.popularity.desc()).first()

        if not most_popular_untrained_track:
            print("Keine untrainierten Tracks mehr mit Popularität gefunden.")
            return

        new_track_id = most_popular_untrained_track[0]

        new_training_entry = TrainingData(
            user_id=user_id,
            playlist_id=playlist_id,
            track_id=new_track_id,
            correct_guesses=0,
            repeat_in_n=random.randint(1, 6),
            revisions=0,
            is_done=False,
            correct_in_row=0
        )
        session.add(new_training_entry)
        session.commit()

    def calculate_score(self, training_object):
        # Score anhand der richtigkeit der Antwort berechnen
        if training_object["guess_name"] is not None:
            name_sim = fuzz.ratio(training_object['name'].lower(), training_object['guess_name'].lower())
        else:
            name_sim = 0
        artist_sim = 0
        for artist in training_object['artists']:
            artist_sim = max(artist_sim, fuzz.ratio(artist.lower(), training_object['guess_artist'].lower()))
        year_diff = abs(int(training_object['year']) - int(training_object['guess_year']))
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
        
        return int(score) if score > 0 else 0  # Score auf 0 setzen, wenn kleiner als 0

    def count_tracks_below_threshold(self, playlist_id, user_id, threshold):
        self.refresh_session()
        return (
            self.session.query(TrainingData)
        .filter(
        TrainingData.playlist_id == playlist_id,
        TrainingData.user_id == user_id,
        TrainingData.correct_in_row < threshold
        ).count()
        )
    
    def get_try_count(self, playlist_id, user_id):
        self.refresh_session()
        result = (
            self.session.query(func.sum(TrainingData.revisions))
            .filter(TrainingData.playlist_id == playlist_id, TrainingData.user_id == user_id)
            .scalar()
        )
        return result or 0
    
    def get_active_track_count(self, playlist_id, user_id):
        self.refresh_session()
        return (
            self.session.query(TrainingData)
            .filter(TrainingData.playlist_id == playlist_id, TrainingData.user_id == user_id)
            .count()
        )

    def get_finished_track_count(self, playlist_id, user_id):
        self.refresh_session()
        return (
            self.session.query(TrainingData)
            .filter(TrainingData.playlist_id == playlist_id, TrainingData.user_id == user_id, TrainingData.is_done == True)
            .count()
        )
    
    def get_track_data(self, track_id: str) -> dict:
        self.refresh_session()
        # Track laden oder neu anlegen
        track = self.session.query(Track).filter_by(track_id=track_id).first()
        if not track:
            track = Track(track_id=track_id)
            self.session.add(track)
            self.session.commit()

        # Prüfen, ob Name oder Jahr fehlt
        missing_name = not track.name
        missing_year = not track.year
        missing_popularity = (track.popularity == -1)

        # Künstler über Join ermitteln
        artist_names = (
            self.session.query(Artist.name)
            .join(TrackArtist, Artist.artist_id == TrackArtist.artist_id)
            .filter(TrackArtist.track_id == track_id)
            .all()
        )
        artist_names = [name for (name,) in artist_names]
        missing_artists = len(artist_names) == 0

        # Wenn Daten fehlen → von Spotify laden
        if missing_name or missing_year or missing_artists or missing_popularity:
            try:
                data = self.sp.track(track_id)

                if missing_name:
                    track.name = data["name"]
                if missing_year:
                    track.year = int(data["album"]["release_date"][:4])

                if missing_popularity:
                    track.popularity = data["popularity"]

                if missing_artists:
                    for artist_obj in data["artists"]:
                        artist_name = artist_obj["name"]

                        # Prüfen, ob Artist schon existiert
                        artist = self.session.query(Artist).filter_by(name=artist_name).first()
                        if not artist:
                            artist = Artist(name=artist_name)
                            self.session.add(artist)
                            self.session.flush()  # Holt die neue artist_id

                        # Beziehung track → artist anlegen
                        link_exists = self.session.query(TrackArtist).filter_by(
                            track_id=track_id,
                            artist_id=artist.artist_id
                        ).first()
                        if not link_exists:
                            ta = TrackArtist(track_id=track_id, artist_id=artist.artist_id)
                            self.session.add(ta)

                self.session.commit()

            except Exception as e:
                print(f"Fehler beim Spotify-Track-Fetch: {e}")
                self.session.rollback()

        # Künstler nochmal holen nach möglichem Update
        artist_names = (
            self.session.query(Artist.name)
            .join(TrackArtist, Artist.artist_id == TrackArtist.artist_id)
            .filter(TrackArtist.track_id == track_id)
            .all()
        )
        artist_names = [name for (name,) in artist_names]

        return {
            "track_id": track.track_id,
            "name": track.name,
            "year": track.year,
            "artists": artist_names
        }
    
    def add_track_to_playlist(self, track_id: str, playlist_id: str):
        self.refresh_session()
        exists = self.session.query(PlaylistTrack).filter_by(track_id=track_id, playlist_id=playlist_id).first()
        if not exists:
            new_entry = PlaylistTrack(track_id=track_id, playlist_id=playlist_id)
            self.session.add(new_entry)
            self.session.commit()
            self.get_track_data(track_id)  # Track-Daten abrufen und speichern

    def update_or_create_track_year(self, track_id: str, year: int):
        self.refresh_session()
        track = self.session.query(Track).filter_by(track_id=track_id).first()
        if track:
            track.year = year
        else:
            track = Track(track_id=track_id, name=None, year=year, popularity=None)
            self.session.add(track)
        self.session.commit()

    def refresh_session(self):
        try:
            if self.session:
                self.session.close()
            self.session = self.Session()
            # Test-Query direkt nach Erstellen
            self.session.execute(text("SELECT 1"))
        except OperationalError:
            print("Session ungültig. Engine wird neu aufgebaut")
            self.engine.dispose()
            self.engine = create_engine(self.db_url, pool_pre_ping=True, pool_recycle=300)
            self.Session = sessionmaker(bind=self.engine)
            self.session = self.Session()
