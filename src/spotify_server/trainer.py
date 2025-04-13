import json
import random
import os
from rapidfuzz import fuzz


class SpotifyTrainer:
    def __init__(self, training_data_file, sp):
        self.training_data_file = training_data_file
        self.training_data = {}
        self.sp = sp

    def load_training_data(self):
        # Überprüfen, ob die Datei existiert und nicht leer ist
        if os.path.exists(self.training_data_file) and os.path.getsize(self.training_data_file) > 0:
            with open(self.training_data_file, 'r', encoding="utf-8") as file:
                self.training_data = json.load(file)
        
    def save_training_data(self):
        with open(self.training_data_file, 'w', encoding="utf-8") as file:
            json.dump(self.training_data, file, indent=4)


    def get_playlist_tracks(self, playlist_id):
        tracks = []
        results = self.sp.playlist_items(playlist_id)
        while results:
            for item in results['items']:
                track = item['track']
                if track:
                    tracks.append({
                        'id': track['id'],
                        'name': track['name'],
                        'artists': [artist['name'] for artist in track['artists']]
                    })
            results = self.sp.next(results) if results['next'] else None
        return tracks
    
    def initialize_training_data(self, playlist_id, tracks):
        # Nur 30 zufällige Lieder aus der Playlist auswählen
        selected_tracks = random.sample(tracks, min(20, len(tracks)))

        self.training_data[playlist_id] = {}
        for track in selected_tracks:
            self.training_data[playlist_id][track['id']] = {
                "correct_guesses": 0,
                "repeat_in_n": random.randint(1, 20),  # Zufälliger Wert für den initialen Abstand
                "revisions": 0
            }

        self.save_training_data()

    def get_next_track(self, playlist_id):

        if self.training_data.get(playlist_id) is None:
            self.initialize_training_data(playlist_id, self.get_playlist_tracks(playlist_id))

        active_songs = [
            (track_id, data)
            for track_id, data in self.training_data[playlist_id].items()
            if data['repeat_in_n'] <= 0
        ]

        if not active_songs:
            # Alle Songs sind noch im Cooldown → eins runterzählen
            for data in self.training_data[playlist_id].values():
                data['repeat_in_n'] -= 1
            return self.get_next_track(playlist_id)
        
        song = random.choice(active_songs)[0]
        data = self.training_data[playlist_id][song]
        data["repeat_in_n"] = random.randint(3, 6)  # Zufälliger Wert für den neuen Abstand
        return song

    def update_training(self, playlist_id, track_id, score):
        data = self.training_data[playlist_id][track_id]

        if score == 5:
            data["correct_guesses"] += 1
            base_gap = 10 + data["correct_guesses"] * 5
            if base_gap > 25 and not data["is_done"] and self.count_tracks_below_threshold(playlist_id, 25) < 15:
                all_tracks = self.get_playlist_tracks(playlist_id)
                trained_track_ids = set(self.training_data.get(playlist_id, {}).keys())
                untrained_tracks = [track for track in all_tracks if track["id"] not in trained_track_ids]
                if untrained_tracks:
                    new_track = random.sample(untrained_tracks, min(1, len(untrained_tracks)))
                    new_track_id = new_track[0]["id"]
                    self.add_new_track(playlist_id, new_track_id)  # Neues Lied hinzufügen
                    data["is_done"] = True  # Markiere das Lied als "fertig"
        elif score == 4:
            base_gap = 10
        elif score == 3:
            base_gap = random.randint(6, 8)
        elif score == 2:
            base_gap = random.randint(4, 6)
        elif score == 1:
            base_gap = random.randint(2, 4)
        else:
            base_gap = random.randint(1, 3)  # wenn total daneben, gleich nochmal bringen

        if score < 3:
            data["correct_guesses"] = max(0, data["correct_guesses"] - 1)

        data["repeat_in_n"] = base_gap
        data["revisions"] += 1

        # Save training data after update
        self.save_training_data()

    def add_new_track(self, playlist_id, track_id):
        if track_id not in self.training_data[playlist_id]:
            self.training_data[playlist_id][track_id] = {
                "correct_guesses": 0,
                "repeat_in_n": random.randint(1, 3),  # Zufälliger Wert für das neue Lied
                "revisions": 0,
                "is_done": False
            }

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

        return sum(1 for track_data in self.training_data[playlist_id].values()
                if track_data.get("repeat_in_n", float("inf")) < threshold)
