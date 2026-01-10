"""Factory für die Flask-Anwendung."""

from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from spotify_server.config import Config
from spotify_server.extensions import db


def create_app(config_class=Config):
    """
    Diese Funktion ist die "Application Factory".
    Sie erstellt und konfiguriert die gesamte Flask-Anwendung.
    """
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    # 1. Konfiguration laden
    app.config.from_object(config_class)

    # 2. Erweiterungen initialisieren
    db.init_app(app)

    with app.app_context():

        # Importiere alle Services und die Blueprint-Factory
        from .services.spotify_service import SpotifyService
        from .services.playback_service import PlaybackService
        from .services.song_repository import SongRepository
        from .services.training_repository import TrainingRepository
        from .services.user_repository import UserRepository
        from .services.training_service import TrainingService
        from .routes.training_routes import create_training_blueprint
        from .routes.auth_routes import create_auth_blueprint

        # --- 3. Dependency Injection: Erstelle alle Service-Instanzen EINMAL ---

        user_repository = UserRepository()

        # Services, die direkt von der Konfiguration abhängen
        spotify_service = SpotifyService(
            client_id=app.config["SPOTIFY_CLIENT_ID"],
            client_secret=app.config["SPOTIFY_CLIENT_SECRET"],
        )
        playback_service = PlaybackService(
            client_id=app.config["SPOTIFY_CLIENT_ID"],
            client_secret=app.config["SPOTIFY_CLIENT_SECRET"],
            redirect_uri=app.config[
                "SPOTIFY_REDIRECT_URI"
            ],  # Annahme: URI ist in config
            user_repository=user_repository,
        )

        # Repositories, die von anderen Services abhängen können
        song_repository = SongRepository(spotify_service=spotify_service)
        training_repository = TrainingRepository()  # Dieser hat keine Abhängigkeiten

        # Haupt-Service, der die Repositories als "Werkzeuge" bekommt
        training_service = TrainingService(
            song_repository=song_repository,
            training_repository=training_repository,
            playback_service=playback_service,
            user_repository=user_repository,
        )

        # --- 4. Blueprints registrieren ---

        # Erstelle das Blueprint, indem du der Factory die benötigten Services übergibst
        training_api_bp = create_training_blueprint(
            training_service=training_service,
            playback_service=playback_service,
            user_repository=user_repository,
            spotify_service=spotify_service
        )

        # Registriere das fertige Blueprint bei der App
        app.register_blueprint(training_api_bp)

        # Beispiel für ein weiteres Blueprint
        auth_bp = create_auth_blueprint(user_repository)
        app.register_blueprint(auth_bp)

        @app.route("/favicon.ico")
        def favicon():
            return send_from_directory(app.static_folder, "favicon.png")

    return app
