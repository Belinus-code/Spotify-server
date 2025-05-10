import random
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from rapidfuzz import fuzz
from spotify_server.models import PlaylistTrack, TrainingData, Track, Artist, TrackArtist


class SpotifyTrainer:
    def __init__(self, training_data_file, sp):
        self.training_data_file = training_data_file
        self.training_data = {}
        self.sp = sp
        self.engine = create_engine("mysql+pymysql://ADMIN:Zeppelin@37.120.186.189:3306/spotifytrainer")
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        
    def get_playlist_tracks(self, playlist_id):
        return self.session.query(PlaylistTrack).filter_by(playlist_id=playlist_id).all()
    
    def initialize_training_data(self, playlist_id: str, user_id: int):
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

    def get_next_track(self, playlist_id: str, user_id: int):

        session = self.session  # Session aus der Klasse

        # 1. Alle Trainingsdaten mit repeat_in_n <= 0 laden (aktive Songs)
        active_songs = session.query(TrainingData).filter(
            and_(
                TrainingData.playlist_id == playlist_id,
                TrainingData.user_id == user_id,
                TrainingData.repeat_in_n <= 0
            )
        ).all()

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
            session.commit()

            if len(all_songs) == 0:
                # Wenn keine Songs vorhanden sind, neue Tracks initialisieren
                self.initialize_training_data(playlist_id, user_id)

            # Rekursiver Retry
            return self.get_next_track(playlist_id, user_id)

        # 3. Zufälligen Song auswählen und repeat_in_n neu setzen
        song_data = random.choice(active_songs)
        song_data.repeat_in_n = random.randint(3, 6)
        session.commit()

        return song_data.track_id

    def update_training(self, playlist_id: str, track_id: str, score: int, user_id: int = 0):
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

        session.commit()

    def choose_new_track(self, playlist_id: str, user_id: int = 0):
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

    def calculate_score(self, object):
        # Score anhand der richtigkeit der Antwort berechnen
        if object["guess_name"] is not None:
            name_sim = fuzz.ratio(object['name'].lower(), object['guess_name'].lower())
        else:
            name_sim = 0
        artist_sim = 0
        for artist in object['artists']:
            artist_sim = max(artist_sim, fuzz.ratio(artist.lower(), object['guess_artist'].lower()))
        year_diff = abs(int(object['year']) - int(object['guess_year']))
        score = (5 - min(5, year_diff)) / 2
        if name_sim > 60:
            score += 1.25
        else:
            score += (name_sim / 100) * 0.3
        if artist_sim > 60:
            score += 1.25
        else:     
            score += (artist_sim / 100) * 0.3
        

        return int(score) if score > 0 else 0  # Score auf 0 setzen, wenn kleiner als 0
    
    def count_tracks_below_threshold(self, playlist_id, threshold):
        if playlist_id not in self.training_data:
            return 0

        count = 0
        for track_data in self.training_data[playlist_id].values():
            if "correct_in_row" in track_data:
                if track_data["correct_in_row"] < threshold:
                    count += 1

        return count
    
    def get_try_count(self, playlist_id):
        if playlist_id not in self.training_data:
            return 0

        count = 0
        for track_data in self.training_data[playlist_id].values():
            if "revisions" in track_data:
                count += track_data["revisions"]

        return count
    
    def get_active_track_count(self, playlist_id):
        if playlist_id not in self.training_data:
            return 0
        return len(self.training_data[playlist_id])
    
    def get_finished_track_count(self, playlist_id):
        if playlist_id not in self.training_data:
            return 0

        count = 0
        for track_data in self.training_data[playlist_id].values():
            if "is_done" in track_data and track_data["is_done"]:
                count += 1

        return count
    
    def get_track_data(self, track_id: str) -> dict:
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
        exists = self.session.query(PlaylistTrack).filter_by(track_id=track_id, playlist_id=playlist_id).first()
        if not exists:
            new_entry = PlaylistTrack(track_id=track_id, playlist_id=playlist_id)
            self.session.add(new_entry)
            self.session.commit()
            self.get_track_data(track_id)  # Track-Daten abrufen und speichern

    def update_or_create_track_year(self, track_id: str, year: int):
        track = self.session.query(Track).filter_by(track_id=track_id).first()
        if track:
            track.year = year
        else:
            track = Track(track_id=track_id, name=None, year=year, popularity=None)
            self.session.add(track)
        self.session.commit()
