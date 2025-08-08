"""Module for defining the database models used in the application."""

from . import db

# Linktabelle für die Many-to-Many-Beziehung zwischen Track und Artist
track_artists = db.Table(
    "track_artists",
    db.metadata,
    db.Column(
        "track_id",
        db.String(100),
        db.ForeignKey("track.track_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "artist_id",
        db.Integer,
        db.ForeignKey("artist.artist_id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(db.Model):
    __tablename__ = "user"

    user_id = db.Column(db.String(100), primary_key=True)
    username = db.Column(db.String(100), nullable=True)
    max_streak = db.Column(db.Integer, default=0)
    current_streak = db.Column(db.Integer, default=0)
    spotify_access_token = db.Column(db.String(255), nullable=True)
    spotify_refresh_token = db.Column(db.String(255), nullable=True)
    spotify_token_expires_at = db.Column(db.DateTime, nullable=True)
    spotify_id = db.Column(db.String(100), unique=True, nullable=True)

    training_data = db.relationship(
        "TrainingData", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<User {self.username} (ID: {self.user_id}, Spotify: {self.spotify_id})>"
        )


class Artist(db.Model):
    __tablename__ = "artist"

    artist_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100))

    tracks = db.relationship("Track", secondary=track_artists, back_populates="artists")


class Track(db.Model):
    __tablename__ = "track"

    track_id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100))
    year = db.Column(db.Integer, default=-1)
    popularity = db.Column(db.Integer, default=0)

    artists = db.relationship(
        "Artist", secondary=track_artists, back_populates="tracks"
    )
    playlists = db.relationship("PlaylistTrack", back_populates="track")
    training_data = db.relationship("TrainingData", back_populates="track")

    def __repr__(self):
        return f"<Track {self.name}, Year: {self.year})>"


class Playlist(db.Model):
    __tablename__ = "playlist"

    playlist_id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(100))

    tracks = db.relationship("PlaylistTrack", back_populates="playlist")
    training_data = db.relationship("TrainingData", back_populates="playlist")


class PlaylistTrack(db.Model):
    __tablename__ = "playlist_track"

    playlist_id = db.Column(
        db.String(100),
        db.ForeignKey("playlist.playlist_id", ondelete="CASCADE"),
        primary_key=True,
    )
    track_id = db.Column(
        db.String(100),
        db.ForeignKey("track.track_id", ondelete="CASCADE"),
        primary_key=True,
    )

    playlist = db.relationship("Playlist", back_populates="tracks")
    track = db.relationship("Track", back_populates="playlists")


class TrainingData(db.Model):
    __tablename__ = "training_data"

    user_id = db.Column(
        db.String(100),
        db.ForeignKey("user.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    playlist_id = db.Column(
        db.String(100),
        db.ForeignKey("playlist.playlist_id", ondelete="CASCADE"),
        primary_key=True,
    )
    track_id = db.Column(
        db.String(100),
        db.ForeignKey("track.track_id", ondelete="CASCADE"),
        primary_key=True,
    )

    correct_guesses = db.Column(db.Integer, default=0)
    correct_in_row = db.Column(db.Integer, default=0)
    repeat_in_n = db.Column(db.Integer, default=1)
    revisions = db.Column(db.Integer, default=0)
    is_done = db.Column(db.Boolean, default=False)

    user = db.relationship("User", back_populates="training_data")
    playlist = db.relationship("Playlist", back_populates="training_data")
    track = db.relationship("Track", back_populates="training_data")

    def __repr__(self):
        return f"<TrainingData Track: {self.track_id}, repeat_in_n: {self.repeat_in_n}"
