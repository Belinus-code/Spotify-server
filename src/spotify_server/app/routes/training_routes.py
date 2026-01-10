"""Modul für die Trainings-Routen der Spotify-Server-App."""

from flask import Blueprint, request, jsonify
from spotify_server.app.services.training_service import TrainingService
from spotify_server.app.services.playback_service import PlaybackService
from spotify_server.app.services.user_repository import UserRepository
from spotify_server.app.services.spotify_service import SpotifyService

# Annahme: Du hast eine Möglichkeit, den eingeloggten User zu bekommen, z.B. über flask-login
# from flask_login import current_user, login_required


# Diese Funktion wird in __init__.py aufgerufen, um den Service zu übergeben
def create_training_blueprint(
    training_service: TrainingService,
    playback_service: PlaybackService,
    user_repository: UserRepository,
    spotify_service: SpotifyService
):

    training_bp = Blueprint("training_api", __name__, url_prefix="/api")

    # HINWEIS: Bei einer echten Anwendung wären diese Routen mit @login_required geschützt,
    # und du würdest `current_user` anstelle der user_id aus dem Request-Body verwenden.
    # Zur Vereinfachung nutzen wir hier die übergebene user_id.

    @training_bp.route("/set_playlist", methods=["POST"])
    def set_playlist():
        data = request.get_json()
        if not data or "user_id" not in data or "playlist_url" not in data:
            return (
                jsonify({"error": "Benötigte Daten fehlen: user_id, playlist_url"}),
                400,
            )

        user_id = data.get("user_id")
        playlist_url = data.get("playlist_url")

        playlist_id = playlist_url.split("/")[-1].split("?")[0]

        # Initialisiere das Training und hole den ersten Song
        user = user_repository.get_user_by_id(user_id)
        if user is None:
            raise Exception
        next_track = training_service.choose_next_song(user, playlist_id)

        if not next_track:
            return (
                jsonify({"error": "Kein Song in der Playlist zum Starten gefunden."}),
                404,
            )

        error = playback_service.play_song(user, next_track.track_id)
        if error:
            return (
                jsonify({"error": "Kein aktiver Spotify-Client gefunden."}),
                404,
            )

        # Gib die notwendigen IDs an das Frontend zurück
        return jsonify({"playlist_id": playlist_id, "track_id": next_track.track_id})

    @training_bp.route("/check_guess", methods=["POST"])
    def check_guess():
        data = request.get_json()
        # Hier würdest du die Daten validieren...

        # Rufe deinen Service auf, um den Score zu berechnen
        score_result = training_service.calculate_score(
            data, data["user_id"]
        )  # Annahme: calculate_score verarbeitet das dict
        score = score_result.get("score")
        assert isinstance(score, int)
        training_service.update_training(
            data["playlist_id"],
            data["track_id"],
            score,
            data["user_id"],
        )
        # Gib das Ergebnis als JSON zurück
        return jsonify(
            {
                "score": score_result.get("score"),
                "correct_answer": {
                    "year": score_result.get("correct_year"),
                    "artist": score_result.get("correct_artist"),
                    "title": score_result.get("correct_title"),
                },
            }
        )

    @training_bp.route("/skip", methods=["POST"])
    def skip():
        data = request.get_json()
        user_id = data.get("user_id")
        playlist_id = data.get("playlist_id")
        user = user_repository.get_user_by_id(user_id)
        if user is None:
            raise Exception

        # Hole den nächsten Song vom Service
        next_track = training_service.choose_next_song(user, playlist_id)
        if not next_track:
            return jsonify({"error": "Kein weiterer Song verfügbar."}), 404

        playback_service.play_song(user_id, next_track.track_id)

        # Gib die neue Track-ID zurück
        return jsonify({"track_id": next_track.track_id})

    @training_bp.route("/play_pause", methods=["POST"])
    def play_pause():
        data = request.get_json()
        user_id = data.get("user_id")
        user = user_repository.get_user_by_id(user_id)
        if user is None:
            raise Exception
        playback_service.toggle_play_pause(user)

        return jsonify({"status": "ok"}), 200  # Einfache Bestätigung

    @training_bp.route("/test_new_song", methods=["POST"])
    def test_new_song():
        data = request.get_json()
        result = spotify_service.get_song_details(data.get("song_id"))
        return jsonify({"status": "ok", "results": result}), 200

    @training_bp.route("/stats", methods=["POST"])
    def stats():
        data = request.get_json()
        user_id = data.get("user_id")
        playlist_id = data.get("playlist_id")

        # Hole die Daten aus dem Repository
        finished_tracks = training_service.training_repository.get_finished_track_count(
            user_id, playlist_id
        )
        active_tracks = training_service.training_repository.get_active_track_count(
            user_id, playlist_id
        )
        total_revisions = training_service.training_repository.get_total_revisions(
            user_id, playlist_id
        )

        return jsonify(
            {
                "finished_tracks": finished_tracks,
                "active_tracks": active_tracks,
                "total_revisions": total_revisions,
            }
        )

    return training_bp
