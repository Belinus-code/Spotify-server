from spotify_server.trainer import SpotifyTrainer

import json

# Dateien einlesen
with open("training_data.json", "r") as f:
    training_data = json.load(f)

with open("internal_playlists.json", "r") as f:
    internal_playlists = json.load(f)

# Playlist-ID, die du vergleichen willst (z. B. per URL extrahieren oder manuell setzen)
playlist_id = "15hZ0ez6sHYhTeCCshxJTN"

# IDs aus den Trainingsdaten
trained_track_ids = set(training_data.get(playlist_id, {}).keys())

# IDs aus der internen Playlist
internal_track_ids = set(internal_playlists.get(playlist_id, []))

# IDs, die nur in training_data sind
only_in_training = trained_track_ids - internal_track_ids

# Ausgabe
print("Tracks in training_data, aber NICHT in internal_playlists:")
for track_id in only_in_training:
    print(track_id)