import json
import random
import os


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
        selected_tracks = random.sample(tracks, min(30, len(tracks)))

        self.training_data[playlist_id] = {}
        for track in selected_tracks:
            self.training_data[playlist_id][track['id']] = {
                "correct_guesses": 0,
                "repeat_in_n": random.randint(1, 15),  # Zufälliger Wert für den initialen Abstand
                "revisions": 0
            }

        self.save_training_data()

    def get_next_track(self, playlist_id):

        if self.training_data[playlist_id] is None:
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
        data["repeat_in_n"] = random.randint(3, 10)  # Zufälliger Wert für den neuen Abstand
        return song

    def update_training(self, playlist_id, track_id, score):
        data = self.training_data[playlist_id][track_id]

        if score == 5:
            data["correct_guesses"] += 1
            base_gap = 10 + data["correct_guesses"] * 10
        elif score == 4:
            base_gap = 10
        elif score == 3:
            base_gap = 5
        else:
            base_gap = 1  # wenn total daneben, gleich nochmal bringen

        data["repeat_in_n"] = base_gap
        data["revisions"] += 1

        # Save training data after update
        self.save_training_data()

    def add_new_track(self, playlist_id, track_id):
        if track_id not in self.training_data[playlist_id]:
            self.training_data[playlist_id][track_id] = {
                "correct_guesses": 0,
                "repeat_in_n": random.randint(1, 3),  # Zufälliger Wert für das neue Lied
                "revisions": 0
            }

    def calculate_score(self, correct_guesses, revisions):
        # Beispielhafter Score-Algorithmus
        if revisions == 0:
            return 0  # noch nie bewertet
        score = correct_guesses / revisions
        return min(score * 5, 5)  # Maximaler Wert von 5